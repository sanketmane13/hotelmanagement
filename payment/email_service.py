import logging
from decimal import Decimal

from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string

from .models import Payment


logger = logging.getLogger(__name__)


def send_payment_confirmation_email(payment_id):
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_id)
        if (
            payment.status != Payment.PaymentStatus.SUCCESS
            or payment.confirmation_email_sent
        ):
            return True

        if payment.order_id:
            order = payment.order
            customer = order.customer
            items = [
                {
                    "name": item.menu_item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "subtotal": item.subtotal,
                }
                for item in order.items.select_related("menu_item")
            ]
            template_name = "customer/emails/order_payment_success.html"
            subject = f"Payment confirmed for Order #{order.pk}"
            text_message = (
                f"Your payment for Order #{order.pk} has been confirmed. "
                f"Payment ID: {payment.pk}. Amount: "
                f"{payment.currency} {payment.amount}."
            )
            context = {
                "customer_name": customer.get_full_name() or customer.username,
                "order": order,
                "booking": payment.booking,
                "table": payment.booking.table,
                "items": items,
                "subtotal": sum(
                    (item["subtotal"] for item in items),
                    start=Decimal("0.00"),
                ),
                "payment": payment,
                "hotel_name": "Hotel Management",
            }
        else:
            customer = payment.booking.user
            template_name = "customer/emails/booking_payment_success.html"
            subject = f"Booking payment confirmed - Booking #{payment.booking_id}"
            text_message = (
                f"Your booking payment has been confirmed. "
                f"Booking ID: {payment.booking_id}. Payment ID: {payment.pk}. "
                f"Amount: {payment.currency} {payment.amount}."
            )
            context = {
                "customer_name": customer.get_full_name() or customer.username,
                "booking": payment.booking,
                "table": payment.booking.table,
                "payment": payment,
                "hotel_name": "Hotel Management",
            }

        try:
            html_message = render_to_string(template_name, context)
            email = EmailMultiAlternatives(
                subject,
                text_message,
                None,
                [customer.email],
            )
            email.attach_alternative(html_message, "text/html")
            sent_count = email.send(fail_silently=False)
        except Exception:
            logger.exception(
                "Could not send confirmation email for payment %s.",
                payment.pk,
            )
            return False

        if not sent_count:
            logger.error(
                "Email backend did not send confirmation for payment %s.",
                payment.pk,
            )
            return False

        payment.confirmation_email_sent = True
        payment.save(update_fields=["confirmation_email_sent"])

    return True
