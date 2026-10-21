from datetime import date, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Booking, Table


class CancelBookingTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="customer",
			email="customer@example.com",
			phone="1234567890",
			password="test-password",
		)
		self.table = Table.objects.create(table_number=1, capacity=2)
		self.booking = Booking.objects.create(
			user=self.user,
			table=self.table,
			booking_date=date(2026, 10, 20),
			start_time=time(10, 0),
			end_time=time(11, 0),
		)
		self.client = APIClient()
		self.client.force_authenticate(user=self.user)

	def test_patch_without_body_cancels_booking(self):
		response = self.client.patch(
			reverse("cancel-booking", kwargs={"pk": self.booking.pk}),
			{},
			format="json",
		)

		self.booking.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.booking.status, Booking.Status.CANCELLED)

	def test_my_bookings_returns_newest_first(self):
		newer_booking = Booking.objects.create(
			user=self.user,
			table=self.table,
			booking_date=date(2026, 10, 21),
			start_time=time(12, 0),
			end_time=time(13, 0),
		)
		Booking.objects.filter(pk=self.booking.pk).update(
			created_at=timezone.now() - timedelta(days=1)
		)

		response = self.client.get(reverse("my-bookings"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(
			[booking["id"] for booking in response.data["results"]],
			[newer_booking.pk, self.booking.pk],
		)


class BookingFeeTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="booking-customer",
			email="booking-customer@example.com",
			phone="1234567891",
			password="test-password",
		)
		self.table = Table.objects.create(
			table_number=10,
			capacity=2,
			booking_price="125.50",
		)
		self.client = APIClient()
		self.client.force_authenticate(user=self.user)

	def test_booking_saves_fixed_fee_independent_of_table_price(self):
		response = self.client.post(
			reverse("create-booking"),
			{
				"table": self.table.pk,
				"booking_date": "2026-10-22",
				"start_time": "10:00:00",
				"end_time": "11:00:00",
				"booking_price": "0.01",
			},
			format="json",
		)

		self.assertEqual(response.status_code, 201)
		booking = Booking.objects.get(pk=response.data["id"])
		self.assertEqual(booking.booking_price, Decimal("200.00"))
		self.assertEqual(response.data["booking_price"], "200.00")
		self.assertEqual(booking.status, Booking.Status.PENDING_PAYMENT)

		self.table.booking_price = "200.00"
		self.table.save(update_fields=["booking_price"])
		booking.refresh_from_db()
		self.assertEqual(booking.booking_price, Decimal("200.00"))


class UpdateTableTests(TestCase):
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
		self.url = reverse("update-table", kwargs={"pk": self.table.pk})

	def test_admin_can_update_table(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.patch(
			self.url,
			{"capacity": 4, "location": "Window"},
			format="json",
		)

		self.table.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.table.capacity, 4)
		self.assertEqual(self.table.location, "Window")

	def test_customer_cannot_update_table(self):
		client = APIClient()
		client.force_authenticate(user=self.customer)

		response = client.patch(self.url, {"capacity": 4}, format="json")

		self.table.refresh_from_db()
		self.assertEqual(response.status_code, 403)
		self.assertEqual(self.table.capacity, 2)

	def test_admin_can_create_table(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.post(
			reverse("create-table"),
			{"table_number": 2, "capacity": 4, "location": "Window"},
			format="json",
		)

		self.assertEqual(response.status_code, 201)
		self.assertTrue(Table.objects.filter(table_number=2).exists())

	def test_admin_can_update_table_status(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.patch(
			reverse("update-table-status", kwargs={"pk": self.table.pk}),
			{"status": Table.Status.MAINTENANCE},
			format="json",
		)

		self.table.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.table.status, Table.Status.MAINTENANCE)

	def test_admin_can_delete_unreferenced_table(self):
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.delete(
			reverse("delete-table", kwargs={"pk": self.table.pk})
		)

		self.assertEqual(response.status_code, 204)
		self.assertFalse(Table.objects.filter(pk=self.table.pk).exists())

	def test_table_with_booking_cannot_be_deleted(self):
		Booking.objects.create(
			user=self.customer,
			table=self.table,
			booking_date=date(2026, 10, 20),
			start_time=time(10, 0),
			end_time=time(11, 0),
		)
		client = APIClient()
		client.force_authenticate(user=self.admin)

		response = client.delete(
			reverse("delete-table", kwargs={"pk": self.table.pk})
		)

		self.assertEqual(response.status_code, 409)
		self.assertTrue(Table.objects.filter(pk=self.table.pk).exists())

	def test_customer_cannot_create_delete_or_update_table_status(self):
		client = APIClient()
		client.force_authenticate(user=self.customer)

		create_response = client.post(
			reverse("create-table"),
			{"table_number": 2, "capacity": 4},
			format="json",
		)
		status_response = client.patch(
			reverse("update-table-status", kwargs={"pk": self.table.pk}),
			{"status": Table.Status.MAINTENANCE},
			format="json",
		)
		delete_response = client.delete(
			reverse("delete-table", kwargs={"pk": self.table.pk})
		)

		self.table.refresh_from_db()
		self.assertEqual(create_response.status_code, 403)
		self.assertEqual(status_response.status_code, 403)
		self.assertEqual(delete_response.status_code, 403)
		self.assertEqual(self.table.status, Table.Status.AVAILABLE)
		self.assertTrue(Table.objects.filter(pk=self.table.pk).exists())
