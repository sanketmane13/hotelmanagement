from decimal import Decimal

from django.db import models
from django.conf import settings
# Create your models here.

BOOKING_FEE = Decimal("200.00")

class Table(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        MAINTENANCE = "MAINTENANCE", "Maintenance"

    table_number = models.PositiveIntegerField(unique=True)
    capacity = models.PositiveIntegerField()
    booking_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
    )
    location = models.CharField(max_length=100,blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(booking_price__gte=0),
                name="table_booking_price_nonnegative",
            ),
        ]

    def __str__(self):
        return f"Table {self.table_number}"

class Booking(models.Model):

    class Status(models.TextChoices):
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pending payment"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookings")
    table = models.ForeignKey(Table, on_delete=models.PROTECT, related_name="bookings")
    booking_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=BOOKING_FEE,
    )
    booking_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.booking_price = BOOKING_FEE
        super().save(*args, **kwargs)

    def __str__(self):
        return (f"Table {self.table.table_number} - "f"{self.booking_date}")

    
