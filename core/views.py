import json
from decimal import Decimal
import logging
import requests

from django.db import transaction, IntegrityError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import OrderingFilter

from rave_python import Rave
from rave_python.rave_misc import generateTransactionReference 


from utils.helpers import *
from utils.payment import initiate_flutterwave_payment, verify_flutterwave_transaction

from core import TRANSACTION_REFERENCE_PREFIX as tref_pref
from core import *
from .serializers import UserSerializer, TransactionSerializer
from .models import User, Asset, HotelRoom, Transaction, Vehicle
from .permissions import IsAdmin,IsManager


User = get_user_model()

logger = logging.getLogger()
logger.setLevel(logging.INFO)
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
        
class VerifyPaymentView(APIView):
    permission_classes = [AllowAny]
    def get(self, request):
        tx_ref = request.GET.get('tx_ref')
        transaction_id = request.GET.get('transaction_id')

        if not all([tx_ref, transaction_id]):
            logger.error(f"Missing required parameters: tx_ref={tx_ref}, transaction_id={transaction_id}")
            return Response({"error": "Missing required parameters"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Verify the transaction status
            transaction_data, error = verify_flutterwave_transaction(transaction_id)

            if error:
                logger.error(f"Error verifying transaction: {error}")
                return Response({"error": "Failed to verify transaction"}, status=status.HTTP_400_BAD_REQUEST)

            if not transaction_data:
                logger.error("No transaction data received")
                return Response({"error": "No transaction data received"}, status=status.HTTP_400_BAD_REQUEST)

            flw_status = transaction_data.get('status', '').lower()

            # Use select_for_update to lock the row and ensure idempotency
            with transaction.atomic():
                db_transaction = Transaction.objects.select_for_update().get(transaction_ref=tx_ref)
                
                if db_transaction.is_verified:
                    logger.info(f"Transaction {tx_ref} already verified")
                    return Response({"message": "Payment already verified"}, status=status.HTTP_200_OK)

                self.update_transaction(db_transaction, flw_status)
                if flw_status == 'successful':
                    return Response({"message": "Payment verified successfully"}, status=status.HTTP_200_OK)
                else:
                    return Response({"message": f"Payment status updated to {flw_status}"}, status=status.HTTP_200_OK)

        except Transaction.DoesNotExist:
            logger.error(f"Transaction {tx_ref} not found in database")
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error processing transaction {tx_ref}: {str(e)}")
            return Response({"error": "Error processing payment"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update_transaction(self, transaction, status):
        transaction.payment_status = status
        transaction.is_verified = True

        transaction.save()

        # Trigger async tasks
        send_user_sms() # NOTE: these are currently unimplemented
        send_user_email()

        logger.info(f"Transaction {transaction.transaction_ref} updated successfully")

class FlutterwaveWebhookView(APIView):

    """
    Webhook to allow flutterwave update transaction status on db  
    Keyword arguments:
    argument -- description
    Return: return_description
    """
    
    def post(self, request):
        # Verify webhook signature
        if not self.verify_webhook_signature(request):
            logger.error("Invalid webhook signature")
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = request.data.get('event')
        if event_type == 'charge.completed':
            tx_ref = request.data['data']['tx_ref']
            try:
                with transaction.atomic():
                    db_transaction = Transaction.objects.select_for_update().get(transaction_ref=tx_ref)
                    if not db_transaction.is_verified:
                        verification_result = self.verify_flutterwave_transaction(request.data['data']['id'])
                        if verification_result['status'] == 'success':
                            self.update_transaction(db_transaction, verification_result)
            except Transaction.DoesNotExist:
                logger.error(f"Transaction {tx_ref} not found for webhook event")
            except Exception as e:
                logger.error(f"Error processing webhook for transaction {tx_ref}: {str(e)}")

        return Response({"status": "Webhook received"}, status=status.HTTP_200_OK)

    def verify_webhook_signature(self, request):
        return settings.FLW_SECRET_HASH == request.headers.get("verif-hash")

class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]  # Apply authentication
    pagination_class = TransactionPagination
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['payment_status', 'payment_type', 'currency', 'is_outgoing']
    ordering_fields = ['timestamp', 'amount']
    ordering = ['-timestamp']  # Default ordering

    def get_queryset(self):
        user = self.request.user

        # Admins can see all transactions
        if IsAdmin().has_permission(self.request, self):
            queryset = Transaction.objects.all()

        # Managers can see transactions only for assets they manage
        elif IsManager().has_permission(self.request, self):
            managed_assets = Asset.objects.filter(managers=user)  # Assuming managers relation exists in Asset model
            queryset = Transaction.objects.filter(asset_id__in=managed_assets)

        else:
            # If the user is neither an admin nor a manager, they should not see anything
            queryset = Transaction.objects.none()

        # Search functionality
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
            serializer = TransactionSerializer(transaction)
            return Response(serializer.data, status=status.HTTP_200_OK)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TransactionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = TransactionSerializer(queryset, many=True)
        return Response(serializer.data)
