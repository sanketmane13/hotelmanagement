from django.urls import path

from .views import (CreateOrderView,MyOrdersView,ChefOrdersView,WaiterOrdersView,UpdateOrderStatusView,CancelMyOrderView)

urlpatterns = [
    path("", CreateOrderView.as_view(), name="create-order"),
    path("my-orders/", MyOrdersView.as_view(), name="my-orders"),
    path("chef/", ChefOrdersView.as_view(), name="chef-orders"),
    path("waiter/", WaiterOrdersView.as_view(), name="waiter-orders"),
    path( "<int:pk>/status/", UpdateOrderStatusView.as_view(), name="update-order-status"),
    path("<int:pk>/cancel/", CancelMyOrderView.as_view(),name="cancel-my-order",),
]