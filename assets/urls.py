from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssetViewSet, AssociateUserView


router = DefaultRouter()
router.register('assets', AssetViewSet, basename='asset')


urlpatterns = [
    path('', include(router.urls)),
    path('assets/associate/<str:asset_id>/', AssociateUserView.as_view(), name='associate-user'),
]
