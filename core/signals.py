from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Transaction
from .utils import payment_aggregator

@receiver(post_save, sender=Transaction)
@receiver(post_delete, sender=Transaction)
def update_total_revenue(sender, instance, **kwargs):
    if instance.payment_status == 'completed':
        asset = instance.asset
        payment_aggregator(asset)