from rest_framework import serializers
from .models import User, Asset, HotelRoom, Payment, Vehicle, HotelRoomHistory, VehicleHistory
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'account_number', 'bank', 'avatar']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
