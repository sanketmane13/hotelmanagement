from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields =[
            "id",
            "username",
            "email",
            "phone",
            "role",
            "is_verified",
            "created_at",
        ]

        read_only_fields = [
            "id",
            "role",
            "is_verified",
            "created_at",
        ]        

class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    class Meta:
        model = User

        fields = [
            "username",
            "email",
            "phone",
            "password",
        ]

    def create(self, validated_data):

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            phone=validated_data["phone"],
            password=validated_data["password"],
        )

        return user
    
    def create(self, validated_data):

        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            phone=validated_data["phone"],
            password=validated_data["password"],
        )

        return user

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    otp = serializers.CharField(
        min_length = 6,
        max_length = 6
    )


class CurrentUserSerializer(serializers.ModelSerializer):
    staff_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone",
            "role",
            "is_verified",
            "staff_role",
        ]

    def get_staff_role(self, obj):
        if obj.role != User.Role.STAFF:
            return None

        try:
            return obj.staff_profile.role
        except User.staff_profile.RelatedObjectDoesNotExist:
            return None