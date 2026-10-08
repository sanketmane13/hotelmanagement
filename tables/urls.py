from django.urls import path

from .views import (TableListView, AvailableTableListView, CreateBookingView, MyBookingsView, CancelBookingView,)


urlpatterns = [
    path("", TableListView.as_view(), name="table-list"),

    path("available/", AvailableTableListView.as_view(), name="available-tables"),

    path("book/", CreateBookingView.as_view(),name="create-booking"),

    path("my-bookings/", MyBookingsView.as_view(), name="my-bookings"),

    path("booking/<int:pk>/cancel/",CancelBookingView.as_view(),name="cancel-booking"),
]