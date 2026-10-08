from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Table, Booking
from .serializers import TableSerializer, BookingSerializer

from staff.permissions import IsAdmin, IsCustomer
# Create your views here.

class TableListView(generics.ListAPIView):

    queryset = Table.objects.filter(
        is_active=True
    )

    serializer_class = TableSerializer

    permission_classes = [
        IsAuthenticated
    ]


class AvailableTableListView(generics.ListAPIView):

    serializer_class = TableSerializer

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        queryset = Table.objects.filter(is_active=True, status=Table.Status.AVAILABLE)

        booking_date = self.request.query_params.get("date")

        start_time = self.request.query_params.get("start_time")

        end_time = self.request.query_params.get("end_time")

        if not all([ booking_date, start_time, end_time]):
            return queryset

        booked_table_ids = Booking.objects.filter(
            booking_date=booking_date,
            status=Booking.Status.CONFIRMED,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).values_list("table_id",flat=True)

        return queryset.exclude(
            id__in=booked_table_ids
        )
    
class CreateBookingView(generics.CreateAPIView):

    serializer_class = BookingSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    def perform_create(self, serializer):

        serializer.save(user=self.request.user)

class MyBookingsView(generics.ListAPIView):

    serializer_class = BookingSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    def get_queryset(self):

        return Booking.objects.filter(
            user=self.request.user
        ).select_related("table")


class CancelBookingView(generics.UpdateAPIView):

    serializer_class = BookingSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    def get_queryset(self):

        return Booking.objects.filter(
            user=self.request.user
        )

    def perform_update(self, serializer):

        serializer.save(
            status=Booking.Status.CANCELLED
        )

        