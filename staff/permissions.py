from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):

    message = "Only admin users are allowed."

    def has_permission(self, request, view):

        return (request.user.is_authenticated and request.user.role == request.user.Role.ADMIN)

    
class IsStaff(BasePermission):

    message = "Only staff users are allowed."

    def has_permission(self, request, view):

        return ( request.user.is_authenticated and request.user.role == request.user.Role.STAFF)


class IsCustomer(BasePermission):

    message = "Only customers are allowed."

    def has_permission(self, request, view):

        return (request.user.is_authenticated and request.user.role == request.user.Role.CUSTOMER)

    

class IsChef(BasePermission):

    message = "Only chefs are allowed."

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        if request.user.role != request.user.Role.STAFF:
            return False

        if not hasattr(request.user, "staff_profile"):
            return False

        return (
            request.user.staff_profile.role == "CHEF"
        )

class IsWaiter(BasePermission):

    message = "Only waiters are allowed."

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        if request.user.role != request.user.Role.STAFF:
            return False

        if not hasattr(request.user, "staff_profile"):
            return False

        return (
            request.user.staff_profile.role == "WAITER"
        )


class IsHelper(BasePermission):

    message = "Only helpers are allowed."

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        if request.user.role != request.user.Role.STAFF:
            return False

        if not hasattr(request.user, "staff_profile"):
            return False

        return (
            request.user.staff_profile.role == "HELPER"
        )

