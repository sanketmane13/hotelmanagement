from django.shortcuts import render

# Create your views here.
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from staff.permissions import IsAdmin
from .models import Category, MenuItem
from .serializers import (
    CategorySerializer,
    MenuItemSerializer,
)

class CategoryViewSet(viewsets.ModelViewSet):

    serializer_class = CategorySerializer

    def get_queryset(self):
        if self.request.user.role == "ADMIN":
            return Category.objects.all()

        return Category.objects.filter(
            is_active=True
        )

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated, IsAdmin]
        else:
            permission_classes = [IsAuthenticated]

        return [
            permission()
            for permission in permission_classes
        ]

class MenuItemViewSet(viewsets.ModelViewSet):

    serializer_class = MenuItemSerializer

    def get_queryset(self):
        queryset = MenuItem.objects.select_related(
            "category"
        )

        if self.request.user.role == "ADMIN":
            return queryset

        return queryset.filter(
            is_available=True,
            category__is_active=True
        )

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            permission_classes = [IsAuthenticated, IsAdmin]
        else:
            permission_classes = [IsAuthenticated]

        return [
            permission()
            for permission in permission_classes
        ]

