from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings


class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        STAFF = "STAFF", "Staff"
        CUSTOMER = "CUSTOMER", "Customer"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True)

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER
    )

    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.username} - {self.role}"


class OTPVerification(models.Model):

    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = "EMAIL_VERIFICATION", "Email Verification"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="otp_verifications"
    )

    otp = models.CharField(max_length=6)

    purpose = models.CharField(
        max_length=30,
        choices=Purpose.choices,
        default=Purpose.EMAIL_VERIFICATION
    )

    expires_at = models.DateTimeField()

    is_used = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.purpose}"