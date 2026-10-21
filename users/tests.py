from django.test import TestCase
from django.core import mail
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from staff.models import StaffProfile
from users.models import OTPVerification
from users.utils import send_otp_email

# Create your tests here.


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class OTPEmailTemplateTests(TestCase):
	def test_otp_email_includes_text_and_html_templates(self):
		user_model = get_user_model()
		user = user_model(username="customer", email="customer@example.com")

		send_otp_email(user, "012345")

		self.assertEqual(len(mail.outbox), 1)
		message = mail.outbox[0]
		self.assertEqual(message.subject, "Hotel Management - Email Verification OTP")
		self.assertEqual(message.to, ["customer@example.com"])
		self.assertIn("012345", message.body)
		self.assertIn("expires in 10 minutes", message.body)
		self.assertEqual(len(message.alternatives), 1)
		self.assertEqual(message.alternatives[0].mimetype, "text/html")
		self.assertIn("012345", message.alternatives[0].content)
		self.assertIn("email verification", message.alternatives[0].content)


class LoginOTPGenerationTests(TestCase):
	def setUp(self):
		user_model = get_user_model()
		self.user = user_model.objects.create_user(
			username="customer",
			email="customer@example.com",
			phone="2222222222",
			password="test-password",
			is_verified=True,
		)
		self.client = APIClient()

	@patch("users.views.send_otp_email")
	def test_verified_user_can_request_login_otp(self, send_otp_email):
		response = self.client.post(
			reverse("login-otp"),
			{
				"user_id": str(self.user.pk),
				"email": self.user.email,
				"password": "test-password",
			},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		otp_record = OTPVerification.objects.get(user=self.user)
		self.assertEqual(otp_record.purpose, OTPVerification.Purpose.LOGIN)
		self.assertFalse(otp_record.is_used)
		self.assertTrue(self.user.is_verified)
		send_otp_email.assert_called_once_with(
			self.user,
			otp_record.otp,
			purpose=OTPVerification.Purpose.LOGIN,
		)

	@patch("users.views.send_otp_email")
	def test_invalid_password_does_not_generate_or_send_login_otp(self, send_otp_email):
		response = self.client.post(
			reverse("login-otp"),
			{
				"user_id": str(self.user.pk),
				"email": self.user.email,
				"password": "incorrect-password",
			},
			format="json",
		)

		self.assertEqual(response.status_code, 401)
		self.assertFalse(OTPVerification.objects.exists())
		send_otp_email.assert_not_called()


class AdminStaffManagementTests(TestCase):
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
		self.staff = user_model.objects.create_user(
			username="chef",
			email="chef@example.com",
			phone="3333333333",
			password="test-password",
			role=user_model.Role.STAFF,
		)
		StaffProfile.objects.create(user=self.staff, role=StaffProfile.StaffRole.CHEF)
		self.client = APIClient()
		self.client.force_authenticate(user=self.admin)
		self.staff_url = reverse(
			"admin-manage-staff",
			kwargs={"pk": self.staff.pk},
		)

	def test_admin_can_create_staff(self):
		response = self.client.post(
			reverse("admin-create-staff"),
			{
				"username": "waiter",
				"email": "waiter@example.com",
				"phone": "4444444444",
				"password": "test-password",
				"role": StaffProfile.StaffRole.WAITER,
			},
			format="json",
		)

		self.assertEqual(response.status_code, 201)
		created_staff = get_user_model().objects.get(username="waiter")
		self.assertEqual(created_staff.role, get_user_model().Role.STAFF)
		self.assertEqual(created_staff.staff_profile.role, StaffProfile.StaffRole.WAITER)

	def test_admin_can_list_only_staff(self):
		response = self.client.get(reverse("admin-create-staff"))

		self.assertEqual(response.status_code, 200)
		staff_results = response.data["results"]
		self.assertEqual(len(staff_results), 1)
		self.assertEqual(staff_results[0]["id"], self.staff.pk)
		self.assertEqual(staff_results[0]["role"], StaffProfile.StaffRole.CHEF)

	def test_non_admin_cannot_list_staff(self):
		self.client.force_authenticate(user=self.customer)
		response = self.client.get(reverse("admin-create-staff"))

		self.assertEqual(response.status_code, 403)

	def test_admin_can_list_only_customers_with_pagination(self):
		response = self.client.get(reverse("admin-user-list"))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.data["count"], 1)
		user_ids = {user["id"] for user in response.data["results"]}
		self.assertEqual(user_ids, {self.customer.pk})

	def test_non_admin_cannot_list_or_update_users(self):
		self.client.force_authenticate(user=self.customer)
		list_response = self.client.get(reverse("admin-user-list"))
		update_response = self.client.patch(
			reverse("admin-manage-user", kwargs={"pk": self.staff.pk}),
			{"username": "unauthorized-change"},
			format="json",
		)

		self.assertEqual(list_response.status_code, 403)
		self.assertEqual(update_response.status_code, 403)

	def test_admin_can_put_and_patch_user(self):
		user_url = reverse("admin-manage-user", kwargs={"pk": self.customer.pk})
		patch_response = self.client.patch(
			user_url,
			{"username": "updated-customer"},
			format="json",
		)
		put_response = self.client.put(
			user_url,
			{
				"username": "replaced-customer",
				"email": "replaced@example.com",
				"phone": "5555555555",
			},
			format="json",
		)

		self.assertEqual(patch_response.status_code, 200)
		self.assertEqual(put_response.status_code, 200)
		self.customer.refresh_from_db()
		self.assertEqual(self.customer.username, "replaced-customer")
		self.assertEqual(self.customer.email, "replaced@example.com")
		self.assertEqual(self.customer.phone, "5555555555")

	def test_admin_can_delete_user(self):
		response = self.client.delete(
			reverse("admin-manage-user", kwargs={"pk": self.customer.pk})
		)

		self.assertEqual(response.status_code, 204)
		self.assertFalse(get_user_model().objects.filter(pk=self.customer.pk).exists())

	def test_admin_can_update_staff(self):
		response = self.client.patch(
			self.staff_url,
			{"username": "head-chef", "role": StaffProfile.StaffRole.HELPER},
			format="json",
		)

		self.staff.refresh_from_db()
		self.assertEqual(response.status_code, 200)
		self.assertEqual(self.staff.username, "head-chef")
		self.assertEqual(self.staff.staff_profile.role, StaffProfile.StaffRole.HELPER)

	def test_admin_can_delete_staff(self):
		response = self.client.delete(self.staff_url)

		self.assertEqual(response.status_code, 204)
		self.assertFalse(get_user_model().objects.filter(pk=self.staff.pk).exists())

	def test_non_admin_cannot_manage_staff(self):
		self.client.force_authenticate(user=self.customer)
		response = self.client.patch(
			self.staff_url,
			{"role": StaffProfile.StaffRole.HELPER},
			format="json",
		)

		self.assertEqual(response.status_code, 403)
