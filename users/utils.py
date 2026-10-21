import secrets

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"

def send_otp_email(user, otp, purpose="EMAIL_VERIFICATION"):
    purpose_label = "login" if purpose == "LOGIN" else "email verification"
    subject = f"Hotel Management - {purpose_label.title()} OTP"
    context = {
        "username": user.username,
        "otp": otp,
        "purpose_label": purpose_label,
        "purpose_title": purpose_label.title(),
    }
    text_message = render_to_string(
        "users/emails/otp_email.txt",
        context,
    )
    html_message = render_to_string(
        "users/emails/otp_email.html",
        context,
    )

    email = EmailMultiAlternatives(
        subject,
        text_message,
        None,
        [user.email],
    )
    email.attach_alternative(html_message, "text/html")
    email.send()