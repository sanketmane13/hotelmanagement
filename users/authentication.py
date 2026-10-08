from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

User = get_user_model()

class HotelTokenObtainPairSerializer(TokenObtainPairSerializer):
    

    def validate(self, attrs):

        data = super().validate(attrs)

        user = self.user

        if not user.is_verified:

            raise serializers.ValidationError(
                "Please verify your email before login."
            )

        return data

class HotelTokenObtainPairView(TokenObtainPairView):

    serializer_class = HotelTokenObtainPairSerializer

    