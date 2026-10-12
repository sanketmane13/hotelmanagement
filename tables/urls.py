from django.urls import path

from .views import (
    TableListView,
    UpdateTableView,
    CreateTableView,
    UpdateTableStatusView,
    DeleteTableView,
    AvailableTableListView,
    CreateBookingView,
    MyBookingsView,
    CancelBookingView,
)


urlpatterns = [
    path("", TableListView.as_view(), name="table-list"),

    path("<int:pk>/", UpdateTableView.as_view(), name="update-table"),

    path("create/", CreateTableView.as_view(), name="create-table"),

    path("<int:pk>/status/", UpdateTableStatusView.as_view(), name="update-table-status"),

    path("<int:pk>/delete/", DeleteTableView.as_view(), name="delete-table"),

    path("available/", AvailableTableListView.as_view(), name="available-tables"),

    path("book/", CreateBookingView.as_view(),name="create-booking"),

    path("my-bookings/", MyBookingsView.as_view(), name="my-bookings"),

    path("booking/<int:pk>/cancel/",CancelBookingView.as_view(),name="cancel-booking"),
]