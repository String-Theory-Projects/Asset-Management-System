from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from .models import Payment, Asset

@receiver(post_save, sender=Payment)
@receiver(post_delete, sender=Payment)
def update_total_revenue(sender, instance, **kwargs):
    if instance.payment_status == 'completed':
        asset = instance.asset_id
        total_revenue = asset.payments.aggregate(total=Sum('amount'))['total'] or 0.0
        asset.total_revenue = total_revenue
        asset.save()
