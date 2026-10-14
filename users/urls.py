from django.urls import path

from .views import (
    RegisterView,
    VerifyOTPView,
    CurrentUserView,
    AdminUserListView,
    AdminUserDetailView,
    AdminStaffCreateView,
    AdminStaffDetailView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("", AdminUserListView.as_view(), name="admin-user-list"),
    path("<int:pk>/", AdminUserDetailView.as_view(), name="admin-manage-user"),
    path("staff/", AdminStaffCreateView.as_view(), name="admin-create-staff"),
    path("staff/<int:pk>/", AdminStaffDetailView.as_view(), name="admin-manage-staff"),
]