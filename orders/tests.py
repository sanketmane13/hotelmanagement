from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta

from tables.models import Table
from .models import Order
from .serializers import OrderSerializer


class AdminOrderListTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.admin = user_model.objects.create_user(
			username="admin",
			email="admin@example.com",
			phone="1111111111",
			password="test-password",
			role=user_model.Role.ADMIN,
		)
		self.customer = user_model.objects.create_user(
			username="customer",
			email="customer@example.com",
			phone="2222222222",
			password="test-password",
			role=user_model.Role.CUSTOMER,
		)
		table = Table.objects.create(table_number=1, capacity=2)
		self.older_order = Order.objects.create(
			customer=self.customer,
			table=table,
		)
		self.newer_order = Order.objects.create(
			customer=self.customer,
			table=table,
		)
		Order.objects.filter(pk=self.older_order.pk).update(
			created_at=timezone.now() - timedelta(days=1),
		)
		self.url = reverse("admin-orders")

	def test_admin_gets_all_orders_newest_first_with_required_fields(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.get(self.url)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			[order["id"] for order in response.data["results"]],
			[self.newer_order.pk, self.older_order.pk],
		)
		self.assertEqual(response.data["results"][0]["customer_username"], "customer")
		self.assertIn("created_at", response.data["results"][0])
		self.assertIn("payment_status", response.data["results"][0])

	def test_customer_cannot_get_all_orders(self):
		client = APIClient()
		client.force_authenticate(user=self.customer)

		response = client.get(self.url)

		self.assertEqual(response.status_code, 403)


class UpdateOrderPaymentStatusTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.admin = user_model.objects.create_user(
			username="admin",
			email="admin@example.com",
			phone="1111111111",
			password="test-password",
			role=user_model.Role.ADMIN,
		)
		self.customer = user_model.objects.create_user(
			username="customer",
			email="customer@example.com",
			phone="2222222222",
			password="test-password",
			role=user_model.Role.CUSTOMER,
		)
		self.table = Table.objects.create(table_number=1, capacity=2)
		self.order = Order.objects.create(
			customer=self.customer,
			table=self.table,
		)
		self.url = reverse(
			"update-order-payment-status",
			kwargs={"pk": self.order.pk},
		)

	def test_admin_can_update_payment_status(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.patch(
			self.url,
			{"payment_status": Order.PaymentStatus.PAID},
			format="json",
		)

		self.order.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)
		self.assertEqual(
			OrderSerializer(self.order).data["payment_status"],
			Order.PaymentStatus.PAID,
		)

	def test_customer_cannot_update_payment_status(self):
		client = APIClient()
		client.force_authenticate(user=self.customer)

		response = client.patch(
			self.url,
			{"payment_status": Order.PaymentStatus.PAID},
			format="json",
		)

		self.order.refresh_from_db()
		self.assertEqual(response.status_code, 403)
		self.assertEqual(
			self.order.payment_status,
			Order.PaymentStatus.PENDING,
		)

	def test_invalid_payment_status_is_rejected(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.patch(
			self.url,
			{"payment_status": "UNKNOWN"},
			format="json",
		)

		self.assertEqual(response.status_code, 400)
