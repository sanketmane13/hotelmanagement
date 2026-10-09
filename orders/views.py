
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from staff.permissions import IsChef, IsWaiter, IsCustomer
from .models import Order
from .serializers import CreateOrderSerializer, OrderSerializer
from django.db import transaction
from django.shortcuts import get_object_or_404
from staff.models import StaffProfile
from rest_framework.filters import SearchFilter, OrderingFilter

from .filters import filter_orders
from .pagination import OrderPagination


class CreateOrderView(generics.CreateAPIView):

    serializer_class = CreateOrderSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]


class MyOrdersView(generics.ListAPIView):

    serializer_class = OrderSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    filter_backends = [SearchFilter, OrderingFilter]
    pagination_class = OrderPagination

    search_fields = [
        "customer__username",
        "items__menu_item__name",
    ]

    ordering_fields = ["created_at", "total_amount", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = (
            Order.objects
            .filter(customer=self.request.user)
            .prefetch_related("items__menu_item")
            .select_related("customer", "table")
            .order_by("-created_at")
            .distinct()
        )

        return filter_orders(queryset, self.request.query_params)

class ChefOrdersView(generics.ListAPIView):

    serializer_class = OrderSerializer

    permission_classes = [
        IsAuthenticated,
        IsChef
    ]

    filter_backends = [SearchFilter, OrderingFilter]
    pagination_class = OrderPagination

    search_fields = [
        "customer__username",
        "items__menu_item__name",
    ]

    ordering_fields = ["created_at", "total_amount", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset= (
            Order.objects
            .filter(
                status__in=[
                    Order.Status.PENDING,
                    Order.Status.PREPARING,
                    Order.Status.READY,
                ]
            )
            .select_related("customer", "table")
            .prefetch_related("items__menu_item")
            .order_by("created_at")
            .distinct()
        )

        return filter_orders(queryset, self.request.query_params)

class WaiterOrdersView(generics.ListAPIView):

    serializer_class = OrderSerializer

    permission_classes = [
        IsAuthenticated,
        IsWaiter
    ]

    filter_backends = [SearchFilter, OrderingFilter]
    pagination_class = OrderPagination

    search_fields = [
        "customer__username",
        "items__menu_item__name",
    ]

    ordering_fields = ["created_at", "total_amount", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset= (
            Order.objects
            .filter(status=Order.Status.READY)
            .select_related("customer", "table")
            .prefetch_related("items__menu_item")
            .order_by("created_at")
            .distinct()
        )
        return filter_orders(queryset, self.request.query_params)

class UpdateOrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=pk,
        )

        user = request.user
        current_status = order.status

        # Only admins, chefs, and waiters may update order status.
        if user.role == user.Role.ADMIN:
            allowed_transitions = {
                Order.Status.PENDING: [
                    Order.Status.PREPARING,
                    Order.Status.CANCELLED,
                ],
                Order.Status.PREPARING: [
                    Order.Status.READY,
                    Order.Status.CANCELLED,
                ],
                Order.Status.READY: [
                    Order.Status.SERVED,
                    Order.Status.CANCELLED,
                ],
            }

        elif (
            user.role == user.Role.STAFF
            and hasattr(user, "staff_profile")
            and user.staff_profile.role == StaffProfile.StaffRole.CHEF
        ):
            allowed_transitions = {
                Order.Status.PENDING: [Order.Status.PREPARING],
                Order.Status.PREPARING: [Order.Status.READY],
            }

        elif (
            user.role == user.Role.STAFF
            and hasattr(user, "staff_profile")
            and user.staff_profile.role == StaffProfile.StaffRole.WAITER
        ):
            allowed_transitions = {
                Order.Status.READY: [Order.Status.SERVED],
            }

        else:
            return Response(
                {"detail": "You cannot update order status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get("status")

        if new_status not in allowed_transitions.get(current_status, []):
            return Response(
                {
                    "detail": (
                        f"Transition from {current_status} "
                        f"to {new_status} is not allowed."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_200_OK,
        )
class CancelMyOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk):
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=pk,
            customer=request.user,
        )

        if order.status != Order.Status.PENDING:
            return Response(
                {
                    "detail": (
                        "You can only cancel an order "
                        "that is pending."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])

        return Response(
            OrderSerializer(order).data,
            status=status.HTTP_200_OK,
        )
