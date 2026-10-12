from django.urls import path

from .views import RegisterView, VerifyOTPView, CurrentUserView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
]