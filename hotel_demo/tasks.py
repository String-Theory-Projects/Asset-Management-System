from django.conf import settings
from celery import shared_task
import requests
import logging
import json
from utils.helpers import get_system_user_token
from django.conf import settings
from core.models import HotelRoom, Asset 


logger = logging.getLogger()
logger.setLevel(logging.INFO)


@shared_task
def schedule_sub_asset_expiry(asset_number, sub_asset_number, action_type, data, update_status):
    logger.info(f"Expiry task started for asset {asset_number}, sub-asset {sub_asset_number}")
    url = f'{settings.DOMAIN}/api/assets/{asset_number}/control/{sub_asset_number}/'
    headers = {
        'Authorization': f'Bearer {get_system_user_token()}'
    }
    payload = {
        'action_type': action_type,
        'data': data,
        'update_status': update_status  # Add this flag to indicate status update is needed (currently only handles sub-asset deactivation)
    }
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Control request sent successfully: {url}, Status: {response.status_code}")
        logger.info(f"Response content: {response.text}")
        
        # Update room status directly in the task
        try:
            asset = Asset.objects.get(asset_number=asset_number)
            if asset.asset_type == 'hotel':
                room = HotelRoom.objects.get(hotel=asset, room_number=sub_asset_number)
                room.status = False
                room.save()
                logger.info(f"Room status updated to False for room {sub_asset_number}")
        except Exception as e:
            logger.error(f"Failed to update room status: {str(e)}")
        
    except requests.RequestException as e:
        logger.error(f"Failed to send control request: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Response status code: {e.response.status_code}")
            logger.error(f"Response content: {e.response.content}")


@shared_task()
def send_control_request(asset_number, sub_asset_number, action_type, data):
    url = f'{settings.DOMAIN}/api/assets/{asset_number}/control/{sub_asset_number}/'
    headers = {
        'Authorization': f'Bearer {get_system_user_token()}',
        'Content-Type': 'application/json'
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
