from decimal import Decimal

from django.db import transaction
from rest_framework import serializers

from menu.models import MenuItem
from tables.models import Table
from .models import Order, OrderItem
from django.utils import timezone
from tables.models import Booking, Table


class OrderItemInputSerializer(serializers.Serializer):

    menu_item = serializers.PrimaryKeyRelatedField(
        queryset=MenuItem.objects.filter(
            is_available=True,
            category__is_active=True
        )
    )

    quantity = serializers.IntegerField(min_value=1)


class CreateOrderSerializer(serializers.ModelSerializer):
    booking = serializers.PrimaryKeyRelatedField(
        queryset=Booking.objects.filter(
            status=Booking.Status.CONFIRMED
        )
    )
    items = OrderItemInputSerializer(many=True)

    class Meta:
        model = Order
        fields = ["booking", "items"]

    def validate_booking(self, booking):
        user = self.context["request"].user

        if booking.user_id != user.id:
            raise serializers.ValidationError(
                "You can only order using your own booking."
            )

        if booking.booking_date != timezone.localdate():
            raise serializers.ValidationError(
                "Orders can only be placed for today's booking."
            )

        table = booking.table

        if not table.is_active:
            raise serializers.ValidationError(
                "This table is inactive."
            )

        if table.status != Table.Status.AVAILABLE:
            raise serializers.ValidationError(
                "This table is not available for ordering."
            )

        return booking

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError(
                "An order must contain at least one item."
            )

        item_ids = [item["menu_item"].pk for item in items]

        if len(item_ids) != len(set(item_ids)):
            raise serializers.ValidationError(
                "Add each menu item once and increase its quantity."
            )

        return items

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items")
        booking = validated_data.pop("booking")
        total = Decimal("0.00")

        order = Order.objects.create(
            customer=self.context["request"].user,
            booking=booking,
            table=booking.table,
            total_amount=Decimal("0.00"),
        )

        for item_data in items_data:
            menu_item = item_data["menu_item"]
            quantity = item_data["quantity"]
            unit_price = menu_item.price

            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=quantity,
                unit_price=unit_price,
            )

            total += unit_price * quantity

        order.total_amount = total
        order.save(update_fields=["total_amount", "updated_at"])

        return order


class OrderItemSerializer(serializers.ModelSerializer):

    menu_item_name = serializers.CharField(
        source="menu_item.name",
        read_only=True
    )

    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "menu_item",
            "menu_item_name",
            "quantity",
            "unit_price",
            "subtotal",
        ]


class OrderSerializer(serializers.ModelSerializer):

    customer_username = serializers.CharField(
        source="customer.username",
        read_only=True
    )

    table_number = serializers.IntegerField(
        source="table.table_number",
        read_only=True
    )

    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_username",
            "table",
            "table_number",
            "items",
            "status",
            "total_amount",
            "created_at",
            "updated_at",
        ]

