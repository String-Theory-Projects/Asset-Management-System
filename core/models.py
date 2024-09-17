from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


ROLE_CHOICES = [
    ('admin', 'Admin'),
    ('manager', 'Manager'),
    ('viewer', 'Viewer'),
]

PAYMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('failed', 'Failed')
]

ASSET_TYPE_CHOICES = [
    ('vehicle', 'Vehicle'),
    # ('machine', 'Machine'),
    ('hotel', 'Hotel'),
]

class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', default='default_avatars/default_avatar.png', blank=True, null=True)
    account_number = models.CharField(max_length=10)
    bank = models.CharField(max_length=20)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=255, unique=True)

    def save(self, *args, **kwargs):
        self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Payment(models.Model):
    asset_id = models.ForeignKey('Asset', related_name='payments', on_delete=models.CASCADE)
    sub_asset_id = models.IntegerField()
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES)
    payment_type = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)
    checkout = models.CharField(max_length=255)
    sender_name = models.CharField(max_length=255)

    def __str__(self):
        return f"Payment {self.id} for {self.asset_id.asset_name}"


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

class Role(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='roles')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='roles')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    class Meta:
        unique_together = ('user', 'asset')  # Ensures that each user can only have one role per asset

    def __str__(self):
        return f"{self.user} is a {self.role} of {self.asset}"

class HotelRoom(models.Model):
    id = models.AutoField(primary_key=True)
    hotel = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='rooms', limit_choices_to={'asset_type': 'hotel'})
    room_number = models.CharField(max_length=10, unique=True)
    room_type = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.room_number} - {self.room_type} in {self.hotel.asset_name}"


class HotelRoomHistory(models.Model):
    id = models.AutoField(primary_key=True)
    room_id = models.ForeignKey(HotelRoom, on_delete=models.CASCADE, related_name='history')
    access = models.BooleanField()
    utility = models.BooleanField()
    occupancy = models.BooleanField()
    timestamp = models.DateTimeField(default=timezone.now)
    message_data = models.JSONField()  # To store other message data if needed

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Room Data: {self.message_data}"



class Vehicle(models.Model):
    id = models.AutoField(primary_key=True)
    fleet = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='fleet', limit_choices_to={'asset_type': 'vehicle'})
    brand = models.CharField(max_length=255)
    vehicle_type = models.CharField(max_length=255)
    vehicle_number = models.CharField(max_length=255)
    brand = models.CharField(max_length=255)
    status = models.BooleanField(default=True)

    def __str__(self):
        return f"Vehicle {self.asset.asset_name}"

class VehicleHistory(models.Model):
    id = models.AutoField(primary_key=True)
    vehicle_id = models.ForeignKey(Vehicle, on_delete=models.CASCADE, related_name='history')
    num_passengers = models.IntegerField()
    location = models.CharField(max_length=255)
    timestamp = models.DateTimeField(default=timezone.now)
    message_data = models.JSONField()  # To store other message data if needed

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Vehicle Data: {self.message_data}"

# class Machinery(Asset):
#     id = models.AutoField(primary_key=True)
#     fleet = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='fleet', limit_choices_to={'asset_type': 'machine'})
#     machine_type = models.CharField(max_length=255)
#     machine_number = models.CharField(max_length=255)
#     petrol_level = models.FloatField()
#     timestamp = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return f"Machinery {self.asset.asset_name}"
