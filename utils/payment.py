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
        response = requests.get(url, headers=headers, timeout=30)  # Increased timeout
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, "Connection timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Connection error: {str(e)}"
    except ValueError:  # Includes JSONDecodeError
        return None, "Invalid response from Flutterwave"
    
def initiate_paystack_payment(payment_data):
    payment_url = "https://api.paystack.co/transaction/initialize"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payment_data['amount'] = str(100 * float(payment_data['amount']))
        response = requests.post(payment_url, json=payment_data, headers=headers)
        response.raise_for_status()
        response_data = response.json()
        payment_link = response_data.get('data', {}).get('authorization_url')
        return payment_link, None
    except ValueError as e:
        return None, f"Failed to convert amount to appropriate format: {str(e)}"
    except requests.RequestException as e:
        return None, f"Failed to initiate payment: {str(e)}"
    


def verify_paystack_payment(transaction_ref):
    url = f"https://api.paystack.co/transaction/verify/{transaction_ref}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)  # Increased timeout
        response.raise_for_status()
        return response.json(), None
    except requests.exceptions.Timeout:
        return None, "Connection timed out"
    except requests.exceptions.RequestException as e:
        return None, f"Connection error: {str(e)}"
    except ValueError:  # Includes JSONDecodeError
        return None, "Invalid response from Flutterwave"