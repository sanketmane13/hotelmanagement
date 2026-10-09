from django.db import models

# Create your models here.

from django.db import models


class Category(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    description = models.TextField(
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.name


class MenuItem(models.Model):

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="menu_items"
    )

    name = models.CharField(
        max_length=150
    )

    description = models.TextField(
        blank=True
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    is_available = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_menu_item_per_category"
            ),
            models.CheckConstraint(
                condition=models.Q(price__gte=0),
                name="menu_item_price_nonnegative"
            ),
        ]

    def __str__(self):
        return self.name