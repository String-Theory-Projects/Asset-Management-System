from rest_framework import permissions
from core.models import Role

class IsAdmin(permissions.BasePermission):
    """
    Custom permission to allow only asset admins to perform certain actions.
    """

    def has_permission(self, request, view):
        # Check if the user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Extract the asset from the request (assuming the asset ID is passed in the URL)
        asset_id = view.kwargs.get('asset_id')
        if asset_id is None:
            return False

        # Check if the user has an admin role for the given asset
        return Role.objects.filter(user=request.user, asset_id=asset_id, role='admin').exists()


class IsManager(permissions.BasePermission):
    """
    Custom permission to allow only asset managers to perform certain actions.
    """

    def has_permission(self, request, view):
        # Check if the user is authenticated
        if not request.user or not request.user.is_authenticated:
            return False

        # Extract the asset ID from the request (assuming it's passed in the URL)
        asset_id = view.kwargs.get('asset_id')
        if asset_id is None:
            return False

        # Check if the user has a manager role for the given asset
        return Role.objects.filter(user=request.user, asset_id=asset_id, role='manager').exists()