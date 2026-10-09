
from django.db.models import Count, Sum
from django.utils import timezone

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from staff.permissions import IsAdmin
from users.models import User
from staff.models import StaffProfile
from tables.models import Table
from menu.models import Category, MenuItem
from orders.models import Order, OrderItem


class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        today = timezone.localdate()

        # Order statistics
        total_orders = Order.objects.count()
        today_orders = Order.objects.filter(
            created_at__date=today
        ).count()

        order_status_counts = {
            status_value: Order.objects.filter(
                status=status_value
            ).count()
            for status_value, _ in Order.Status.choices
        }

        # Revenue: only completed service (SERVED) orders
        total_revenue = (
            Order.objects
            .filter(status=Order.Status.SERVED)
            .aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        today_revenue = (
            Order.objects
            .filter(
                status=Order.Status.SERVED,
                created_at__date=today,
            )
            .aggregate(total=Sum("total_amount"))["total"]
            or 0
        )

        # User statistics
        total_users = User.objects.count()
        total_customers = User.objects.filter(
            role=User.Role.CUSTOMER
        ).count()
        total_staff = StaffProfile.objects.count()
        total_admins = User.objects.filter(
            role=User.Role.ADMIN
        ).count()

        # Table and menu statistics
        total_tables = Table.objects.count()
        active_tables = Table.objects.filter(
            is_active=True
        ).count()
        available_tables = Table.objects.filter(
            is_active=True,
            status=Table.Status.AVAILABLE,
        ).count()

        total_categories = Category.objects.count()
        total_menu_items = MenuItem.objects.count()
        available_menu_items = MenuItem.objects.filter(
            is_available=True,
            category__is_active=True,
        ).count()

        # Top five menu items by quantity in served orders
        popular_items = (
            OrderItem.objects
            .filter(order__status=Order.Status.SERVED)
            .values("menu_item_id", "menu_item__name")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-total_quantity")[:5]
        )

        popular_items_data = [
            {
                "menu_item_id": item["menu_item_id"],
                "name": item["menu_item__name"],
                "quantity_sold": item["total_quantity"],
            }
            for item in popular_items
        ]

        return Response({
            "date": today,
            "orders": {
                "total": total_orders,
                "today": today_orders,
                "by_status": order_status_counts,
            },
            "revenue": {
                "total_served_orders": total_revenue,
                "today_served_orders": today_revenue,
            },
            "users": {
                "total": total_users,
                "customers": total_customers,
                "staff": total_staff,
                "admins": total_admins,
            },
            "tables": {
                "total": total_tables,
                "active": active_tables,
                "available": available_tables,
            },
            "menu": {
                "categories": total_categories,
                "items": total_menu_items,
                "available_items": available_menu_items,
            },
            "popular_items": popular_items_data,
        })
