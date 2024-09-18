from django.core.cache import cache
from rest_framework import status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.viewsets import ModelViewSet
from core.models import Asset, Role
from .serializers import AssetSerializer


ROLE_CHOICES = [
    'admin',
    'manager',
    'viewer'
]

class AssetViewSet(ModelViewSet):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = AssetSerializer

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
