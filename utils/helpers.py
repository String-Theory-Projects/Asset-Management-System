from decimal import Decimal
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

from rest_framework.pagination import PageNumberPagination


# ----------- Data manipulation -------------
def get_cached_data(cache_key, queryset):
    data = cache.get(cache_key)
    if not data:
        data = list(queryset)
        cache.set(cache_key, data, timeout=60 * 15)  # Cache for 15 minutes
    return data

class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# ----------- API helpers -------------

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100