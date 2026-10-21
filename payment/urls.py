from django.urls import path

from .views import (
    CreateCheckoutSessionView,
    PaymentStatusView,
    ReconcileCheckoutSessionView,
    RefundView,
    stripe_webhook,
)

urlpatterns = [
    path("create-checkout-session/", CreateCheckoutSessionView.as_view(), name="create-checkout-session",),
    path("status/<int:payment_id>/", PaymentStatusView.as_view(), name="payment-status",),
    path(
        "reconcile-checkout-session/",
        ReconcileCheckoutSessionView.as_view(),
        name="reconcile-checkout-session",
    ),
    path("webhook/", stripe_webhook, name="stripe-webhook"),
    path("refund/", RefundView.as_view(), name="refund-payment"),
]