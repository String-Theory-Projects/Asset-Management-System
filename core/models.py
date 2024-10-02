from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from core import * #import the global variables from conf


class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', default='default_avatars/default_avatar.png', blank=True, null=True)
    account_number = models.CharField(max_length=10, blank=True, null=True)
    bank = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=255, unique=True)

    def save(self, *args, **kwargs):
        self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Transaction(models.Model):
    asset = models.ForeignKey('Asset', related_name='transactions', on_delete=models.CASCADE)
    sub_asset_id = models.IntegerField(null=True, blank=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES)
    payment_type = models.CharField(max_length=100, choices=[('card','Card'), ('transfer', 'Transfer'),('mobile_money', 'Mobile_money')])
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN')
    timestamp = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    transaction_ref = models.CharField(max_length=255, unique=True)
    processor_ref = models.CharField(max_length=255, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    is_outgoing = models.BooleanField(default=False)
    description = models.TextField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"Payment {self.id} of {self.currency}{self.amount} by {self.name}"

    class Meta:
        indexes = [
            models.Index(fields=['transaction_ref']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['timestamp']),
        ]



class Asset(models.Model):
    id = models.CharField(max_length=50, primary_key=True)
    asset_type = models.CharField(max_length=10, choices=ASSET_TYPE_CHOICES)
    asset_name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    details = models.JSONField()
    account_number = models.CharField(max_length=10)
    bank = models.CharField(max_length=20)

    def __str__(self):
        return self.asset_name


class AssetEvent(models.Model):
    asset = models.ForeignKey(Asset, on_delete=models.SET_NULL, null=True) # Retain events even if asset is deleted
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    data = models.CharField(max_length=255)

    # Generic Foreign Key fields
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    sub_asset = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.event_type} for {self.asset.asset_name if self.asset else 'Unknown Asset'} at {self.timestamp}"


class Role(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'asset')  # Ensures that each user can only have one role per asset

    def __str__(self):
        return f"{self.user} is a {self.role} of {self.asset}"


class HotelRoom(models.Model):
    hotel = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='rooms', limit_choices_to={'asset_type': 'hotel'})
    room_number = models.CharField(max_length=10)
    room_type = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.BooleanField(default=True)

    class Meta:
        unique_together = ['hotel', 'room_number']

    def __str__(self):
        return f"{self.room_number} - {self.room_type} in {self.hotel.asset_name}"


class Vehicle(models.Model):
    fleet = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='fleet', limit_choices_to={'asset_type': 'vehicle'})
    vehicle_number = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    vehicle_type = models.CharField(max_length=255)
    status = models.BooleanField(default=True)

    class Meta:
        unique_together = ['fleet', 'vehicle_number']

    def __str__(self):
        return f"{self.vehicle_number} - {self.brand} {self.vehicle_type} in {self.fleet.asset_name}"
