from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_otpverification"),
    ]

    operations = [
        migrations.AlterField(
            model_name="otpverification",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("EMAIL_VERIFICATION", "Email Verification"),
                    ("LOGIN", "Login"),
                ],
                default="EMAIL_VERIFICATION",
                max_length=30,
            ),
        ),
    ]