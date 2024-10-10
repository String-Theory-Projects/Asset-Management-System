from rest_framework import permissions
from core.models import Role

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to allow only asset admins to perform certain actions.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        asset_number = view.kwargs.get('asset_number')
        if asset_number is None:
            return False

        return Role.objects.filter(
            user=request.user, 
            asset_id=asset_number, 
            role='admin'
        ).exists()


class IsManager(permissions.BasePermission):
    """
    Custom permission to allow only asset managers to perform certain actions.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        asset_number = view.kwargs.get('asset_number')
        if asset_number is None:
            # If there's no asset_id, we might want to allow the action
            # depending on the specific requirements of the use case
            return True  # or False, depending on the security needs

        return Role.objects.filter(user=request.user, asset_id=asset_number, role='manager').exists()
