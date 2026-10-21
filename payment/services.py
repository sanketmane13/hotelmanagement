import logging
from datetime import timedelta
from decimal import Decimal

import stripe
from django.conf import settings
from django.utils import timezone

from orders.models import Order
from tables.models import Booking

from .email_service import send_payment_confirmation_email
from .models import Payment


logger = logging.getLogger(__name__)


def stripe_is_configured(*, webhook=False):
    secret = (
        settings.STRIPE_WEBHOOK_SECRET
        if webhook
        else settings.STRIPE_SECRET_KEY
    )
    return bool(secret)


def create_checkout_session(payment):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    if payment.order_id:
        order = payment.order
        line_items = []

        for item in order.items.select_related("menu_item"):
            line_items.append(
                {
                    "price_data": {
                        "currency": payment.currency.lower(),
                        "product_data": {
                            "name": item.menu_item.name,
                        },
                        "unit_amount": int(item.unit_price * Decimal("100")),
                    },
                    "quantity": item.quantity,
                }
            )
    else:
        # Stripe expects paise for INR, rather than a decimal rupee amount.
        amount_in_minor_units = int(payment.amount * Decimal("100"))
        line_items = [
            {
                "price_data": {
                    "currency": payment.currency.lower(),
                    "product_data": {
                        "name": f"Table booking #{payment.booking_id}",
                    },
                    "unit_amount": amount_in_minor_units,
                },
                "quantity": 1,
            }
        ]

    return stripe.checkout.Session.create(
        mode="payment",
        line_items=line_items,
        expires_at=int((timezone.now() + timedelta(hours=23)).timestamp()),
        metadata={
            "payment_id": str(payment.pk),
            "booking_id": str(payment.booking_id),
            **(
                {"order_id": str(payment.order_id)}
                if payment.order_id
                else {}
            ),
        },
        success_url=settings.STRIPE_CHECKOUT_SUCCESS_URL,
        cancel_url=settings.STRIPE_CHECKOUT_CANCEL_URL,
        idempotency_key=str(payment.stripe_idempotency_key),
    )


def refund_payment(payment):
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe.Refund.create(
        payment_intent=payment.stripe_payment_intent_id,
        idempotency_key=f"refund-{payment.stripe_idempotency_key}",
    )


def apply_checkout_event(event, *, send_confirmation_email=False):
    event_type = event["type"]
    session = event["data"]["object"]
    payment = Payment.objects.select_related("order", "booking").filter(
        stripe_checkout_session_id=session["id"],
    ).first()

    if payment is None:
        logger.warning("Stripe event references an unknown checkout session.")
        return

    # Only a verified Stripe event, never a browser redirect, can confirm payment.
    if event_type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:
        payment_succeeded = (
            event_type == "checkout.session.async_payment_succeeded"
            or session.get("payment_status") == "paid"
        )
        if payment_succeeded and payment.status != Payment.PaymentStatus.REFUNDED:
            payment.status = Payment.PaymentStatus.SUCCESS
            payment_intent = session.get("payment_intent")
            if isinstance(payment_intent, dict):
                payment_intent = payment_intent.get("id")
            payment.stripe_payment_intent_id = payment_intent or None
            payment.save(
                update_fields=[
                    "status",
                    "stripe_payment_intent_id",
                    "updated_at",
                ]
            )
            if payment.order_id:
                payment.order.payment_status = Order.PaymentStatus.PAID
                payment.order.save(
                    update_fields=["payment_status", "updated_at"]
                )
            elif payment.booking.status == Booking.Status.PENDING_PAYMENT:
                payment.booking.status = Booking.Status.CONFIRMED
                payment.booking.save(update_fields=["status", "updated_at"])
            if send_confirmation_email:
                return send_payment_confirmation_email(payment.pk)
            
    elif event_type in {
        "checkout.session.async_payment_failed",
        "checkout.session.cancelled",
        "checkout.session.expired",
    }:
        if payment.status == Payment.PaymentStatus.PENDING:
            payment.status = {
                "checkout.session.async_payment_failed": (
                    Payment.PaymentStatus.FAILED
                ),
                "checkout.session.cancelled": Payment.PaymentStatus.CANCELLED,
                "checkout.session.expired": Payment.PaymentStatus.EXPIRED,
            }[event_type]
            payment.save(update_fields=["status", "updated_at"])
            if payment.order_id:
                payment.order.payment_status = Order.PaymentStatus.FAILED
                payment.order.save(
                    update_fields=["payment_status", "updated_at"]
                )


def apply_refund_event(event):
    charge = event["data"]["object"]
    if not charge.get("refunded"):
        return

    payment_intent = charge.get("payment_intent")
    if isinstance(payment_intent, dict):
        payment_intent = payment_intent.get("id")
    if not payment_intent:
        return

    payments = Payment.objects.select_related("order").filter(
        stripe_payment_intent_id=payment_intent,
        status=Payment.PaymentStatus.SUCCESS,
    )
    for payment in payments:
        payment.status = Payment.PaymentStatus.REFUNDED
        payment.save(update_fields=["status", "updated_at"])
        if payment.order_id:
            payment.order.payment_status = Order.PaymentStatus.REFUNDED
            payment.order.save(
                update_fields=["payment_status", "updated_at"]
            )