from django.db.models import Sum
from core.models import Transaction, Asset

def payment_aggregator(asset):
    # Calculating the total payments for a given asset
    total_payments = Transaction.objects.filter(asset=asset, payment_status='completed').aggregate(total=Sum('amount'))
    # If no payments set to 0
    total_amount = total_payments['total'] if total_payments['total'] is not None else 0
    asset.total_revenue = total_amount
    asset.save()