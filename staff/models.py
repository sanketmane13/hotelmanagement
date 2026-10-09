from django.db import models

from django.conf import settings
from django.db import models

class StaffProfile(models.Model):

    class StaffRole(models.TextChoices):
        CHEF = "CHEF", "Chef"
        WAITER = "WAITER", "Waiter"
        HELPER = "HELPER", "Helper"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_profile"
    )

    role = models.CharField(
        max_length=20,
        choices=StaffRole.choices
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
    

