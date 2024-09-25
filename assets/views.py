from django.core.cache import cache

from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.viewsets import ModelViewSet
from rest_framework.views import APIView

from .serializers import AssetSerializer, AssociateUserSerializer
from core.models import Asset, Role, User
from core.permissions import IsAdmin, IsManager
from assets import ROLE_CHOICES


class AssetViewSet(ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer

    def get_permissions(self):
        # Apply custom permission for update or delete actions
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), IsAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        cache_key = f'user_assets_{user.id}'
        
        # Check cache first
        assets = cache.get(cache_key)
        if not assets:
            # Filter assets associated with the logged-in user
            assets = Asset.objects.filter(roles__user_id=user.id)
            cache.set(cache_key, assets, 60 * 5)  # Cache for 5 minutes
        
        return assets

    def perform_create(self, serializer):
        user = self.request.user
        asset = serializer.save()

        # create the role associating the user with this asset
        Role.objects.create(user=user, asset=asset, role=ROLE_CHOICES[0])

        cache.delete(f'user_assets_{user.id}')  # Invalidate cache on asset creation


    def perform_update(self, serializer):
        super().perform_update(serializer)
        user = self.request.user
        cache.delete(f'user_assets_{user.id}')  # Invalidate cache on asset update

    def perform_destroy(self, instance):
        user = self.request.user
        instance.delete()
        cache.delete(f'user_assets_{user.id}')  # Invalidate cache on asset deletion

    # List assets associated with the user
    def list(self, request, *args, **kwargs):
        asset_type = request.query_params.get('type', None)
        queryset = self.filter_queryset(self.get_queryset())
        
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # Create a new asset
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # Retrieve a specific asset
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # Update asset information
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    # Delete an asset
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssociateUserView(APIView):
    permission_classes = [IsAuthenticated]  # Authentication required

    def post(self, request, *args, **kwargs):
        asset_id = kwargs.get('asset_id')
        if not asset_id:
            return Response({'error': 'Asset ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Try to get the asset by its primary key 'id'
        try:
            asset = Asset.objects.get(id=asset_id)
        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Verify that the user is either an admin or a manager for the asset
        if not (IsAdmin().has_permission(request, self) or IsManager().has_permission(request, self)):
            return Response({'error': 'You do not have permission to associate users with this asset.'}, status=status.HTTP_403_FORBIDDEN)

        # Deserialize and validate the request data
        serializer = AssociateUserSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            role = serializer.validated_data['role']

            # Check if a user with the given email exists
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                return Response({'error': 'User with this email does not exist.'}, status=status.HTTP_404_NOT_FOUND)

            # Create or update the role association
            Role.objects.update_or_create(user=user, asset=asset, defaults={'role': role})

            return Response({'message': 'User associated with the asset successfully.'}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)