from django.urls import path
from .views import IndexStats

urlpatterns = [
    path('analytics/index/', IndexStats.as_view(), name='user-asset-statistics'), # ?year=2024&month=10
]