from django.urls import path

from .views import (
    CreateOrderView,
    MyOrdersView,
    AdminOrdersView,
    ChefOrdersView,
    WaiterOrdersView,
    UpdateOrderStatusView,
    UpdateOrderPaymentStatusView,
    CancelMyOrderView,
)

urlpatterns = [
    path("", CreateOrderView.as_view(), name="create-order"),
    path("my-orders/", MyOrdersView.as_view(), name="my-orders"),
    path("admin/", AdminOrdersView.as_view(), name="admin-orders"),
    path("chef/", ChefOrdersView.as_view(), name="chef-orders"),
    path("waiter/", WaiterOrdersView.as_view(), name="waiter-orders"),
    path( "<int:pk>/status/", UpdateOrderStatusView.as_view(), name="update-order-status"),
    path("<int:pk>/payment-status/", UpdateOrderPaymentStatusView.as_view(), name="update-order-payment-status"),
    path("<int:pk>/cancel/", CancelMyOrderView.as_view(),name="cancel-my-order",),
]