from rest_framework import serializers
from core.models import HotelRoom
from django.contrib.auth import get_user_model

User= get_user_model()

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelRoom
        fields = ['hotel', 'room_number', 'room_type', 'price', 'status']