import json
from decimal import Decimal
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
import logging
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from .models import User, Asset, HotelRoom, Payment, Vehicle
from .serializers import UserSerializer




User = get_user_model()
logger = logging.getLogger(__name__)

# Caching helper function
def get_cached_data(cache_key, queryset):
    data = cache.get(cache_key)
    if not data:
        data = list(queryset)
        cache.set(cache_key, data, timeout=60 * 15)  # Cache for 15 minutes
    return data

class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


class RegisterView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # Creating user with validated data
                user = User.objects.create(
                    username=serializer.validated_data['email'],
                    last_name=serializer.validated_data['last_name'],
                    first_name=serializer.validated_data['first_name'],
                    email=serializer.validated_data['email'],
                    account_number=serializer.validated_data['account_number'],
                    bank=serializer.validated_data['bank'],
                    avatar=serializer.validated_data.get('avatar', 'default_avatars/default_avatar.png')
                )
                # Set the password
                user.set_password(request.data['password'])
                user.save()

                return Response({'message': 'User created successfully.'}, status=status.HTTP_201_CREATED)

            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        data = request.data
        serializer = UserSerializer(user, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserDataView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            users = User.objects.all()
            data = []
            
            for user in users:
                user_data = {
                    "id": user.id,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "avatar": user.avatar.url if user.avatar else None,
                    "assets": {
                        "hotel": [],
                        "logistics": [],
                        "machinery": []
                    },
                    "payments": []
                }

                # Get user's assets
                assets = Asset.objects.filter(roles__user_id=user)
                for asset in assets:
                    asset_data = {
                        "asset_id": str(asset.id),
                        "asset_name": asset.asset_name,
                        "created_at": asset.created_at.isoformat(),
                        "location": asset.location,
                        "details": asset.details,
                    }

                    # Differentiate asset types
                    if asset.asset_type == 'hotel':
                        asset_data["rooms"] = []
                        # Fetch related HotelRooms
                        rooms = HotelRoom.objects.filter(hotel=asset)
                        for room in rooms:
                            room_data = {
                                "id": room.id,
                                "room_number": room.room_number,
                                "room_type": room.room_type,
                                "price": room.price,
                                "status": "active" if room.status else "inactive"
                            }
                            asset_data["rooms"].append(room_data)
                        user_data["assets"]["hotel"].append(asset_data)

                    elif asset.asset_type == 'vehicle':
                        asset_data["vehicles"] = []
                        # Fetch related Vehicles
                        vehicles = Vehicle.objects.filter(fleet=asset)
                        for vehicle in vehicles:
                            vehicle_data = {
                                "id": vehicle.id,
                                "vehicle_number": vehicle.vehicle_number,
                                "type": vehicle.vehicle_type,
                                "brand": vehicle.brand,
                                "status": "active" if vehicle.status else "inactive"
                            }
                            asset_data["vehicles"].append(vehicle_data)
                        user_data["assets"]["logistics"].append(asset_data)

                    
                    # elif asset.asset_type == 'machine':
                    #     # Fetch related Machinery
                    #     machinery = Machinery.objects.filter(fleet=asset)
                    #     for machine in machinery:
                    #         machine_data = {
                    #             "id": machine.id,
                    #             "machine_number": machine.machine_number,
                    #             "machine_type": machine.machine_type,
                    #             "petrol_level": machine.petrol_level,
                    #             "status": "active" if machine.timestamp else "inactive"
                    #         }
                    #         asset_data["machines"].append(machine_data)
                    #     user_data["assets"]["machinery"].append(asset_data)

                # Get user's payments
                payments = Payment.objects.filter(asset_id__in=assets)
                for payment in payments:
                    payment_data = {
                        "id": payment.id,
                        "asset_id": str(payment.asset_id.id),  # Fixed to reference asset_id's id
                        "sub_asset_id": payment.sub_asset_id,
                        "amount": payment.amount,
                        "status": payment.payment_status,
                        "timestamp": payment.timestamp.isoformat(),
                        "payment_type": payment.payment_type
                    }
                    user_data["payments"].append(payment_data)

                data.append(user_data)
            
            pretty_data = json.dumps(data, indent=4, cls=CustomJSONEncoder)
            return HttpResponse(pretty_data, content_type="application/json")
            
        except Exception as e:
            # Log the error
            print(f"Error: {str(e)}")
            return Response({'error': 'An error occurred while processing your request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
