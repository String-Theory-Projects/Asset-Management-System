from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Payment
from .utils import payment_aggregator

@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
def update_total_revenue(sender, instance, **kwargs):
    if instance.payment_status == 'completed':
        asset = instance.asset_id
        payment_aggregator(asset)