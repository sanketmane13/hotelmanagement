import secrets
from django.core.mail import send_mail

def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"

def send_otp_email(user, otp, purpose="EMAIL_VERIFICATION"):
    purpose_label = "login" if purpose == "LOGIN" else "email verification"
    subject = f"Hotel Management - {purpose_label.title()} OTP"

    message = f"""
        Hello {user.username},

        Your OTP for {purpose_label} is:

        {otp}

        This OTP is valid for 10 minutes.

        If you did not request this OTP, please ignore this email.

        Regards,
        Hotel Management Team
        """

    send_mail(
        subject,
        message,
        None,
        [user.email],
    )