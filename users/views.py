
from datetime import timedelta

from django.utils import timezone

from django.shortcuts import render
from rest_framework import generics
from rest_framework.permissions import AllowAny
from .serializers import RegisterSerializer, VerifyOTPSerializer

from rest_framework.response import Response
from rest_framework import status
from .models import OTPVerification
from .utils import generate_otp, send_otp_email
from django.contrib.auth import get_user_model

User = get_user_model()



# Create your views here.

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
            purpose=OTPVerification.Purpose.EMAIL_VERIFICATION,
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
    


