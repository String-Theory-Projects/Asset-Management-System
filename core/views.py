import json
from decimal import Decimal
import logging
import requests

from django.db import transaction, IntegrityError
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.conf import settings

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny


from rave_python import Rave
from rave_python.rave_misc import generateTransactionReference 


from utils.helpers import get_cached_data, CustomJSONEncoder
from utils.payment import initiate_flutterwave_payment
from core import TRANSACTION_REFERENCE_PREFIX as tref_pref
from core import *
from .serializers import UserSerializer
from .models import User, Asset, HotelRoom, Transaction, Vehicle


User = get_user_model()
logger = logging.getLogger(__name__)

# ---------- AUTH VIEWS ----------

class RegisterView(APIView):
    authentication_classes = []  # Disable authentication for this view
    permission_classes = []  # Disable permissions for this view
    
    def post(self, request, *args, **kwargs):
        serializer = UserSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response({
                    'message': 'User created successfully.',
                    'user': UserSerializer(user).data
                }, status=status.HTTP_201_CREATED)

            except IntegrityError:
                return Response({'error': 'A user with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)
            except ValidationError as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({'error': 'An unexpected error occurred. Please try again later.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Customize error messages
            error_messages = {}
            for field, errors in serializer.errors.items():
                error_messages[field] = errors[0]  # Take the first error message for each field
            return Response({'errors': error_messages}, status=status.HTTP_400_BAD_REQUEST)

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

# ---------- USER VIEWS ----------

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
                payments = Transaction.objects.filter(asset_id__in=assets)
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


# ---------- PAYMENT VIEWS ----------

class InitiatePaymentView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        tx_ref = generateTransactionReference(tref_pref)

        try:
            customer_email = request.data["email"]
            customer_name = request.data["name"]
            customer_phonenumber = request.data["phonenumber"]
            amount = request.data["amount"]
            redirect_url = request.data["redirect_url"]
            title = request.data["title"]
            description = request.data["description"]
            asset_id = request.data["asset_id"]
            sub_asset_id = request.data.get("sub_asset_id")
            currency = request.data.get("currency", "NGN")
            is_outgoing = request.data.get("is_outgoing", False)
        except KeyError as e:
            return Response({"error": f"Missing required field: {e.args[0]}"}, status=status.HTTP_400_BAD_REQUEST)

        payment_data = {
            "tx_ref": tx_ref,
            "amount": amount,
            "currency": currency,
            "redirect_url": redirect_url,
            "customer": {
                "email": customer_email,
                "name": customer_name,
                "phonenumber": customer_phonenumber
            },
            "customizations": {
                "title": title,
                "description": description
            }
        }

        payment_link, error = initiate_flutterwave_payment(payment_data)

        if error:
            return Response({"error": error}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if payment_link:
            try:
                with transaction.atomic(): #start a transaction to ensure that the database is consistent
                    asset = Asset.objects.get(id=asset_id)
                    transaction_obj = Transaction.objects.create(
                        asset_id=asset,
                        sub_asset_id=sub_asset_id,
                        payment_status='pending',
                        payment_type='card',  # TODO: confirm if card payment, adjust if needed
                        amount=amount,
                        currency=currency,
                        transaction_ref=tx_ref,
                        name=customer_name,
                        email=customer_email,
                        description=description,
                        is_outgoing=is_outgoing
                    )
                return Response({
                    "payment_link": payment_link,
                    "transaction_id": transaction_obj.id
                }, status=status.HTTP_200_OK)
            except Asset.DoesNotExist:
                return Response({"error": "Invalid asset_id"}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"Failed to create transaction: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"error": "Payment link not found"}, status=status.HTTP_400_BAD_REQUEST)
        
