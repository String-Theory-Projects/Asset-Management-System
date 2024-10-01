from rest_framework import serializers
from core.models import Asset
from django.contrib.auth import get_user_model


class AssetSerializer(serializers.ModelSerializer):
    asset_number = serializers.SerializerMethodField()

    class Meta:
        model = Asset
        fields = "__all__"
        read_only_fields = ['id', 'asset_number']

# Genearating asset number
    def get_asset_number(self, obj):
        
        user_id = obj.roles.first().user.id
        # Get total count of user assets till this point
        user_assets = Asset.objects.filter(roles__user__id=user_id).order_by('created_at')
        # Getting the asset ordinal number from a list of assets
        asset_number = list(user_assets).index(obj) + 1
        formatted_user_id = f"{user_id:05}" # Limiting the user id to five digits
        formatted_asset_number = f"{asset_number:03}" # Limiting the asset_number to three digits

        return f"TP{formatted_user_id}{formatted_asset_number}"
    
    def create(self, validated_data):
        # If you have a many-to-many field, exclude it from the creation of the object
        users = validated_data.pop('users', None)  # pop the 'users' field, if it exists

        # Create the Asset object with the remaining data
        asset = Asset.objects.create(**validated_data)

        # Now, if users were provided, set them
        if users:
            asset.users.set(users)  # Add users to the asset's many-to-many field

        return asset


class AssociateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    role = serializers.ChoiceField(choices=['admin', 'manager', 'viewer'])
