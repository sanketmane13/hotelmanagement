from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from orders.models import Order
from payment.models import Payment
from tables.models import Booking, Table


class AdminDashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            phone="5550001111",
            password="test-password",
            role=user_model.Role.ADMIN,
        )
        self.customer = user_model.objects.create_user(
            username="dashboard-customer",
            email="dashboard-customer@example.com",
            phone="5550002222",
            password="test-password",
        )
        self.table = Table.objects.create(table_number=31, capacity=4)
        self.booking = Booking.objects.create(
            user=self.customer,
            table=self.table,
            booking_date=date.today(),
            start_time=time(18, 0),
            end_time=time(19, 0),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_dashboard_includes_payment_and_email_metrics(self):
        Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            status=Payment.PaymentStatus.SUCCESS,
            confirmation_email_sent=True,
        )
        order = Order.objects.create(
            customer=self.customer,
            table=self.table,
            booking=self.booking,
            total_amount=Decimal("75.50"),
        )
        Payment.objects.create(
            booking=self.booking,
            order=order,
            amount=Decimal("75.50"),
            status=Payment.PaymentStatus.SUCCESS,
        )
        Payment.objects.create(
            booking=self.booking,
            amount=Decimal("200.00"),
            status=Payment.PaymentStatus.PENDING,
        )

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 200)
        payments = response.data["payments"]
        self.assertEqual(payments["total"], 3)
        self.assertEqual(payments["by_status"]["SUCCESS"], 2)
        self.assertEqual(payments["by_status"]["PENDING"], 1)
        self.assertEqual(payments["successful"], 2)
        self.assertEqual(payments["confirmation_emails"], {
            "sent": 1,
            "pending": 1,
        })
        self.assertEqual(payments["amounts_by_currency"], [{
            "currency": "INR",
            "successful_total": Decimal("275.50"),
            "booking_fees": Decimal("200.00"),
            "food_orders": Decimal("75.50"),
            "successful_today": Decimal("275.50"),
        }])

    def test_dashboard_remains_admin_only(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 403)
