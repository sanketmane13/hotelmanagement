
from datetime import timedelta

from django.db.models.deletion import ProtectedError
from django.utils import timezone

from django.shortcuts import render
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny
from .serializers import RegisterSerializer, VerifyOTPSerializer

from rest_framework.response import Response
from rest_framework import status
from .models import OTPVerification
from .utils import generate_otp, send_otp_email
from django.contrib.auth import get_user_model
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from .serializers import CurrentUserSerializer, UserSerializer
from .serializers import StaffManagementSerializer
from staff.permissions import IsAdmin

User = get_user_model()



class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):

        serializer = self.get_serializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        user = serializer.save()

        otp = generate_otp()

        OTPVerification.objects.create(
            user=user,
            otp=otp,
            expires_at=timezone.now() + timedelta(minutes=10)
        )
        send_otp_email(user, otp)

        return Response(
            {
                "message": "Registration successful. OTP sent to your email.",
                "email": user.email
            },
            status=status.HTTP_201_CREATED
        )

class LoginOTPView(generics.GenericAPIView):
    class RequestSerializer(serializers.Serializer):
        user_id = serializers.CharField()
        email = serializers.EmailField()
        password = serializers.CharField(write_only=True, trim_whitespace=False)

    serializer_class = RequestSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(email=email, username=user_id).first()
        if user is None and user_id.isdecimal():
            user = User.objects.filter(email=email, pk=user_id).first()

        if user is None or not user.check_password(password):
            return Response(
                {"error": "Invalid user ID, email, or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_verified:
            return Response(
                {"error": "Please verify your email before requesting a login OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        otp = generate_otp()
        OTPVerification.objects.create(
            user=user,
            otp=otp,
            purpose=OTPVerification.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        send_otp_email(user, otp, purpose=OTPVerification.Purpose.LOGIN)

        return Response(
            {"message": "Login OTP sent to your email.", "email": user.email},
            status=status.HTTP_200_OK,
        )



class VerifyOTPView(generics.GenericAPIView):
    serializer_class = VerifyOTPSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        try:
            user = User.objects.get(email=email)

        except User.DoesNotExist:
            return Response(
                {
                    "error": "User not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        otp_record = OTPVerification.objects.filter(
            user=user,
            otp=otp,
            is_used=False
        ).order_by("-created_at").first()

        if not otp_record:

            return Response(
                {
                    "error": "Invalid OTP."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        
        if otp_record.expires_at < timezone.now():

            return Response(
                {
                    "error": "OTP has expired."
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        otp_record.is_used = True
        otp_record.save(update_fields=["is_used"])

        return Response(
            {
                "message": "Email verified successfully."
            },
            status=status.HTTP_200_OK
        )
    
class CurrentUserView(RetrieveAPIView):
    serializer_class = CurrentUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AdminUserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return User.objects.filter(role=User.Role.CUSTOMER).order_by("pk")


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return User.objects.all()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete user because the account is referenced by existing records."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminStaffCreateView(generics.ListCreateAPIView):
    serializer_class = StaffManagementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return User.objects.filter(
            role=User.Role.STAFF,
            staff_profile__isnull=False,
        ).select_related("staff_profile").order_by("pk")


class AdminStaffDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StaffManagementSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        return User.objects.filter(
            role=User.Role.STAFF,
            staff_profile__isnull=False,
        ).select_related("staff_profile")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {"detail": "Cannot delete staff account because it is referenced by existing records."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

