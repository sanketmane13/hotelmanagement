import uuid

from django.db import models
from django.db.models import Q
from django.conf import settings

class Payment(models.Model):

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        SUCCESS = "SUCCESS", "Success"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"
        EXPIRED = "EXPIRED", "Expired"
        REFUNDED = "REFUNDED", "Refunded"

    booking = models.ForeignKey(
        "tables.Booking",
        on_delete=models.PROTECT,
        related_name="payments",
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
        blank=True,
        null=True,
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="INR",
    )

    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        unique=True,
    )

    stripe_checkout_session_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
    )

    stripe_checkout_session_expires_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    stripe_idempotency_key = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )

    confirmation_email_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=Q(status="PENDING", order__isnull=True),
                name="one_pending_booking_payment",
            ),
            models.UniqueConstraint(
                fields=["order"],
                condition=Q(status="PENDING", order__isnull=False),
                name="one_pending_payment_per_order",
            ),
        ]

    def __str__(self):
        return f"Payment #{self.pk} - {self.status}"