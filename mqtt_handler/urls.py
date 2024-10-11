from django.urls import path
from .views import ControlAssetView, CheckSubAssetStatusView, CheckAssetStatusView

urlpatterns = [
    path('assets/<str:asset_number>/control/<str:sub_asset_id>/', ControlAssetView.as_view(), name='control_asset'),
    path('assets/<str:asset_number>/status/<str:sub_asset_id>/', CheckSubAssetStatusView.as_view(), name='check_sub_asset_status'),
    path('assets/<str:asset_number>/status/', CheckAssetStatusView.as_view(), name='check-asset-status'), # default = /?days=7
]
