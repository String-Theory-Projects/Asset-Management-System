import requests
from django.conf import settings
from rest_framework import status

import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def initiate_flutterwave_payment(payment_data):
    payment_url = "https://api.flutterwave.com/v3/payments"
    headers = {
        "Authorization": f"Bearer {settings.FLW_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(payment_url, json=payment_data, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        payment_link = response_data.get('data', {}).get('link')
        return payment_link, None
    except requests.RequestException as e:
        return None, f"Failed to initiate payment: {str(e)}"
    
def verify_flutterwave_transaction(transaction_id):
    url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.FLW_SECRET_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for non-2xx status codes
        return response.json(), None
    except requests.RequestException as e:
        logger.error(f"Error verifying Flutterwave transaction: {str(e)}")
        return None, str(e)