from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction

from staff.models import StaffProfile

User = get_user_model()


class StaffManagementSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=15)
    password = serializers.CharField( write_only=True, min_length=8, required=False,)
    role = serializers.ChoiceField(choices=StaffProfile.StaffRole.choices)

    def validate(self, attrs):
        if self.instance is None and "password" not in attrs:
            raise serializers.ValidationError({"password": "This field is required."})

        for field in ("username", "email", "phone"):
            value = attrs.get(field)
            if value is None:
                continue

            users = User.objects.filter(**{field: value})
            if self.instance is not None:
                users = users.exclude(pk=self.instance.pk)
            if users.exists():
                raise serializers.ValidationError(
                    {field: f"A user with this {field} already exists."}
                )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        staff_role = validated_data.pop("role")
        password = validated_data.pop("password")
        user = User.objects.create_user(
            **validated_data,
            password=password,
            role=User.Role.STAFF,
            is_verified=True,
        )
        StaffProfile.objects.create(user=user, role=staff_role)
        return user

    @transaction.atomic
    def update(self, instance, validated_data):
        staff_role = validated_data.pop("role", None)
        password = validated_data.pop("password", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()

        if staff_role is not None:
            instance.staff_profile.role = staff_role
            instance.staff_profile.save(update_fields=["role", "updated_at"])

        return instance

    def to_representation(self, instance):
        return {
            "id": instance.pk,
            "username": instance.username,
            "email": instance.email,
            "phone": instance.phone,
            "role": instance.staff_profile.role,
        }

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