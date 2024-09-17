from rest_framework import serializers
from core.models import Asset
from django.contrib.auth import get_user_model


User = get_user_model()

class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = '__all__'

    def create(self, validated_data):
        # If you have a many-to-many field, exclude it from the creation of the object
        users = validated_data.pop('users', None)  # pop the 'users' field, if it exists

        # Create the Asset object with the remaining data
        asset = Asset.objects.create(**validated_data)

        # Now, if users were provided, set them
        if users:
            asset.users.set(users)  # Add users to the asset's many-to-many field

        return asset
