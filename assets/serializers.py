from rest_framework import serializers
from core.models import Asset
from django.contrib.auth import get_user_model
from core.models import HotelRoom, Vehicle, Role, Transaction

User = get_user_model()

class TransactionHistorySerializer(serializers.ModelSerializer):
    date_time = serializers.DateTimeField(source='timestamp', format="%Y-%m-%d %H:%M:%S")

    class Meta:
        model = Transaction
        fields = ['name', 'amount', 'sub_asset_number', 'payment_status', 'date_time']
        

class AssetSerializer(serializers.ModelSerializer):
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = ['asset_number', 'asset_type', 'asset_name', 'location', 'created_at', 'total_revenue', 'details', 'account_number', 'bank', 'user_role']
        read_only_fields = ['asset_number', 'created_at', 'total_revenue', 'user_role']

    def get_user_role(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            role = Role.objects.filter(user=request.user, asset=obj).first()
            return role.role if role else None
        return None

    def create(self, validated_data):
        user = validated_data.pop('user', None)
        asset = Asset(**validated_data)
        asset.save(user=user)
        return asset

    def update(self, instance, validated_data):
        user = validated_data.pop('user', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(user=user)
        return instance


class AssetUserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()
    role_association_timestamp = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['full_name', 'username', 'last_login', 'role', 'role_association_timestamp']

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    def get_role(self, obj):
        asset_number = self.context.get('asset_number')
        role = obj.roles.filter(asset__asset_number=asset_number).first()
        return role.role if role else None

    def get_role_association_timestamp(self, obj):
        asset_number = self.context.get('asset_number')
        role = obj.roles.filter(asset__asset_number=asset_number).first()
        return role.created_at if role else None


class AssociateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=['admin', 'manager', 'viewer'])


class DisassociateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class HotelRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelRoom
        fields = ['id', 'room_number', 'room_type', 'price', 'status', 'hotel']
        read_only_fields = ['id', 'hotel']
        extra_kwargs = {
            'room_number': {'required': True}
        }


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = ['id', 'vehicle_number', 'brand', 'vehicle_type', 'status', 'fleet']
        read_only_fields = ['id', 'fleet']
        extra_kwargs = {
            'vehicle_number': {'required': True}
        }
