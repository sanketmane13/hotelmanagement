
from rest_framework.exceptions import ValidationError

from .models import Order


def filter_orders(queryset, params):
    order_status = params.get("status")
    created_date = params.get("created_date")

    if order_status:
        valid_statuses = [
            value for value, label in Order.Status.choices
        ]

        if order_status not in valid_statuses:
            raise ValidationError({
                "status": "Invalid order status."
            })

        queryset = queryset.filter(status=order_status)

    if created_date:
        from datetime import date

        try:
            date.fromisoformat(created_date)
        except ValueError:
            raise ValidationError({
                "created_date": "Use YYYY-MM-DD format."
            })

        queryset = queryset.filter(
            created_at__date=created_date
        )

    return queryset
