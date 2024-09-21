from rest_framework import serializers
from core.models import HotelRoom, HotelRoomHistory
from django.contrib.auth import get_user_model

User= get_user_model()

class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelRoom
        fields = ['id', 'room_number', 'room_type', 'price', 'status']
        read_only_fields = ['id']
