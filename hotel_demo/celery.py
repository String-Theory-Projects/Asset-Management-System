import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_demo.settings_test')

app = Celery('hotel_demo')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()