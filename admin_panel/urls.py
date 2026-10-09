from django.urls import path

from .dashboard_views import AdminDashboardView

urlpatterns = [
    path(
        "dashboard/",
        AdminDashboardView.as_view(),
        name="admin-dashboard",
    ),
]
