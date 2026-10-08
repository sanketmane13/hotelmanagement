
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated


from rest_framework.response import Response


from .permissions import IsAdmin, IsChef
from .serializers import (
    CreateStaffSerializer,
    StaffProfileSerializer
)

class CreateStaffView(generics.CreateAPIView):

    serializer_class = CreateStaffSerializer

    permission_classes = [
        IsAuthenticated,
        IsAdmin
    ]

class ChefTestView(generics.GenericAPIView):

    permission_classes = [
        IsAuthenticated,
        IsChef
    ]

    def get(self, request):

        return Response({
            "message": "Welcome Chef",
            "username": request.user.username,
            "role": request.user.staff_profile.role
        })
