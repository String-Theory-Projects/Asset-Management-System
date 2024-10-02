import threading
import paho.mqtt.client as mqtt
from core.models import AssetEvent, HotelRoom, Vehicle, Asset
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
            print(f"Subscribed to topic: {topic}")

    def on_message(self, client, userdata, message):
        data = message.payload.decode()
        print(f"Received message on {message.topic}: {data}")

        try:
            asset_id, object_id, event_type, content_type = extract_event_info(message.topic)
            print(f"Extracted info: asset_id={asset_id}, object_id={object_id}, event_type={event_type}")

            # Check if the Asset exists
            try:
                asset = Asset.objects.get(id=asset_id)
            except Asset.DoesNotExist:
                print(f"Asset with ID {asset_id} does not exist.")
                return

            # Determine if it's a vehicle or hotel room based on the content_type
            if content_type == ContentType.objects.get_for_model(Vehicle):
                try:
                    vehicle = Vehicle.objects.get(vehicle_number=object_id, fleet=asset)
                    stored_object_id = vehicle.vehicle_number

                    if event_type == 'location':
                        # Parse the GPS coordinates
                        try:
                            lat, lon = map(float, data.split(','))
                            vehicle.update_location(lat, lon)
                            print(f"Updated location for vehicle {object_id}: lat={lat}, lon={lon}")
                        except ValueError:
                            print(f"Invalid GPS data format: {data}")
                            return

                except Vehicle.DoesNotExist:
                    print(f"Vehicle with number {object_id} does not exist for asset {asset_id}.")
                    return

            elif content_type == ContentType.objects.get_for_model(HotelRoom):
                try:
                    room = HotelRoom.objects.get(room_number=object_id, hotel=asset)
                    stored_object_id = room.room_number
                except HotelRoom.DoesNotExist:
                    print(f"Hotel room with number {object_id} does not exist for asset {asset_id}.")
                    return
            else:
                print(f"Unsupported content type: {content_type}")
                return

            AssetEvent.objects.create(
                asset=asset,
                content_type=content_type,
                object_id=stored_object_id,
                event_type=event_type,
                data=data,
                timestamp=timezone.now()
            )
            print(f"Successfully created AssetEvent for asset_id={asset_id}, {content_type.model}={stored_object_id}")

        except Exception as e:
            print(f"Error processing message: {str(e)}")

    def run(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_forever()

def extract_event_info(topic):
    """
    Extract asset_id, object_id, event_type, and content_type from the topic string.
    Example topic: "vehicles/AMS11120/999/passengers"
    """
    topic_parts = topic.split('/')
    asset_type = topic_parts[0]  # 'vehicles'
    asset_id = topic_parts[1]    # 'AMS11120'
    object_id = topic_parts[2]   # '999'
    event_type = topic_parts[3]  # 'passengers'

    # Determine content type based on asset type
    if asset_type == 'rooms':
        content_type = ContentType.objects.get_for_model(HotelRoom)
    elif asset_type == 'vehicles':
        content_type = ContentType.objects.get_for_model(Vehicle)
    else:
        raise ValueError("Unsupported asset type")

    return asset_id, object_id, event_type, content_type


def start_mqtt_subscriber():
    topics = [
        "rooms/+/+/occupancy",
        "rooms/+/+/electricity",
        "rooms/+/+/access",
        "vehicles/+/+/location",
        "vehicles/+/+/ignition",
        "vehicles/+/+/passenger_count",
        "vehicles/+/+/tampering",
        "vehicles/+/+/payment"
    ]
    subscriber = MQTTSubscriber("broker.emqx.io", 1883, topics) # Replace with your MQTT broker address
    subscriber.start()
