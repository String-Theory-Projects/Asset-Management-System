import paho.mqtt.client as mqtt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from core.models import Asset, AssetEvent, HotelRoom, Vehicle, Role
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from rest_framework.permissions import IsAuthenticated


# Configure the MQTT client
MQTT_BROKER = 'localhost'  # Replace with your MQTT broker address
MQTT_PORT = 1883  # Default MQTT port

class ControlAssetView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT)

    def post(self, request, *args, **kwargs):
        asset_id = kwargs.get('asset_id')
        sub_asset_id = kwargs.get('sub_asset_id')  # Retrieve sub_asset_id from URL
        action_type = request.data.get('action_type')
        data = request.data.get('data')

        if not asset_id or not sub_asset_id or not action_type:
            return Response({'error': 'Asset ID, sub-asset ID, and action type are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            asset = Asset.objects.get(id=asset_id)
        except Asset.DoesNotExist:
            return Response({'error': 'Asset not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure the user is an admin for the specified asset
        if not request.user.roles.filter(asset=asset, role='admin').exists():
            return Response({'error': 'You do not have permission to control this asset.'}, status=status.HTTP_403_FORBIDDEN)

        topic = None

        # Define action handling based on asset type
        if asset.asset_type == 'hotel':
            # Validate the sub-asset (room)
            try:
                room = HotelRoom.objects.get(room_number=sub_asset_id, hotel=asset)
            except HotelRoom.DoesNotExist:
                return Response({'error': 'Room not found for the specified hotel.'}, status=status.HTTP_404_NOT_FOUND)

            if action_type == 'electricity':
                topic = f"rooms/{sub_asset_id}/electricity"
            elif action_type == 'access':
                topic = f"rooms/{sub_asset_id}/access"
            else:
                return Response({'error': f'Invalid action type for {asset.asset_type} asset.'}, status=status.HTTP_400_BAD_REQUEST)

        elif asset.asset_type == 'vehicle':
            # Validate the sub-asset (vehicle)
            try:
                vehicle = Vehicle.objects.get(vehicle_number=sub_asset_id, fleet=asset)
            except Vehicle.DoesNotExist:
                return Response({'error': 'Vehicle not found for the specified fleet.'}, status=status.HTTP_404_NOT_FOUND)

            if action_type == 'ignition':
                topic = f"vehicles/{sub_asset_id}/ignition"
            else:
                return Response({'error': f'Invalid action type for {asset.asset_type} asset.'}, status=status.HTTP_400_BAD_REQUEST)

        else:
            return Response({'error': 'Invalid asset type.'}, status=status.HTTP_400_BAD_REQUEST)

        # Publish the MQTT command
        try:
            self.mqtt_client.publish(topic, data)  # Assuming `data` contains the command to send
            # Log the action with sub-asset
            AssetEvent.objects.create(
                asset=asset,
                event_type=action_type,
                data=data,
                timestamp=timezone.now(),
                content_type=ContentType.objects.get_for_model(room if asset.asset_type == 'hotel' else vehicle),
                object_id=sub_asset_id
            )
            return Response({'message': f'{action_type.capitalize()} control command sent.'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': f'Failed to send command: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CheckSubAssetStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, asset_id, sub_asset_id):
        # Validate the asset
        try:
            asset = Asset.objects.get(id=asset_id)
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

            data = {
                'last_access_command': {
                    'command': access_event.data if access_event else 'No access command found',
                    'timestamp': access_event.timestamp if access_event else None
                },
                'last_electricity_command': {
                    'command': electricity_event.data if electricity_event else 'No electricity command found',
                    'timestamp': electricity_event.timestamp if electricity_event else None
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

            data = {
                'last_ignition_command': {
                    'command': ignition_event.data if ignition_event else 'No ignition command found',
                    'timestamp': ignition_event.timestamp if ignition_event else None
                }
            }

        else:
            return Response({'error': 'Unsupported asset type.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(data, status=status.HTTP_200_OK)
