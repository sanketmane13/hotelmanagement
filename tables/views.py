from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models.deletion import ProtectedError

from .models import Table, Booking
from .serializers import (
    TableSerializer,
    TableStatusSerializer,
    BookingSerializer,
)

from staff.permissions import IsAdmin, IsCustomer

class TableListView(generics.ListAPIView):

    queryset = Table.objects.filter(is_active=True)

    serializer_class = TableSerializer

    permission_classes = [

        IsAuthenticated
        
    ]


class UpdateTableView(generics.UpdateAPIView):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


class CreateTableView(generics.CreateAPIView):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


class UpdateTableStatusView(generics.UpdateAPIView):
    queryset = Table.objects.all()
    serializer_class = TableStatusSerializer
    permission_classes = [IsAuthenticated, IsAdmin]


class DeleteTableView(generics.DestroyAPIView):
    queryset = Table.objects.all()
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def destroy(self, request, *args, **kwargs):
        table = self.get_object()
        try:
            table.delete()
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete a table that has bookings or orders."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


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
            status__in=[
                Booking.Status.PENDING_PAYMENT,
                Booking.Status.CONFIRMED,
            ],
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
        ).select_related("table").order_by("-created_at", "-pk")


class CancelBookingView(generics.GenericAPIView):

    serializer_class = BookingSerializer

    permission_classes = [
        IsAuthenticated,
        IsCustomer
    ]

    def get_queryset(self):

        return Booking.objects.filter(
            user=self.request.user
        )

    def patch(self, request, *args, **kwargs):
        booking = self.get_object()
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

        return Response(self.get_serializer(booking).data)

        