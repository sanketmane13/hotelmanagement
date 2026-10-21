import logging
from datetime import datetime, timedelta
from decimal import Decimal

import stripe
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.models import Order
from orders.serializers import CreateOrderSerializer
from tables.models import BOOKING_FEE, Booking

from .models import Payment

from .serializers import (
    CheckoutSessionResponseSerializer,
    CreateCheckoutSessionSerializer,
    PaymentStatusSerializer,
    ReconcileCheckoutSessionSerializer,
    ReconcileCheckoutSessionResponseSerializer,
    RefundResponseSerializer,
    RefundSerializer,
)

from .services import (
    apply_checkout_event,
    apply_refund_event,
    create_checkout_session,
    refund_payment,
    stripe_is_configured,
)


logger = logging.getLogger(__name__)


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def checkout_response(payment):
        response_data = {
            "payment_id": payment.pk,
            "session_id": payment.stripe_checkout_session_id,
            "checkout_url": payment.stripe_checkout_session_url,
            "amount": payment.amount,
            "currency": payment.currency,
        }
        if payment.order_id:
            response_data["order_id"] = payment.order_id
        return response_data

    @staticmethod
    def save_checkout_session(payment, session):
        payment.stripe_checkout_session_id = session.id
        payment.stripe_checkout_session_url = session.url
        expires_at = getattr(session, "expires_at", None)
        if expires_at:
            payment.stripe_checkout_session_expires_at = datetime.fromtimestamp(
                expires_at,
                tz=timezone.get_current_timezone(),
            )
        else:
            payment.stripe_checkout_session_expires_at = (
                timezone.now() + timedelta(hours=23)
            )
        payment.save(
            update_fields=[
                "stripe_checkout_session_id",
                "stripe_checkout_session_url",
                "stripe_checkout_session_expires_at",
                "updated_at",
            ]
        )

    @extend_schema(
        request=CreateCheckoutSessionSerializer,
        responses={201: CheckoutSessionResponseSerializer},
        description=(
            "Create a ₹200 booking-fee Checkout Session, or a separate "
            "food-order Checkout Session for a paid booking."
        ),
    )
    def post(self, request):
        serializer = CreateCheckoutSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if not stripe_is_configured():
            return Response(
                {"detail": "Stripe is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        booking = get_object_or_404(
            Booking.objects.select_related("table"),
            pk=serializer.validated_data["booking_id"],
            user=request.user,
        ) #This checks that is bookig_id and is assosciated with requested user not not

        if "items" in serializer.validated_data:
            return self.create_order_checkout(
                request,
                booking,
                serializer.validated_data["items"],
            )

        if booking.status in {
            Booking.Status.CANCELLED,
            Booking.Status.COMPLETED,
        }:
            return Response(
                {"detail": "This booking cannot be paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if booking.payments.filter(
            order__isnull=True,
            status=Payment.PaymentStatus.SUCCESS,
        ).exists():
            return Response(
                {"detail": "This booking has already been paid."},
                status=status.HTTP_409_CONFLICT,
            )

        pending_payment = booking.payments.filter(
            order__isnull=True,
            status=Payment.PaymentStatus.PENDING,
        ).first()

        if pending_payment:
            if (
                pending_payment.stripe_checkout_session_expires_at
                and pending_payment.stripe_checkout_session_expires_at
                <= timezone.now()
            ):
                pending_payment.status = Payment.PaymentStatus.EXPIRED
                pending_payment.save(update_fields=["status", "updated_at"])
            elif pending_payment.stripe_checkout_session_url:
                return Response(
                    self.checkout_response(pending_payment),
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {
                        "detail": (
                            "A checkout session is already pending "
                            "for this booking."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        try:
            with transaction.atomic():
                payment = Payment.objects.create(
                    booking=booking,
                    amount=BOOKING_FEE,
                )

        except IntegrityError:
            if booking.payments.filter(
                order__isnull=True,
                status=Payment.PaymentStatus.PENDING,
            ).exists():
                return Response(
                    {"detail": "A checkout session is already pending for this booking."},
                    status=status.HTTP_409_CONFLICT,
                )
            raise

        try:
            session = create_checkout_session(payment)
        except stripe.error.StripeError:
            logger.exception("Stripe checkout session creation failed.")
            payment.status = Payment.PaymentStatus.FAILED
            payment.save(update_fields=["status", "updated_at"])
            return Response(
                {"detail": "Could not start checkout. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        self.save_checkout_session(payment, session)
        return Response(
            self.checkout_response(payment),
            status=status.HTTP_201_CREATED,
        )

    def create_order_checkout(self, request, booking, items):
        try:
            with transaction.atomic():
                booking = get_object_or_404(
                    Booking.objects.select_for_update().select_related("table"),
                    pk=booking.pk,
                    user=request.user,
                )

                if booking.status != Booking.Status.CONFIRMED or not booking.payments.filter(
                    order__isnull=True,
                    status=Payment.PaymentStatus.SUCCESS,
                ).exists():
                    return Response(
                        {"detail": "Pay the booking fee before placing an order."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                requested_items = sorted(
                    (item["menu_item"].pk, item["quantity"])
                    for item in items
                )
                pending_payments = (
                    booking.payments
                    .select_related("order")
                    .filter(
                        status=Payment.PaymentStatus.PENDING,
                        order__isnull=False,
                    )
                )
                for pending_payment in pending_payments:
                    if (
                        pending_payment.stripe_checkout_session_expires_at
                        and pending_payment.stripe_checkout_session_expires_at
                        <= timezone.now()
                    ):
                        pending_payment.status = Payment.PaymentStatus.EXPIRED
                        pending_payment.save(
                            update_fields=["status", "updated_at"]
                        )
                        pending_payment.order.payment_status = (
                            Order.PaymentStatus.FAILED
                        )
                        pending_payment.order.save(
                            update_fields=["payment_status", "updated_at"]
                        )
                        continue

                    pending_items = (
                        sorted(
                            pending_payment.order.items.values_list(
                                "menu_item_id",
                                "quantity",
                            )
                        )
                        if pending_payment.order_id
                        else []
                    )
                    if requested_items == pending_items:
                        if pending_payment.stripe_checkout_session_url:
                            return Response(
                                self.checkout_response(pending_payment),
                                status=status.HTTP_201_CREATED,
                            )
                        return Response(
                            {
                                "detail": (
                                    "A checkout session is already being "
                                    "created for this order."
                                )
                            },
                            status=status.HTTP_409_CONFLICT,
                        )

                order_serializer = CreateOrderSerializer(
                    data={
                        "booking": booking.pk,
                        "items": [
                            {
                                "menu_item": item["menu_item"].pk,
                                "quantity": item["quantity"],
                            }
                            for item in items
                        ],
                    },
                    context={"request": request},
                )
                order_serializer.is_valid(raise_exception=True)

                order_total = sum(
                    (
                        item["menu_item"].price * item["quantity"]
                        for item in order_serializer.validated_data["items"]
                    ),
                    Decimal("0.00"),
                )
                amount = order_total

                if amount <= 0:
                    return Response(
                        {"detail": "The checkout total must be greater than zero."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                order = order_serializer.save()
                payment = Payment.objects.create(
                    booking=booking,
                    order=order,
                    amount=amount,
                )
                session = create_checkout_session(payment)
                self.save_checkout_session(payment, session)
        except stripe.error.StripeError:
            logger.exception("Stripe order checkout session creation failed.")
            return Response(
                {"detail": "Could not start checkout. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except IntegrityError:
            if booking.payments.filter(
                status=Payment.PaymentStatus.PENDING,
                order__isnull=True,
            ).exists():
                return Response(
                    {
                        "detail": (
                            "A checkout session is already pending "
                            "for this booking."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            raise

        return Response(
            self.checkout_response(payment),
            status=status.HTTP_201_CREATED,
        )


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=PaymentStatusSerializer)
    def get(self, request, payment_id):
        payment = get_object_or_404(
            Payment.objects.select_related("booking"),
            pk=payment_id,
            booking__user=request.user,
        )
        return Response(PaymentStatusSerializer(payment).data)


class ReconcileCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ReconcileCheckoutSessionSerializer

    @extend_schema(
        request=ReconcileCheckoutSessionSerializer,
        responses={200: ReconcileCheckoutSessionResponseSerializer},
    )
    def post(self, request):
        serializer = ReconcileCheckoutSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session_id = serializer.validated_data["session_id"]
        payment = get_object_or_404(
            Payment.objects.select_related("booking", "order"),
            stripe_checkout_session_id=session_id,
            booking__user=request.user,
        )

        if not stripe_is_configured():
            return Response(
                {"detail": "Stripe is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            session = stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError:
            logger.exception("Stripe checkout session verification failed.")
            return Response(
                {"detail": "Could not verify the Stripe checkout session."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if session.id != payment.stripe_checkout_session_id:
            return Response(
                {"detail": "Stripe returned a different checkout session."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        session_data = session.to_dict()
        if session.status == "expired":
            apply_checkout_event(
                {
                    "type": "checkout.session.expired",
                    "data": {"object": session_data},
                }
            )
        elif session.status == "complete":
            apply_checkout_event(
                {
                    "type": "checkout.session.completed",
                    "data": {"object": session_data},
                }
            )

        payment.refresh_from_db()
        payment.booking.refresh_from_db()
        return Response(
            {
                "payment_status": payment.status,
                "booking_status": payment.booking.status,
                "order_id": payment.order_id,
            }
        )


class RefundView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=RefundSerializer,
        responses={200: RefundResponseSerializer},
        description="Request a full refund for one of your successful payments.",
    )
    def post(self, request):
        serializer = RefundSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = get_object_or_404(
            Payment.objects.select_related("booking"),
            pk=serializer.validated_data["payment_id"],
            booking__user=request.user,
        )
        if payment.status != Payment.PaymentStatus.SUCCESS:
            return Response(
                {"detail": "Only successful payments can be refunded."},
                status=status.HTTP_409_CONFLICT,
            )
        if not payment.stripe_payment_intent_id:
            return Response(
                {"detail": "This payment cannot be refunded through Stripe."},
                status=status.HTTP_409_CONFLICT,
            )
        if not stripe_is_configured():
            return Response(
                {"detail": "Stripe is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            refund = refund_payment(payment)
        except stripe.error.StripeError:
            logger.exception("Stripe refund request failed.")
            return Response(
                {"detail": "Could not process the refund. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if refund.status == "succeeded":
            payment.status = Payment.PaymentStatus.REFUNDED
            payment.save(update_fields=["status", "updated_at"])
            if payment.order_id:
                payment.order.payment_status = Order.PaymentStatus.REFUNDED
                payment.order.save(
                    update_fields=["payment_status", "updated_at"]
                )

        return Response(
            {
                "payment_id": payment.pk,
                "payment_status": payment.status,
                "refund_status": refund.status,
            },
            status=status.HTTP_200_OK,
        )


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)
    if not stripe_is_configured(webhook=True):
        return JsonResponse(
            {"detail": "Stripe webhook is not configured on the server."},
            status=503,
        )

    signature = request.headers.get("Stripe-Signature")
    if not signature:
        return JsonResponse({"detail": "Missing Stripe signature."}, status=400)

    # Only Stripe-signed events are allowed to change payment state.
    try:
        event = stripe.Webhook.construct_event(
            request.body,
            signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return JsonResponse({"detail": "Invalid Stripe webhook signature."}, status=400)

    try:
        if event["type"].startswith("checkout.session."):
            apply_checkout_event(event)
        elif event["type"] == "charge.refunded":
            apply_refund_event(event)
    except (KeyError, TypeError, ValueError):
        logger.exception("Could not process Stripe webhook event.")
        return JsonResponse({"detail": "Invalid Stripe event payload."}, status=400)

    return JsonResponse({"received": True})
