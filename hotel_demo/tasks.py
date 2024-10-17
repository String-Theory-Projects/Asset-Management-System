from celery import shared_task
import requests
import logging
from mqtt_handler.views import get_system_user_token
from hotel_demo.settings import SYSTEM_USER_REQUEST_DOMAIN


logger = logging.getLogger(__name__)
DOMAIN = SYSTEM_USER_REQUEST_DOMAIN

@shared_task
def schedule_sub_asset_expiry(asset_number, sub_asset_number, action_type, data):
    url = f'assets/{asset_number}/control/{sub_asset_number}'
    payload = {
        'action_type': action_type,
        'data': data
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.info(f"Expiry control request sent successfully: {url}")
    except requests.RequestException as e:
        logger.error(f"Failed to send expiry control request: {str(e)}")

@shared_task()
def send_control_request(asset_number, sub_asset_number, action_type, data):
    url = f'{DOMAIN}/api/assets/{asset_number}/control/{sub_asset_number}/'
    headers = {
        'Authorization': f'Bearer {get_system_user_token()}'
    }
    payload = {
        'action_type': action_type,
        'data': data
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Control request sent successfully: {url}")
    except Exception as e:
        logger.error(f"Failed to send control request: {str(e)}")

