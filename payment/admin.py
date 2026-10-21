from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    search_fields = (
        "stripe_payment_intent_id",
        "stripe_checkout_session_id",
        "booking__user__email",
    )
    readonly_fields = (
        "booking",
        "amount",
        "currency",
        "stripe_payment_intent_id",
        "stripe_checkout_session_id",
        "status",
        "created_at",
        "updated_at",
    )
