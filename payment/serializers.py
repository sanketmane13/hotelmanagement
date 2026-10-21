from rest_framework import serializers

from orders.serializers import OrderItemInputSerializer

from .models import Payment


class CreateCheckoutSessionSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1)
    items = OrderItemInputSerializer(many=True, required=False)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError(
                "A cart checkout must contain at least one item."
            )
        return items


class ReconcileCheckoutSessionSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=255)


class ReconcileCheckoutSessionResponseSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=Payment.PaymentStatus.choices)
    booking_status = serializers.CharField()
    order_id = serializers.IntegerField(allow_null=True)


class CheckoutSessionResponseSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    order_id = serializers.IntegerField(required=False)
    session_id = serializers.CharField()
    checkout_url = serializers.URLField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class PaymentStatusSerializer(serializers.ModelSerializer):
    booking_id = serializers.IntegerField(read_only=True)
    order_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "booking_id",
            "order_id",
            "amount",
            "currency",
            "status",
            "stripe_checkout_session_id",
            "stripe_checkout_session_expires_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RefundSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField(min_value=1)


class RefundResponseSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    payment_status = serializers.ChoiceField(choices=Payment.PaymentStatus.choices)
    refund_status = serializers.CharField()