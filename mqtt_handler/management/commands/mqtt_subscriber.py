import threading
import paho.mqtt.client as mqtt
from core.models import AssetEvent, HotelRoom, Vehicle
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

class MQTTSubscriber(threading.Thread):
    def __init__(self, broker, port, topics):
        super().__init__()
        self.broker = broker
        self.port = port
        self.topics = topics
        self.client = mqtt.Client()

    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code: {rc}")
        for topic in self.topics:
            client.subscribe(topic)

    def on_message(self, client, userdata, message):
        data = message.payload.decode()
        print(f"Received message on {message.topic}: {data}")

        # Extract information from the topic (e.g., "rooms/101/presence")
        asset_id, object_id, event_type, content_type = extract_event_info(message.topic)

        if asset_id is None:
            print("Ignoring message due to missing asset ID.")
            return  # Skip processing if asset ID is not found

        # Log the received message in the database
        AssetEvent.objects.create(
            asset_id=asset_id,
            content_type=content_type,
            object_id=object_id,
            event_type=event_type,
            data=data,
            timestamp=timezone.now()
        )

    def run(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_forever()

def extract_event_info(topic):
    """
    Extract asset_id, object_id, event_type, and content_type from the topic string.
    Example topic: "rooms/101/presence" or "vehicles/201/ignition"
    """
    topic_parts = topic.split('/')
    asset_type = topic_parts[0]  # 'rooms' or 'vehicles'
    object_id = int(topic_parts[1])  # e.g., 101 or 201
    event_type = topic_parts[2]  # e.g., 'presence' or 'ignition'

    # Determine content type based on asset type
    if asset_type == 'rooms':
        content_type = ContentType.objects.get_for_model(HotelRoom)
    elif asset_type == 'vehicles':
        content_type = ContentType.objects.get_for_model(Vehicle)
    else:
        raise ValueError("Unsupported asset type")

    # Extract asset_id based on the asset type
    asset_id = extract_asset_id(asset_type, object_id)

    return asset_id, object_id, event_type, content_type

def extract_asset_id(asset_type, object_id):
    """
    Get the asset_id based on the object_id and asset_type.
    This function assumes that the asset_id can be determined by looking up
    the sub-asset (e.g., HotelRoom or Vehicle).
    """
    try:
        if asset_type == 'rooms':
            room = HotelRoom.objects.get(room_number=object_id)
            return room.hotel.id
        elif asset_type == 'vehicles':
            vehicle = Vehicle.objects.get(vehicle_number=object_id)
            return vehicle.fleet.id
        else:
            raise ValueError("Unsupported asset type")
    except Vehicle.DoesNotExist:
        print(f"Vehicle with ID {object_id} does not exist.")
        return None  # Or handle some other way
    except HotelRoom.DoesNotExist:
        print(f"HotelRoom with ID {object_id} does not exist.")
        return None  # Or handle some other way

def start_mqtt_subscriber():
    topics = [
        "rooms/+/occupancy",
        "rooms/+/electricity",
        "rooms/+/access",
        "vehicles/+/location",
        "vehicles/+/ignition",
        "vehicles/+/passengers",
        "vehicles/+/tampering",
        "vehicles/+/payment"
    ]
    subscriber = MQTTSubscriber("broker.emqx.io", 1883, topics) # Replace with your MQTT broker address
    subscriber.start()
