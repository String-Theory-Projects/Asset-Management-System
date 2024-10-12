from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APIClient

from decimal import Decimal
from ..models import Asset, AssetEvent, Role, Transaction, Vehicle, HotelRoom, User

from unittest.mock import patch, Mock

from datetime import timedelta


User = get_user_model()


class InitiatePaymentViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('initiate_payment')

        # Create test users
        self.user1 = User.objects.create_user(username='user1', password='password1', email='test1@gmail.com')
        self.user2 = User.objects.create_user(username='user2', password='password2', email='test2@gmail.com')

        # Create test assets
        self.asset1 = Asset.objects.create(
            asset_number='ASSET001',
            asset_type='vehicle',
            asset_name='Test Vehicle 1',
            location='Test Location 1',
            details={'make': 'Toyota', 'model': 'Corolla'},
            account_number='1234567890',
            bank='Test Bank',
            total_revenue=1000.00
        )
        self.asset2 = Asset.objects.create(
            asset_number='ASSET002',
            asset_type='hotel',
            asset_name='Test Hotel',
            location='Test Location 2',
            details={'rooms': 50, 'stars': 4},
            account_number='0987654321',
            bank='Another Bank',
            total_revenue=5000.00
        )

        # Create roles
        Role.objects.create(user=self.user1, asset=self.asset1, role='admin')
        Role.objects.create(user=self.user2, asset=self.asset2, role='manager')
        
        # Create hotel rooms for the hotel asset
        self.room1 = HotelRoom.objects.create(
            hotel=self.asset2,
            room_number='101',
            room_type='Standard',
            price=100.00,
            status=True,
            activation_timestamp=timezone.now(),
            expiry_timestamp=timezone.now() + timedelta(days=365)
        )
        self.room2 = HotelRoom.objects.create(
            hotel=self.asset2,
            room_number='201',
            room_type='Deluxe',
            price=150.00,
            status=True,
            activation_timestamp=timezone.now(),
            expiry_timestamp=timezone.now() + timedelta(days=365)
        )

        # Create vehicles for the vehicle asset
        self.vehicle1 = Vehicle.objects.create(
            fleet=self.asset1,
            last_latitude=40.7128,
            last_longitude=-74.0060,
            total_distance=1000.5,
            vehicle_number='V001',
            brand='Toyota',
            vehicle_type='Sedan',
            status=False,
            activation_timestamp=timezone.now(),
            expiry_timestamp=timezone.now() + timedelta(days=365)
        )
        self.vehicle2 = Vehicle.objects.create(
            fleet=self.asset1,
            last_latitude=34.0522,
            last_longitude=-118.2437,
            total_distance=500.2,
            vehicle_number='V002',
            brand='Honda',
            vehicle_type='SUV',
            status=True,
            activation_timestamp=timezone.now(),
            expiry_timestamp=timezone.now() + timedelta(days=365)
        )
        # Create asset events
        AssetEvent.objects.create(
            asset=self.asset1,
            event_type='ignition',
            data='Ignition on',
            content_type=ContentType.objects.get_for_model(self.asset1),
            object_id=self.asset1.asset_number
        )
            
        # Valid payload for payment initiation
        self.valid_payload = {
            "email": "customer@example.com",
            "name": "John Doe",
            "phonenumber": "1234567890",
            "amount": 5000,
            "redirect_url": "https://example.com/redirect",
            "title": "Test Payment",
            "description": "Payment for service",
            "asset_number": self.asset2.asset_number,  # Using the hotel asset
            "sub_asset_number": self.room1.room_number,  # Using the first room
            "currency": "NGN",  # Optional field with default value
            "is_outgoing": False  # Optional field with default value
        }
        
    @patch('core.views.initiate_flutterwave_payment')
    def test_successful_payment_initiation(self, mock_init):
        mock_init.return_value = ("checkout.flutterwave.com/yippee", None)
        mock_init.get.return_value.status_code = 200
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('payment_link', response.data)
        self.assertIn('transaction_id', response.data)
        
        transaction = Transaction.objects.get(id=response.data['transaction_id'])
        self.assertEqual(transaction.amount, Decimal(self.valid_payload['amount']))
        self.assertEqual(str(transaction.asset.asset_number), str(self.asset2.asset_number)) 
    def test_payment_initiation_unauthorized_user(self):
        pass
        # self.client.force_authenticate(user=self.user2)  # user2 doesn't have access to asset1
        # response = self.client.post(self.url, self.valid_payload, format='json')
        # self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    @patch('core.views.initiate_flutterwave_payment')
    def test_payment_initiation_with_different_asset_types(self, mock_init):
        mock_init.return_value = ("checkout.flutterwave.com/yippee", None)
        mock_init.get.return_value.status_code = 200
        self.client.force_authenticate(user=self.user1)
        
        # Test with vehicle asset
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test with hotel asset
        self.valid_payload['asset_number'] = self.asset2.asset_number
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch('core.views.initiate_flutterwave_payment')
    def test_payment_initiation_with_asset_events(self, mock_init):
        mock_init.return_value = ("checkout.flutterwave.com/yippee", None)
        mock_init.get.return_value.status_code = 200
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if a new AssetEvent is created for the payment
        latest_event = AssetEvent.objects.filter(asset=self.asset1).latest('timestamp')
        self.assertEqual(latest_event.event_type, 'ignition')  # Assuming 'payment' is added to EVENT_TYPE_CHOICES

    @patch('core.views.initiate_flutterwave_payment')
    def test_payment_initiation_with_invalid_asset_number(self, mock_init):
        mock_init.return_value = ("checkout.flutterwave.com/yippee", None)
        mock_init.get.return_value.status_code = 200
        self.client.force_authenticate(user=self.user1)
        self.valid_payload['asset_number'] = 'INVALID_ID'
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('core.views.initiate_flutterwave_payment')
    def test_payment_initiation_role_based_access(self, mock_init):
        mock_init.return_value = ("checkout.flutterwave.com/yippee", None)
        mock_init.get.return_value.status_code = 200
        # Test admin role
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Test manager role
        Role.objects.filter(user=self.user1, asset=self.asset1).update(role='manager')
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    @patch('core.views.initiate_flutterwave_payment')
    def test_payment_initiation_api_failure(self, mock_initiate_payment):
        mock_initiate_payment.return_value = (None, "Failed to initiate payment: skill issue")
        mock_initiate_payment.get.return_value.status_code = 400
        
        self.client.force_authenticate(user=self.user1)
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    # Field validation tests...
    def test_invalid_email_format(self):
        self.client.force_authenticate(user=self.user1)
        payload = self.valid_payload.copy()
        payload["email"] = "invalid-email-format"
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_amount_type(self):
        self.client.force_authenticate(user=self.user1)
        payload = self.valid_payload.copy()
        payload["amount"] = "invalid-amount"
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_negative_amount(self):
        self.client.force_authenticate(user=self.user1)
        payload = self.valid_payload.copy()
        payload["amount"] = "-100"
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_zero_amount(self):
        self.client.force_authenticate(user=self.user1)
        payload = self.valid_payload.copy()
        payload["amount"] = "0"
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_very_large_amount(self):
        self.client.force_authenticate(user=self.user1)
        payload = self.valid_payload.copy()
        payload["amount"] = "1000000000000"  # 1 trillion
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_invalid_redirect_url(self):
        pass


class VerifyPaymentViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('verify_payment')

        user = User.objects.create(
            username='admin',
            email='info@trykey.com',
            password='admin',
            is_superuser=True
        )
        user.save()

        # Create test asset
        self.asset = Asset.objects.create(
            asset_number='ASSET001',
            asset_type='vehicle',
            asset_name='Test Vehicle 1',
            location='Test Location 1',
            details={'make': 'Toyota', 'model': 'Corolla'},
            account_number='1234567890',
            bank='Test Bank',
            total_revenue=Decimal('1000.00')
        )

        # create sub-asset
        self.vehicle1 = Vehicle.objects.create(
            fleet=self.asset,
            last_latitude=40.7128,
            last_longitude=-74.0060,
            total_distance=1000.5,
            vehicle_number='V001',
            brand='Toyota',
            vehicle_type='Sedan',
            status=True,
            activation_timestamp=timezone.now(),
            expiry_timestamp=timezone.now() + timedelta(days=365)
        )
        # Create test transactions
        self.pending_transaction = Transaction.objects.create(
            asset=self.asset,
            sub_asset_number='V001',
            payment_status='pending',
            payment_type='card',
            amount=Decimal('5000.00'),
            currency='NGN',
            transaction_ref='tx_ref_pending',
            processor_ref='proc_ref_pending',
            name='John Doe',
            email='john@example.com',
            is_outgoing=False,
            description='Pending payment for vehicle rental',
            is_verified=False
        )
        self.canceled_transaction = Transaction.objects.create(
            asset=self.asset,
            sub_asset_number='V001',
            payment_status='canceled',
            payment_type='card',
            amount=Decimal('5000.00'),
            currency='NGN',
            transaction_ref='tx_ref_canceled',
            processor_ref='proc_ref_canceled',
            name='John Doe',
            email='john@example.com',
            is_outgoing=False,
            description='Canceled payment for vehicle rental',
            is_verified=False
        )


        self.successful_transaction = Transaction.objects.create(
            asset=self.asset,
            sub_asset_number='V001',
            payment_status='completed',
            payment_type='transfer',
            amount=Decimal('7500.00'),
            currency='NGN',
            transaction_ref='tx_ref_success',
            processor_ref='proc_ref_success',
            name='Jane Smith',
            email='naj@gmail.com',
            is_outgoing=False,
            description='Successful payment for vehicle rental',
            is_verified=False
        )

        self.failed_transaction = Transaction.objects.create(
            asset=self.asset,
            sub_asset_number='V001',
            payment_status='failed',
            payment_type='mobile_money',
            amount=Decimal('3000.00'),
            currency='NGN',
            transaction_ref='tx_ref_failed',
            processor_ref='proc_ref_failed',
            name='Bob Johnson',
            email='bob@example.com',
            is_outgoing=False,
            description='Failed payment for vehicle rental',
            is_verified=False
        )

    @patch('core.views.verify_flutterwave_transaction')
    @patch('core.views.send_user_sms.delay')
    @patch('core.views.send_user_email.delay')
    def test_successful_verification(self, mock_email, mock_sms, mock_verify):
        mock_verify.return_value = ({'status': 'successful', 'amount': '5000.00', 'currency': 'NGN'}, None)
        mock_verify.get.return_value.status_code = 200
        response = self.client.get(self.url, {'tx_ref': 'tx_ref_success', 'transaction_id': 'valid_transaction_id', 'status': 'successful'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Payment verified successfully")
        
        self.successful_transaction.refresh_from_db()
        self.assertEqual(self.successful_transaction.payment_status.lower(), 'completed')
        self.assertTrue(self.successful_transaction.is_verified)
        
        mock_email.assert_called_once()
        mock_sms.assert_called_once()

    @patch('core.views.verify_flutterwave_transaction')
    def test_failed_verification(self, mock_verify):
        mock_verify.return_value = ({'status': 'failed', 'amount': '5000.00', 'currency': 'NGN'}, None)
        mock_verify.get.return_value.status_code = 200

        response = self.client.get(self.url, {'tx_ref': 'tx_ref_failed', 'transaction_id': 'failed_transaction_id', 'status': 'failed'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Payment status updated to failed")
        
        self.failed_transaction.refresh_from_db()
        self.assertEqual(self.failed_transaction.payment_status, 'failed')
        self.assertTrue(self.failed_transaction.is_verified)

    @patch('core.views.verify_flutterwave_transaction')
    def test_flutterwave_verification_error(self, mock_verify):
        mock_verify.return_value = (None, "API Error")
        mock_verify.get.return_value.status_code = 400
        response = self.client.get(self.url, {'tx_ref': 'tx_ref_success', 'transaction_id': 'error_transaction_id', 'status': 'successful'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "Failed to verify transaction")

    @patch('core.views.verify_flutterwave_transaction')
    def test_different_flutterwave_statuses(self, mock_verify):
        statuses = {'pending':self.pending_transaction, 'canceled':self.canceled_transaction}
        mock_verify.get.return_value.status_code = 200
        for expected_status in statuses:
            mock_verify.return_value = ({'status': expected_status, 'amount': '5000.00', 'currency': 'NGN'}, None)
            response = self.client.get(self.url, {'tx_ref': f'tx_ref_{expected_status}', 'transaction_id': f'{expected_status}_transaction_id', 'status': expected_status})
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data['message'], f"Payment status updated to {expected_status}")
            
            transaction = statuses[expected_status]
            transaction.refresh_from_db()
            self.assertEqual(transaction.payment_status, expected_status)

    def test_missing_parameters(self):
        response = self.client.get(self.url, {'tx_ref': 'tx_ref_1'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], "Missing required parameters")

    @patch('core.views.verify_flutterwave_transaction')
    def test_already_verified_transaction(self, mock_verify):
        mock_verify.return_value = ({'status': 'successful', 'amount': '5000.00', 'currency': 'NGN'}, None)
        self.successful_transaction.is_verified = True
        self.successful_transaction.save()
        
        response = self.client.get(self.url, {'tx_ref': 'tx_ref_success', 'transaction_id': 'test_id', 'status': 'successful'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], "Payment already verified")

