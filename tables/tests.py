from datetime import date, time, timedelta

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
