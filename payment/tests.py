from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient

from menu.models import Category, MenuItem
from orders.models import Order, OrderItem
from tables.models import Booking, Table

from .models import Payment
from .services import apply_checkout_event, create_checkout_session


@override_settings(
    STRIPE_SECRET_KEY="sk_test_for_unit_tests",
    STRIPE_WEBHOOK_SECRET="whsec_for_unit_tests",
)
class PaymentAPITests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.customer = user_model.objects.create_user(
            username="payment-customer",
            email="payment-customer@example.com",
            phone="5550001111",
            password="test-password",
        )
        self.other_customer = user_model.objects.create_user(
            username="other-customer",
            email="other-customer@example.com",
            phone="5550002222",
            password="test-password",
        )
        self.table = Table.objects.create(
            table_number=21,
            capacity=2,
            booking_price=Decimal("125.50"),
        )
        self.booking = Booking.objects.create(
            user=self.customer,
            table=self.table,
            booking_date=date.today(),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        self.category = Category.objects.create(name="Payments test menu")
        self.menu_item = MenuItem.objects.create(
            category=self.category,
            name="Test meal",
            price=Decimal("30.00"),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.customer)

    def mark_booking_paid(self):
        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status", "updated_at"])
        return Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            status=Payment.PaymentStatus.SUCCESS,
            stripe_payment_intent_id="pi_booking_fee",
        )

    def test_checkout_openapi_schema_documents_booking_id_request_body(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        operation = schema["paths"]["/api/payments/create-checkout-session/"]["post"]

        request_body = operation["requestBody"]
        self.assertTrue(request_body["required"])
        request_schema = request_body["content"]["application/json"]["schema"]
        self.assertEqual(request_schema["$ref"], "#/components/schemas/CreateCheckoutSession")
        self.assertIn(
            "booking_id",
            schema["components"]["schemas"]["CreateCheckoutSession"]["required"],
        )
        self.assertIn(
            "items",
            schema["components"]["schemas"]["CreateCheckoutSession"]["properties"],
        )
        self.assertNotIn(
            "items",
            schema["components"]["schemas"]["CreateCheckoutSession"]["required"],
        )

    @patch("payment.views.create_checkout_session")
    def test_checkout_uses_server_price_and_returns_stripe_session(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_session",
            url="https://checkout.stripe.test/session",
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {"booking_id": self.booking.pk, "amount": "0.01"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(payment.amount, Decimal("200.00"))
        self.assertEqual(self.booking.booking_price, Decimal("200.00"))
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(payment.stripe_checkout_session_id, "cs_test_session")
        self.assertEqual(
            response.data["checkout_url"],
            "https://checkout.stripe.test/session",
        )

    @patch("payment.views.create_checkout_session")
    def test_cart_checkout_creates_order_and_charges_only_food(
        self,
        create_session,
    ):
        self.mark_booking_paid()
        create_session.return_value = SimpleNamespace(
            id="cs_test_cart_session",
            url="https://checkout.stripe.test/cart-session",
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["order_id"])
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(order.total_amount, Decimal("60.00"))
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertEqual(payment.order_id, order.pk)
        self.assertEqual(payment.amount, Decimal("60.00"))
        self.assertEqual(response.data["amount"], Decimal("60.00"))
        create_session.assert_called_once_with(payment)

    @patch("payment.views.create_checkout_session")
    def test_paid_booking_checkout_charges_only_food_order(
        self,
        create_session,
    ):
        Payment.objects.create(
            booking=self.booking,
            amount=Decimal("125.50"),
            status=Payment.PaymentStatus.SUCCESS,
            stripe_payment_intent_id="pi_previously_paid",
        )
        self.booking.status = Booking.Status.CONFIRMED
        self.booking.save(update_fields=["status", "updated_at"])
        create_session.return_value = SimpleNamespace(
            id="cs_test_food_only",
            url="https://checkout.stripe.test/food-only",
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 1},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(payment.amount, Decimal("30.00"))

    @patch("payment.views.create_checkout_session")
    def test_cart_checkout_reuses_pending_session_for_same_items(
        self,
        create_session,
    ):
        self.mark_booking_paid()
        create_session.side_effect = [
            SimpleNamespace(
                id="cs_test_reusable",
                url="https://checkout.stripe.test/reusable",
            ),
            SimpleNamespace(
                id="cs_test_different_cart",
                url="https://checkout.stripe.test/different-cart",
            ),
        ]
        payload = {
            "booking_id": self.booking.pk,
            "items": [
                {"menu_item": self.menu_item.pk, "quantity": 2},
            ],
        }

        first_response = self.client.post(
            reverse("create-checkout-session"),
            payload,
            format="json",
        )
        retry_response = self.client.post(
            reverse("create-checkout-session"),
            payload,
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(retry_response.status_code, 201)
        self.assertEqual(
            retry_response.data["checkout_url"],
            "https://checkout.stripe.test/reusable",
        )
        self.assertEqual(
            retry_response.data["order_id"],
            first_response.data["order_id"],
        )
        self.assertEqual(Order.objects.count(), 1)
        create_session.assert_called_once()

        payload["items"][0]["quantity"] = 3
        different_cart_response = self.client.post(
            reverse("create-checkout-session"),
            payload,
            format="json",
        )
        self.assertEqual(different_cart_response.status_code, 201)
        self.assertNotEqual(
            different_cart_response.data["session_id"],
            first_response.data["session_id"],
        )
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(create_session.call_count, 2)

    @patch("payment.views.create_checkout_session")
    def test_different_orders_can_have_independent_pending_sessions(
        self,
        create_session,
    ):
        self.mark_booking_paid()
        create_session.side_effect = [
            SimpleNamespace(
                id="cs_test_first_order",
                url="https://checkout.stripe.test/first-order",
            ),
            SimpleNamespace(
                id="cs_test_second_order",
                url="https://checkout.stripe.test/second-order",
            ),
        ]

        first_response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 1},
                ],
            },
            format="json",
        )
        second_response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 2},
                ],
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        self.assertNotEqual(
            first_response.data["order_id"],
            second_response.data["order_id"],
        )
        self.assertNotEqual(
            first_response.data["session_id"],
            second_response.data["session_id"],
        )
        self.assertEqual(
            Payment.objects.filter(
                booking=self.booking,
                status=Payment.PaymentStatus.PENDING,
                order__isnull=False,
            ).count(),
            2,
        )

    @patch("payment.views.create_checkout_session")
    def test_successful_order_payment_does_not_block_a_later_order(
        self,
        create_session,
    ):
        self.mark_booking_paid()
        create_session.side_effect = [
            SimpleNamespace(
                id="cs_test_paid_order",
                url="https://checkout.stripe.test/paid-order",
            ),
            SimpleNamespace(
                id="cs_test_later_order",
                url="https://checkout.stripe.test/later-order",
            ),
        ]
        first_response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 1},
                ],
            },
            format="json",
        )
        first_payment = Payment.objects.get(pk=first_response.data["payment_id"])
        apply_checkout_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": first_payment.stripe_checkout_session_id,
                        "payment_status": "paid",
                        "payment_intent": "pi_first_order",
                    }
                },
            }
        )

        second_response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 1},
                ],
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 201)
        first_payment.refresh_from_db()
        second_payment = Payment.objects.get(pk=second_response.data["payment_id"])
        self.assertEqual(first_payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(second_payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(second_payment.amount, Decimal("30.00"))

    @patch("payment.views.create_checkout_session")
    def test_expired_booking_checkout_does_not_block_a_new_attempt(
        self,
        create_session,
    ):
        expired_payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            stripe_checkout_session_id="cs_expired_booking",
            stripe_checkout_session_url="https://checkout.stripe.test/expired",
            stripe_checkout_session_expires_at=timezone.now() - timedelta(minutes=1),
        )
        create_session.return_value = SimpleNamespace(
            id="cs_new_booking_attempt",
            url="https://checkout.stripe.test/new-booking",
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {"booking_id": self.booking.pk},
            format="json",
        )

        expired_payment.refresh_from_db()
        new_payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(expired_payment.status, Payment.PaymentStatus.EXPIRED)
        self.assertEqual(new_payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(new_payment.amount, Decimal("200.00"))

    @patch("payment.views.create_checkout_session")
    def test_expired_order_checkout_allows_the_same_cart_to_retry(
        self,
        create_session,
    ):
        self.mark_booking_paid()
        order = Order.objects.create(
            customer=self.customer,
            table=self.table,
            booking=self.booking,
            total_amount=Decimal("30.00"),
        )
        OrderItem.objects.create(
            order=order,
            menu_item=self.menu_item,
            quantity=1,
            unit_price=Decimal("30.00"),
        )
        expired_payment = Payment.objects.create(
            booking=self.booking,
            order=order,
            amount=Decimal("30.00"),
            stripe_checkout_session_id="cs_expired_order",
            stripe_checkout_session_url="https://checkout.stripe.test/expired-order",
            stripe_checkout_session_expires_at=timezone.now() - timedelta(minutes=1),
        )
        create_session.return_value = SimpleNamespace(
            id="cs_new_order_attempt",
            url="https://checkout.stripe.test/new-order",
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 1},
                ],
            },
            format="json",
        )

        expired_payment.refresh_from_db()
        new_payment = Payment.objects.get(pk=response.data["payment_id"])
        order.refresh_from_db()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(expired_payment.status, Payment.PaymentStatus.EXPIRED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)
        self.assertEqual(new_payment.status, Payment.PaymentStatus.PENDING)
        self.assertNotEqual(new_payment.order_id, order.pk)

    @patch("payment.services.stripe.checkout.Session.create")
    def test_stripe_session_contains_only_food_items(
        self,
        stripe_create,
    ):
        self.mark_booking_paid()
        order = Order.objects.create(
            customer=self.customer,
            table=self.table,
            total_amount=Decimal("60.00"),
        )
        OrderItem.objects.create(
            order=order,
            menu_item=self.menu_item,
            quantity=2,
            unit_price=Decimal("30.00"),
        )
        payment = Payment.objects.create(
            booking=self.booking,
            order=order,
            amount=Decimal("60.00"),
        )
        stripe_create.return_value = SimpleNamespace(
            id="cs_test_line_items",
            url="https://checkout.stripe.test/line-items",
        )

        create_checkout_session(payment)

        self.assertEqual(
            stripe_create.call_args.kwargs["idempotency_key"],
            str(payment.stripe_idempotency_key),
        )
        self.assertNotIn(
            "payment_method_types",
            stripe_create.call_args.kwargs,
        )
        line_items = stripe_create.call_args.kwargs["line_items"]
        self.assertEqual(
            [
                (
                    line_item["price_data"]["product_data"]["name"],
                    line_item["price_data"]["unit_amount"],
                    line_item["quantity"],
                )
                for line_item in line_items
            ],
            [
                ("Test meal", 3000, 2),
            ],
        )

    @patch(
        "payment.views.create_checkout_session",
        side_effect=stripe.error.StripeError(
            "Stripe unavailable",
        ),
    )
    def test_failed_stripe_cart_checkout_does_not_create_order_or_payment(
        self,
        create_session,
    ):
        self.mark_booking_paid()
        response = self.client.post(
            reverse("create-checkout-session"),
            {
                "booking_id": self.booking.pk,
                "items": [
                    {"menu_item": self.menu_item.pk, "quantity": 1},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(
            Payment.objects.filter(order__isnull=True).count(),
            1,
        )
        self.assertFalse(Payment.objects.filter(order__isnull=False).exists())
        create_session.assert_called_once()

    @patch("payment.services.stripe.checkout.Session.create")
    def test_new_checkout_attempt_uses_a_new_idempotency_key(
        self,
        stripe_create,
    ):
        self.mark_booking_paid()
        stripe_create.side_effect = [
            stripe.error.IdempotencyError(
                "The old key was used with different parameters.",
                "checkout-payment-1",
            ),
            SimpleNamespace(
                id="cs_test_new_key",
                url="https://checkout.stripe.test/new-key",
            ),
        ]
        payload = {
            "booking_id": self.booking.pk,
            "items": [
                {"menu_item": self.menu_item.pk, "quantity": 1},
            ],
        }

        failed_response = self.client.post(
            reverse("create-checkout-session"),
            payload,
            format="json",
        )
        successful_response = self.client.post(
            reverse("create-checkout-session"),
            payload,
            format="json",
        )

        self.assertEqual(failed_response.status_code, 502)
        self.assertEqual(successful_response.status_code, 201)
        first_key = stripe_create.call_args_list[0].kwargs["idempotency_key"]
        second_key = stripe_create.call_args_list[1].kwargs["idempotency_key"]
        self.assertNotEqual(first_key, second_key)
        self.assertEqual(
            Payment.objects.filter(
                booking=self.booking,
                order__isnull=False,
            ).count(),
            1,
        )

    def test_customer_cannot_create_checkout_for_another_users_booking(self):
        other_booking = Booking.objects.create(
            user=self.other_customer,
            table=Table.objects.create(
                table_number=22,
                capacity=2,
                booking_price=Decimal("80.00"),
            ),
            booking_date=date.today(),
            start_time=time(20, 0),
            end_time=time(21, 0),
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {"booking_id": other_booking.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Payment.objects.exists())

    @patch("payment.views.create_checkout_session")
    def test_booking_checkout_uses_fixed_price_even_when_table_price_is_zero(
        self,
        create_session,
    ):
        create_session.return_value = SimpleNamespace(
            id="cs_test_fixed_booking_fee",
            url="https://checkout.stripe.test/fixed-booking-fee",
        )
        self.table.booking_price = Decimal("0.00")
        self.table.save(update_fields=["booking_price"])
        unpaid_booking = Booking.objects.create(
            user=self.customer,
            table=self.table,
            booking_date=date.today(),
            start_time=time(20, 0),
            end_time=time(21, 0),
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {"booking_id": unpaid_booking.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(pk=response.data["payment_id"])
        self.assertEqual(payment.amount, Decimal("200.00"))
        create_session.assert_called_once_with(payment)

    @patch("payment.views.create_checkout_session")
    def test_checkout_does_not_create_a_second_pending_payment(self, create_session):
        Payment.objects.create(
            booking=self.booking,
            amount=Decimal("125.50"),
            stripe_checkout_session_id="cs_existing_pending",
        )

        response = self.client.post(
            reverse("create-checkout-session"),
            {"booking_id": self.booking.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(Payment.objects.filter(booking=self.booking).count(), 1)
        create_session.assert_not_called()

    def test_status_is_only_visible_to_booking_owner(self):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("125.50"),
        )
        self.client.force_authenticate(user=self.other_customer)

        response = self.client.get(
            reverse("payment-status", kwargs={"payment_id": payment.pk}),
        )

        self.assertEqual(response.status_code, 404)

    @patch("payment.views.refund_payment")
    def test_booking_owner_can_refund_successful_payment(self, refund_payment_mock):
        refund_payment_mock.return_value = SimpleNamespace(status="succeeded")
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("125.50"),
            status=Payment.PaymentStatus.SUCCESS,
            stripe_payment_intent_id="pi_test_refundable",
        )

        response = self.client.post(
            reverse("refund-payment"),
            {"payment_id": payment.pk},
            format="json",
        )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.PaymentStatus.REFUNDED)
        refund_payment_mock.assert_called_once_with(payment)

    @patch("payment.views.refund_payment")
    def test_pending_payment_cannot_be_refunded(self, refund_payment_mock):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("125.50"),
            stripe_payment_intent_id="pi_test_pending",
        )

        response = self.client.post(
            reverse("refund-payment"),
            {"payment_id": payment.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        refund_payment_mock.assert_not_called()

    @patch("payment.views.stripe.Webhook.construct_event")
    def test_signed_checkout_webhook_marks_payment_successful(self, construct_event):
        order = Order.objects.create(
            customer=self.customer,
            table=self.table,
        )
        payment = Payment.objects.create(
            booking=self.booking,
            order=order,
            amount=Decimal("125.50"),
            stripe_checkout_session_id="cs_test_webhook",
        )
        construct_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_webhook",
                    "payment_status": "paid",
                    "payment_intent": "pi_test_paid",
                }
            },
        }

        response = APIClient().post(
            reverse("stripe-webhook"),
            data=b'{"id":"evt_test"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(payment.stripe_payment_intent_id, "pi_test_paid")
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_successful_booking_payment_confirms_booking(self):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            stripe_checkout_session_id="cs_test_booking_payment",
        )

        apply_checkout_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": payment.stripe_checkout_session_id,
                        "payment_status": "paid",
                        "payment_intent": "pi_booking_paid",
                    }
                },
            }
        )

        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)

    @patch("payment.views.stripe.checkout.Session.retrieve")
    def test_checkout_return_reconciles_paid_booking_with_stripe(
        self,
        retrieve_session,
    ):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            stripe_checkout_session_id="cs_returned_paid",
        )
        retrieve_session.return_value = stripe.checkout.Session.construct_from(
            {
                "id": "cs_returned_paid",
                "status": "complete",
                "payment_status": "paid",
                "payment_intent": "pi_returned_paid",
            },
            "sk_test_for_unit_tests",
        )

        response = self.client.post(
            reverse("reconcile-checkout-session"),
            {"session_id": "cs_returned_paid"},
            format="json",
        )

        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.PaymentStatus.SUCCESS)
        self.assertEqual(self.booking.status, Booking.Status.CONFIRMED)
        retrieve_session.assert_called_once_with("cs_returned_paid")

    @patch("payment.views.stripe.checkout.Session.retrieve")
    def test_checkout_return_does_not_confirm_unpaid_session(
        self,
        retrieve_session,
    ):
        payment = Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            stripe_checkout_session_id="cs_returned_unpaid",
        )
        retrieve_session.return_value = SimpleNamespace(
            id="cs_returned_unpaid",
            status="complete",
            to_dict=lambda: {
                "id": "cs_returned_unpaid",
                "payment_status": "unpaid",
                "payment_intent": None,
            },
        )

        response = self.client.post(
            reverse("reconcile-checkout-session"),
            {"session_id": "cs_returned_unpaid"},
            format="json",
        )

        payment.refresh_from_db()
        self.booking.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.PaymentStatus.PENDING)
        self.assertEqual(
            self.booking.status,
            Booking.Status.PENDING_PAYMENT,
        )

    @patch("payment.views.stripe.Webhook.construct_event")
    def test_expired_checkout_marks_related_order_payment_failed(
        self,
        construct_event,
    ):
        order = Order.objects.create(
            customer=self.customer,
            table=self.table,
        )
        payment = Payment.objects.create(
            booking=self.booking,
            order=order,
            amount=Decimal("155.50"),
            stripe_checkout_session_id="cs_test_expired",
        )
        construct_event.return_value = {
            "type": "checkout.session.expired",
            "data": {
                "object": {
                    "id": "cs_test_expired",
                }
            },
        }

        response = APIClient().post(
            reverse("stripe-webhook"),
            data=b'{"id":"evt_expired"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test-signature",
        )

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.PaymentStatus.EXPIRED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.FAILED)

    @patch("payment.views.stripe.Webhook.construct_event", side_effect=ValueError)
    def test_webhook_rejects_invalid_signature(self, construct_event):
        response = APIClient().post(
            reverse("stripe-webhook"),
            data=b'{"id":"evt_test"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, 400)
