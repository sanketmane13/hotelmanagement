from rest_framework import serializers

from .models import Category, MenuItem

class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category

        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class MenuItemSerializer(serializers.ModelSerializer):

    category_name = serializers.CharField(
        source="category.name",
        read_only=True
    )

    class Meta:
        model = MenuItem

        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "description",
            "price",
            "is_available",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_category(self, value):
        if not value.is_active:
            raise serializers.ValidationError(
                "Cannot assign a menu item to an inactive category."
            )

        return value

