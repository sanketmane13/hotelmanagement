
from django.conf import settings
from django.db import models
from django.db.models import Q

from menu.models import MenuItem
from tables.models import Table


class Order(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PREPARING = "PREPARING", "Preparing"
        READY = "READY", "Ready"
        SERVED = "SERVED", "Served"
        CANCELLED = "CANCELLED", "Cancelled"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders"
    )

    table = models.ForeignKey(
        Table,
        on_delete=models.PROTECT,
        related_name="orders"
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    booking = models.ForeignKey(
        "tables.Booking",
        on_delete=models.PROTECT,
        related_name="orders",
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.pk} - {self.status}"


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.PROTECT,
        related_name="order_items"
    )

    quantity = models.PositiveIntegerField()

    # Snapshot of the dish price when the order was placed.
    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1),
                name="order_item_quantity_at_least_one"
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gte=0),
                name="order_item_price_nonnegative"
            ),
            models.UniqueConstraint(
                fields=["order", "menu_item"],
                name="unique_menu_item_per_order"
            ),
        ]

    @property
    def subtotal(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity}"