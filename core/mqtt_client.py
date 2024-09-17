import paho.mqtt.client as mqtt
import json
from django.utils import timezone
from .models import HotelRoom, Vehicle, HotelRoomHistory

# MQTT Callback functions
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    # Subscribe to relevant topics
    client.subscribe("hotel/+/status")  # Adjust topic as needed

def on_message(client, userdata, msg):
    topic_parts = msg.topic.split('/')
    asset_type = topic_parts[1]
    data = json.loads(msg.payload.decode())
    
    if asset_type == 'hotel':
        # Save the historical data
        HotelRoomHistory.objects.create(
            room=data['asset_id'],
            access=data['access'],
            utility=data['utility'],
            timestamp=timezone.now(),
            message_data=data  # Store the whole message if needed
        )
    elif asset_type == 'vehicle':
        vehicle = Vehicle.objects.get(asset_id=data['asset_id'])
        vehicle.location = data.get('location', vehicle.location)
        vehicle.timestamp = timezone.now()
        vehicle.save()

# Initialize and start the MQTT client
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

def start_mqtt():
    # Update with Mosquitto broker address and port
    client.connect("localhost", 1883, 60)  # Use the correct address if not running locally
    client.loop_start()
