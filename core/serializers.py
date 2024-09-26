from rest_framework import serializers
from .models import User
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    account_number = serializers.CharField(required=False, allow_blank=True)
    bank = serializers.CharField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    avatar = serializers.ImageField(required=False)  # Make avatar field optional

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password', 'confirm_password', 'account_number', 'bank', 'avatar']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        return value

    def validate(self, data):
        if data.get('account_number') and not data.get('bank'):
            raise serializers.ValidationError({"bank": "Bank information is required when account number is provided."})
        
        if data.get('password') != data.get('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        return data

    def create(self, validated_data):
        # Remove confirm_password from the data used to create the user
        validated_data.pop('confirm_password', None)
        # Set default avatar if not provided
        if 'avatar' not in validated_data:
            validated_data['avatar'] = 'default_avatars/default_avatar.png'
        return User.objects.create_user(**validated_data)