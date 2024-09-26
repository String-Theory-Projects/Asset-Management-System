import requests
from django.conf import settings
from rest_framework import status

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