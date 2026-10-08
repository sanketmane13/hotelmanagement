from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import StaffProfile

User = get_user_model()

class StaffProfileSerializer(serializers.ModelSerializer):

    username = serializers.CharField(source="user.username", read_only=True )

    email = serializers.EmailField( source="user.email", read_only=True )

    class Meta:
        model = StaffProfile

        fields = [
            "id",
            "username",
            "email",
            "role",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "username",
            "email",
            "created_at",
        ]


class CreateStaffSerializer(serializers.Serializer):

    username = serializers.CharField(max_length=150)

    email = serializers.EmailField()

    phone = serializers.CharField(max_length=15)

    password = serializers.CharField(write_only=True, min_length=8 )

    role = serializers.ChoiceField(  choices=StaffProfile.StaffRole.choices )

    def validate_username(self, value):

        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Username already exists."
            )

        return value

    def validate_email(self, value):

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Email already exists."
            )

        return value

    def validate_phone(self, value):

        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Phone number already exists."
            )

        return value

    def create(self, validated_data):

        role = validated_data.pop("role")

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            phone=validated_data["phone"],
            password=validated_data["password"],
            role=User.Role.STAFF,
            is_verified=True
        )

        StaffProfile.objects.create(
            user=user,
            role=role
        )

        return user