import json
import logging

from django.db import transaction, IntegrityError
from django.db.models import Q, F
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.utils.datetime_safe import datetime
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.filters import OrderingFilter

from rave_python.rave_misc import generateTransactionReference

from django.utils import timezone
from datetime import timedelta
import math

from utils.helpers import *
from utils.payment import initiate_paystack_payment, verify_paystack_payment
from django.conf import settings

from core import TRANSACTION_REFERENCE_PREFIX as tref_pref
from core import *
from .serializers import UserSerializer, TransactionSerializer
from .models import User, Asset, HotelRoom, Transaction, Vehicle
from .permissions import IsAdmin,IsManager
from hotel_demo.tasks import schedule_sub_asset_expiry, send_control_request

User = get_user_model()
logger = logging.getLogger()
logger.setLevel(logging.INFO)
# ---------- AUTH VIEWS ----------

class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []
    
    def post(self, request, *args, **kwargs):
        logger.info(f"Received registration request: {request.data}")
        serializer = UserSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                logger.info(f"User created successfully: {user.email}")
                return Response({
                    'message': 'User created successfully.',
                    'user': UserSerializer(user).data
                }, status=status.HTTP_201_CREATED)

            except IntegrityError as e:
                logger.error(f"IntegrityError during user creation: {str(e)}")
                return Response({'error': f'A user with this email already exists. Details: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
            except ValidationError as e:
                logger.error(f"ValidationError during user creation: {str(e)}")
                return Response({'error': f'Validation error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                logger.error(f"Unexpected error during user creation: {str(e)}", exc_info=True)
                return Response({'error': f'An unexpected error occurred: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            logger.error(f"Serializer validation failed: {serializer.errors}")
            error_messages = {}
            for field, errors in serializer.errors.items():
                error_messages[field] = errors[0]
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
            return Response({'error': 'An error occurred while processing your request.'}, status=status.HTTP_400_BAD_REQUEST)


# ---------- PAYMENT VIEWS ----------

class InitiatePaymentView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        tx_ref = generateTransactionReference(tref_pref)

        try:
            # Validate and retrieve fields
            customer_email = validate_field(request.data, "email", [str])
            customer_name = validate_field(request.data, "name", [str])
            customer_phonenumber = validate_field(request.data, "phonenumber", [str])
            amount = validate_field(request.data, "amount", [float, int])  # Allow int for amounts as well
            redirect_url = validate_field(request.data, "redirect_url", [str])
            title = validate_field(request.data, "title", [str])
            description = validate_field(request.data, "description", [str])
            asset_number = validate_field(request.data, "asset_number", [str])
            sub_asset_number = validate_field(request.data, "sub_asset_number", [str])
            sub_asset_type = validate_field(request.data, "sub_asset_type", [str], required=False)
            
            # Optional fields
            currency = validate_field(request.data, "currency", [str], required=False, default="NGN")
            is_outgoing = validate_field(request.data, "is_outgoing", [bool], required=False, default=False)

            # check if the asset and subasset exist
            asset = Asset.objects.filter(asset_number=asset_number).first()
            if not asset:
                raise ValueError("Asset not found.")

            # Determine if we should filter by a specific sub-asset type
            if sub_asset_type:
                sub_asset = None
                if sub_asset_type == "vehicle":
                    sub_asset = Vehicle.objects.filter(vehicle_number=sub_asset_number).first()
                elif sub_asset_type == "hotel_room":
                    sub_asset = HotelRoom.objects.filter(room_number=sub_asset_number).first()
                
                if not sub_asset:
                    raise ValueError(f"{sub_asset_type.capitalize()} sub-asset not found.")
            else:
                # Check all sub-assets for the given asset number
                vehicle_sub_assets = Vehicle.objects.filter(vehicle_number=sub_asset_number).first()
                hotel_room_sub_assets = HotelRoom.objects.filter(room_number=sub_asset_number).first()

                if not vehicle_sub_assets and not hotel_room_sub_assets:
                    raise ValueError("No sub-assets found for the given sub-asset number.")

        except KeyError as e:
            return Response({"error": f"Missing required field: {e.args[0]}"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        payment_data = {
            "email": customer_email,
            "amount": amount,
            "currency": currency,
            "callback_url": redirect_url,
            "reference": tx_ref
        }


        payment_link, error = initiate_paystack_payment(payment_data)

        if error:
            return Response({"error": error}, status=status.HTTP_400_BAD_REQUEST)

        if payment_link:
            try:
                with transaction.atomic(): #start a transaction to ensure that the database is consistent
                    asset = Asset.objects.get(asset_number=asset_number)
                    if not asset:
                        return Response({"error": f"Asset ({asset_number}) does not exist"}, status=status.HTTP_400_BAD_REQUEST)
                    transaction_obj = Transaction.objects.create(
                        asset=asset,
                        sub_asset_number=sub_asset_number,
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
                    "transaction_ref": tx_ref
                }, status=status.HTTP_200_OK)
            except Asset.DoesNotExist:
                return Response({"error": "Invalid asset number"}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"Failed to create transaction: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response({"error": "Payment link not found"}, status=status.HTTP_400_BAD_REQUEST)
        
class VerifyPaymentView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        tx_ref = request.GET.get('trxref')
        if not tx_ref:
            return Response({"error": "Missing required parameters"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                db_transaction = Transaction.objects.select_for_update().get(transaction_ref=tx_ref)
                
                if db_transaction.is_verified: 
                    logger.info(f"Transaction {tx_ref} already verified")
                    return Response({"message": "Payment already verified"}, status=status.HTTP_200_OK)

                # Verify the transaction status with Paystack
                transaction_data, error = verify_paystack_payment(tx_ref)
                if error:
                    logger.error(f"Error verifying transaction: {error}")
                    return Response({"error": "Failed to verify transaction"}, status=status.HTTP_400_BAD_REQUEST)

                if not transaction_data:
                    logger.error("No transaction data received")
                    return Response({"error": "No transaction data received"}, status=status.HTTP_400_BAD_REQUEST)

                transaction_status =  "completed" if transaction_data['message'] == "Verification successful" else "failed"
                self.process_transaction(db_transaction, transaction_status)
                if transaction_status == 'completed':
                    return Response({"message": "Payment verified successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response({"message": f"Payment status updated to {transaction_status}"}, status=status.HTTP_200_OK)

        except Transaction.DoesNotExist:
            logger.error(f"Transaction {tx_ref} not found in database")
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        except KeyError as e:
            logger.error(f"Error parsing api response: {e}")
            return Response({"error": "Merchant error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            logger.error(f"Error processing transaction {tx_ref}: {str(e)}")
            return Response({"error": "Error processing payment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def process_transaction(self, transaction, status_param):
        self.update_transaction(transaction, status_param)
        if status_param == 'completed' and not transaction.is_outgoing:
            self.update_asset_revenue(transaction)
            self.update_sub_asset(transaction)

        # Trigger async tasks
        # send_user_sms.delay() # NOTE: these are currently unimplemented
        # send_user_email.delay()

    def update_transaction(self, transaction, status_param):
        transaction.payment_status = status_param
        transaction.is_verified = True
        transaction.save()
        logger.info(f"Transaction {transaction.transaction_ref} updated successfully")

    def update_asset_revenue(self, transaction):
        Asset.objects.filter(asset_number=transaction.asset.asset_number).update(
            total_revenue=F('total_revenue') + transaction.amount
        )
        logger.info(f"Updated total revenue for asset {transaction.asset.asset_number}")

    def update_sub_asset(self, transaction):
        asset = transaction.asset
        sub_asset_number = transaction.sub_asset_number
        current_time = timezone.now()

        if asset.asset_type == 'hotel':
            room = HotelRoom.objects.get(hotel=asset, room_number=sub_asset_number)
            duration_days = math.ceil(float(transaction.amount) / float(room.price))

            if room.status and room.expiry_timestamp > current_time:
                # Room is already active, extend the expiry
                if settings.DEBUG is True:
                    new_expiry = room.expiry_timestamp + timedelta(minutes=duration_days)
                else:
                    new_expiry = room.expiry_timestamp + timedelta(days=duration_days)
            else:
                # Room is not active or has expired, set new activation and expiry
                room.activation_timestamp = current_time
                if settings.DEBUG is True:
                    new_expiry = current_time + timedelta(minutes=duration_days)
                else:
                    new_expiry = current_time + timedelta(days=duration_days)
            
            send_control_request.apply_async(args=[asset.asset_number, sub_asset_number, "access", "unlock"])
            room.status = True
            room.expiry_timestamp = new_expiry
            room.save()
            
            # Cancel any existing expiry task and schedule a new one
            schedule_sub_asset_expiry.apply_async(
                args=[asset.asset_number, sub_asset_number, "access", "lock"],
                eta=new_expiry
            )
            
            logger.info(f"Updated HotelRoom {room.room_number} status and timestamps. New expiry: {new_expiry}")

        elif asset.asset_type == 'vehicle':
            vehicle = Vehicle.objects.get(fleet=asset, vehicle_number=sub_asset_number)
            duration_days = 1  # Assuming 1 day per payment, adjust as needed

            if vehicle.status and vehicle.expiry_timestamp > current_time:
                # Vehicle is already active, extend the expiry
                new_expiry = vehicle.expiry_timestamp + timedelta(days=duration_days)
            else:
                # Vehicle is not active or has expired, set new activation and expiry
                vehicle.activation_timestamp = current_time
                new_expiry = current_time + timedelta(days=duration_days)
            send_control_request.apply_async(args=[asset.asset_number, sub_asset_number, "ignition", "turn_on"], eta=datetime.now())
            vehicle.status = True
            vehicle.expiry_timestamp = new_expiry
            vehicle.save()
            # Cancel any existing expiry task and schedule a new one
            schedule_sub_asset_expiry.apply_async(
                args=[asset.asset_number, sub_asset_number, "ignition", "turn_off"],
                eta=new_expiry
            )
            logger.info(f"Updated Vehicle {vehicle.vehicle_number} status and timestamps. New expiry: {new_expiry}")

        else:
            logger.warning(f"Unsupported asset type: {asset.asset_type}")


class TransactionPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class TransactionListView(APIView):
    pagination_class = TransactionPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['payment_status', 'payment_type', 'currency', 'is_outgoing']
    ordering_fields = ['timestamp', 'amount']
    ordering = ['-timestamp']  # Default ordering

    def get_queryset(self):
        user = self.request.user
        
        if IsAdmin():
            queryset = Transaction.objects.all()
        elif IsManager():
            queryset = Transaction.objects.filter(asset__manager=user)
        else:
            # For non-admin, non-manager users, return an empty queryset or handle as needed
            queryset = Transaction.objects.none()

        search_query = self.request.query_params.get('search', None)
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(transaction_ref__icontains=search_query)
            )
        return queryset

    def get(self, request, transaction_id=None):
        if transaction_id:
            transaction = get_object_or_404(Transaction, id=transaction_id)
            if not IsAdmin() and (not IsManager() or transaction.asset.manager != request.user):
                return Response({"detail": "You do not have permission to view this transaction."}, status=status.HTTP_403_FORBIDDEN)
            serializer = TransactionSerializer(transaction)
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = TransactionSerializer(queryset, many=True)
        return Response(serializer.data)

    def filter_queryset(self, queryset):
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset

    @property
    def paginator(self):
        if not hasattr(self, '_paginator'):
            if self.pagination_class is None:
                self._paginator = None
            else:
                self._paginator = self.pagination_class()
        return self._paginator

    def paginate_queryset(self, queryset):
        if self.paginator is None:
            return None
        return self.paginator.paginate_queryset(queryset, self.request, view=self)

    def get_paginated_response(self, data):
        assert self.paginator is not None
        return self.paginator.get_paginated_response(data)