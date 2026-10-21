from django.contrib import admin

from .models import Booking, Table


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("table_number", "capacity", "booking_price", "status", "is_active")
    list_editable = ("booking_price", "status", "is_active")
    search_fields = ("table_number",)


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "table", "booking_date", "status")
    list_filter = ("status", "booking_date")
    search_fields = ("user__username", "user__email")
