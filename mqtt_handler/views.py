import paho.mqtt.client as mqtt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import Asset, AssetEvent, HotelRoom, Vehicle
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
# import settings
from django.conf import settings


# Configure the MQTT client
MQTT_BROKER = 'broker.emqx.io'  # Replace with your MQTT broker address
MQTT_PORT = 1883  # Default MQTT port

User = get_user_model()
logger = logging.getLogger(__name__)

def get_system_user_token():
    system_user = User.objects.get(username='info@trykey.com')
    refresh = RefreshToken.for_user(system_user)
    return str(refresh.access_token)

class ControlAssetView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

    def post(self, request, *args, **kwargs):
        asset_number = kwargs.get('asset_number')
        sub_asset_id = kwargs.get('sub_asset_id')
        action_type = request.data.get('action_type')
        data = request.data.get('data')
        update_status = request.data.get('update_status', False) # fail-safe flag to update sub_asset status by system user in case of celery task failure

        if not asset_number or not sub_asset_id or not action_type:
            return Response({'error': 'Asset number, sub-asset ID, and action type are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            asset = Asset.objects.get(asset_number=asset_number)
        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is an admin for the specified asset or system user
        if not (request.user.is_superuser or request.user.username == 'info@trykey.com' or request.user.roles.filter(asset=asset, role='admin').exists()):
            return Response({'error': 'You do not have permission to control this asset.'}, status=status.HTTP_403_FORBIDDEN)

        topic = None

        # Define action handling based on asset type
        if asset.asset_type == 'hotel':
            # Validate the sub-asset (room)
            try:
                room = HotelRoom.objects.get(room_number=sub_asset_id, hotel=asset)
                if room.status and request.user.username != 'info@trykey.com':
                    return Response({'error': 'Cannot control an active hotel room. Please check out the guest first.'}, status=status.HTTP_400_BAD_REQUEST)
            except HotelRoom.DoesNotExist:
                return Response({'error': 'Room not found for the specified hotel.'}, status=status.HTTP_404_NOT_FOUND)

            if action_type == 'electricity':
                topic = f"rooms/{asset_number}/{sub_asset_id}/electricity"
            elif action_type == 'access':
                topic = f"rooms/{asset_number}/{sub_asset_id}/access"
            else:
                return Response({'error': f'Invalid action type for {asset.asset_type} asset.'}, status=status.HTTP_400_BAD_REQUEST)

        elif asset.asset_type == 'vehicle':
            # Validate the sub-asset (vehicle)
            try:
                vehicle = Vehicle.objects.get(vehicle_number=sub_asset_id, fleet=asset)
                if vehicle.status:
                    return Response({'error': 'Cannot control an active vehicle. Please ensure the vehicle is parked and not in use.'}, status=status.HTTP_400_BAD_REQUEST)
            except Vehicle.DoesNotExist:
                return Response({'error': 'Vehicle not found for the specified fleet.'}, status=status.HTTP_404_NOT_FOUND)

            if action_type == 'ignition':
                topic = f"vehicles/{asset_number}/{sub_asset_id}/ignition"
            else:
                return Response({'error': f'Invalid action type for {asset.asset_type} asset.'}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({'error': 'Invalid asset type.'}, status=status.HTTP_400_BAD_REQUEST)

        # Publish the MQTT command
        try:
            self.mqtt_client.publish(topic, data, retain=True)  # Assuming `data` contains the command to send
            # Log the action with sub-asset
            AssetEvent.objects.create(
                asset=asset,
                event_type=action_type,
                data=data,
                timestamp=timezone.now(),
                content_type=ContentType.objects.get_for_model(room if asset.asset_type == 'hotel' else vehicle),
                object_id=sub_asset_id
            )

            # Update room status if the flag is set
            if update_status and asset.asset_type == 'hotel':
                room = HotelRoom.objects.get(room_number=sub_asset_id, hotel=asset)
                room.status = False
                room.save()
                logger.info(f"Room status updated to False for room {sub_asset_id}")

            return Response({'message': f'{action_type.capitalize()} control command sent.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'Failed to send command: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckSubAssetStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, asset_number, sub_asset_id):
        # Validate the asset
        try:
            asset = Asset.objects.get(asset_number=asset_number)
        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is associated with the asset (admin, manager, or viewer)
        if not request.user.roles.filter(asset=asset).exists():
            return Response({'error': 'You do not have permission to access this asset.'}, status=status.HTTP_403_FORBIDDEN)

        # Determine the asset type
        if asset.asset_type == 'hotel':
            # Check the room
            try:
                room = HotelRoom.objects.get(room_number=sub_asset_id, hotel=asset)
            except HotelRoom.DoesNotExist:
                return Response({'error': 'Room not found for the specified hotel.'}, status=status.HTTP_404_NOT_FOUND)

            # Get the last access and electricity commands with timestamps
            access_event = AssetEvent.objects.filter(
                content_type=ContentType.objects.get_for_model(HotelRoom),
                object_id=sub_asset_id, event_type='access'
            ).first()
            
            electricity_event = AssetEvent.objects.filter(
                content_type=ContentType.objects.get_for_model(HotelRoom),
                object_id=sub_asset_id, event_type='electricity'
            ).first()

            # Get the last occupancy event
            occupancy_event = AssetEvent.objects.filter(
                content_type=ContentType.objects.get_for_model(HotelRoom),
                object_id=sub_asset_id, event_type='occupancy'
            ).first()

            data = {
                'last_access_command': {
                    'command': access_event.data if access_event else 'No access command found',
                    'timestamp': access_event.timestamp if access_event else None
                },
                'last_electricity_command': {
                    'command': electricity_event.data if electricity_event else 'No electricity command found',
                    'timestamp': electricity_event.timestamp if electricity_event else None
                },
                'last_occupancy': {
                    'status': occupancy_event.data if occupancy_event else 'No occupancy data found',
                    'timestamp': occupancy_event.timestamp if occupancy_event else None
                }
            }

        elif asset.asset_type == 'vehicle':
            # Check the vehicle
            try:
                vehicle = Vehicle.objects.get(vehicle_number=sub_asset_id, fleet=asset)
            except Vehicle.DoesNotExist:
                return Response({'error': 'Vehicle not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Get the last ignition command with timestamp
            ignition_event = AssetEvent.objects.filter(
                content_type=ContentType.objects.get_for_model(Vehicle),
                object_id=sub_asset_id, event_type='ignition'
            ).first()

            # Get the last passenger count event
            passenger_count_event = AssetEvent.objects.filter(
                content_type=ContentType.objects.get_for_model(Vehicle),
                object_id=sub_asset_id, event_type='passenger_count'
            ).first()

            # Get the last location event
            location_event = AssetEvent.objects.filter(
                content_type=ContentType.objects.get_for_model(Vehicle),
                object_id=sub_asset_id, event_type='location'
            ).first()

            data = {
                'last_ignition_command': {
                    'command': ignition_event.data if ignition_event else 'No ignition command found',
                    'timestamp': ignition_event.timestamp if ignition_event else None
                },
                'last_passenger_count': {
                    'count': passenger_count_event.data if passenger_count_event else 'No passenger count data found',
                    'timestamp': passenger_count_event.timestamp if passenger_count_event else None
                },
                'last_location': {
                    'location': location_event.data if location_event else 'No location data found',
                    'timestamp': location_event.timestamp if location_event else None
                },
                'total_distance': {
                    'value': vehicle.total_distance,
                    'unit': 'kilometers'
                }
            }

        else:
            return Response({'error': 'Unsupported asset type.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)


class CheckAssetStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, asset_number):
        try:
            asset = Asset.objects.get(asset_number=asset_number)
        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is associated with the asset
        if not request.user.roles.filter(asset=asset).exists():
            return Response({'error': 'You do not have permission to access this asset.'}, status=status.HTTP_403_FORBIDDEN)

        # Get the time range from query parameters, default to last 7 days
        days = int(request.query_params.get('days', 7))
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        if asset.asset_type == 'hotel':
            return self.get_hotel_data(asset, start_date, end_date)
        elif asset.asset_type == 'vehicle':
            return self.get_vehicle_data(asset, start_date, end_date)
        else:
            return Response({'error': 'Unsupported asset type.'}, status=status.HTTP_400_BAD_REQUEST)

    def get_hotel_data(self, asset, start_date, end_date):
        total_rooms = HotelRoom.objects.filter(hotel=asset).count()
        
        # Get current day stats
        current_date = timezone.now().date()
        total_active_rooms = HotelRoom.objects.filter(
            hotel=asset,
            status=True
        ).count()

        occupied_rooms = AssetEvent.objects.filter(
            asset=asset,
            event_type='occupancy',
            timestamp__date=current_date,
            data='1'
        ).values('object_id').distinct()

        total_occupied_rooms = occupied_rooms.count()

        # Calculate expected yield
        expected_yield = HotelRoom.objects.filter(
            hotel=asset,
            room_number__in=occupied_rooms.values_list('object_id', flat=True)
        ).aggregate(total_price=Sum('price'))['total_price'] or 0

        # Get daily stats
        daily_stats = []
        current_date = start_date
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            occupied_rooms = AssetEvent.objects.filter(
                asset=asset,
                event_type='occupancy',
                timestamp__lt=next_date,
                timestamp__gte=current_date,
                data='1'
            ).values('object_id').distinct()

            daily_occupied_count = occupied_rooms.count()

            active_rooms = HotelRoom.objects.filter(
                hotel=asset,
                status=True
            ).count()

            daily_expected_yield = HotelRoom.objects.filter(
                hotel=asset,
                room_number__in=occupied_rooms.values_list('object_id', flat=True)
            ).aggregate(total_price=Sum('price'))['total_price'] or 0

            daily_stats.append({
                'date': current_date.date(),
                'occupied_rooms': daily_occupied_count,
                'active_rooms': active_rooms,
                'expected_yield': daily_expected_yield
            })
            current_date = next_date

        return Response({
            'total_rooms': total_rooms,
            'total_active_rooms': total_active_rooms,
            'total_occupied_rooms': total_occupied_rooms,
            'expected_yield': expected_yield,
            'daily_stats': daily_stats
        })

    def get_vehicle_data(self, asset, start_date, end_date):
        total_vehicles = Vehicle.objects.filter(fleet=asset).count()
        
        # Get current day stats
        current_date = timezone.now().date()
        total_active_vehicles = Vehicle.objects.filter(
            fleet=asset,
            status=True
        ).count()

        total_in_use_vehicles = AssetEvent.objects.filter(
            asset=asset,
            content_type=ContentType.objects.get_for_model(Vehicle),
            timestamp__date=current_date
        ).values('object_id').distinct().count()

        # Get daily stats
        daily_stats = []
        current_date = start_date
        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            active_vehicles = Vehicle.objects.filter(
                fleet=asset,
                status=True
            ).count()

            # Count vehicles with events on this day
            vehicles_with_events = AssetEvent.objects.filter(
                asset=asset,
                content_type=ContentType.objects.get_for_model(Vehicle),
                timestamp__gte=current_date,
                timestamp__lt=next_date
            ).values('object_id').distinct().count()

            daily_stats.append({
                'date': current_date.date(),
                'active_vehicles': active_vehicles,
                'vehicles_with_events': vehicles_with_events
            })
            current_date = next_date

        return Response({
            'total_vehicles': total_vehicles,
            'total_active_vehicles': total_active_vehicles,
            'total_in_use_vehicles': total_in_use_vehicles,
            'daily_stats': daily_stats
        })
