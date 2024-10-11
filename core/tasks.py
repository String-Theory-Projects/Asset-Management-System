from celery import shared_task
import requests
import logging

logger = logging.getLogger(__name__)

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