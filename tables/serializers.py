from rest_framework import serializers
from django.db.models import Q
from .models import Table, Booking

class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table

        fields = [
            "id",
            "table_number",
            "capacity",
            "location",
            "status",
            "is_active",
        ]

        read_only_fields = [
            "id",
        ]


class BookingSerializer(serializers.ModelSerializer):

    table_number = serializers.IntegerField(
        source="table.table_number",
        read_only=True
    )

    class Meta:
        model = Booking

        fields = [
            "id",
            "table",
            "table_number",
            "booking_date",
            "start_time",
            "end_time",
            "status",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "status",
            "created_at",
        ]

    def validate(self, attrs):

        table = attrs["table"]
        booking_date = attrs["booking_date"]
        start_time = attrs["start_time"]
        end_time = attrs["end_time"]

        if start_time >= end_time:
            raise serializers.ValidationError(
                "End time must be after start time."
            )

        if not table.is_active:
            raise serializers.ValidationError(
                "This table is not currently available."
            )

        if table.status != Table.Status.AVAILABLE:
            raise serializers.ValidationError(
                "This table is not available."
            )

        overlapping_booking = Booking.objects.filter(
            table=table,
            booking_date=booking_date,
            status=Booking.Status.CONFIRMED,
            start_time__lt=end_time,
            end_time__gt=start_time,
        ).exists()

        if overlapping_booking:
            raise serializers.ValidationError(
                "This table is already booked for the selected time."
            )

        return attrs