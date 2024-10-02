from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, AssociateUserView, VehicleViewSet, HotelRoomViewSet, DisassociateUserView, AssetUsersListView


router = DefaultRouter()

router = DefaultRouter()
router.register(r'assets/(?P<asset_id>[^/.]+)/rooms', HotelRoomViewSet, basename='hotel-room')
router.register(r'assets/(?P<asset_id>[^/.]+)/vehicles', VehicleViewSet, basename='vehicle')
router.register('assets', AssetViewSet, basename='asset')


urlpatterns = [
    path('', include(router.urls)),
    path('assets/invite/<str:asset_id>/', AssociateUserView.as_view(), name='invite-user'),
    path('assets/kick/<str:asset_id>/', DisassociateUserView.as_view(), name='kick-user'),
    path('assets/<str:asset_id>/rooms/<str:room_number>/', HotelRoomViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='hotel-room-detail'),
    path('assets/<str:asset_id>/vehicles/<str:vehicle_number>/', VehicleViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='vehicle-detail'),
    path('assets/<str:asset_id>/users/', AssetUsersListView.as_view(), name='asset-users-list'),
]

urlpatterns += router.urls
