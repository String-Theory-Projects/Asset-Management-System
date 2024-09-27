from decimal import Decimal
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

from celery import shared_task
import sendgrid
from sendgrid.helpers.mail import *

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


# ----------- Email & sms helpers -------------
@shared_task
def send_user_email(**kwargs):
    """Function that sends emails to users
    
    Args: receiver_email: str , message_details:{}
    Return: None
    """

@shared_task
def send_user_sms(**kwargs):
    """Function that sends SMS messages to users
    
    Args: receiver_number: str , message_details:{}
    Return: None
    """
    
    pass

# ----------- API helpers -------------

class CustomPageNumberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100