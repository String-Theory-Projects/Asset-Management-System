from django.urls import path
from .views import ControlAssetView, CheckSubAssetStatusView

urlpatterns = [
    path('assets/<asset_id>/control/<sub_asset_id>/', ControlAssetView.as_view(), name='control_asset'),
    path('assets/<asset_id>/status/<sub_asset_id>/', CheckSubAssetStatusView.as_view(), name='check_sub_asset_status'),
]
