import threading
import paho.mqtt.client as mqtt
from core.models import AssetEvent, HotelRoom, Vehicle, Asset
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
import math

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
            asset_number, object_id, event_type, content_type = extract_event_info(message.topic)
            print(f"Extracted info: asset_number={asset_number}, object_id={object_id}, event_type={event_type}")

            # Check if the Asset exists
            try:
                asset = Asset.objects.get(asset_number=asset_number)
            except Asset.DoesNotExist:
                print(f"Asset with number {asset_number} does not exist.")
                return

            # Determine if it's a vehicle or hotel room based on the content_type
            if content_type == ContentType.objects.get_for_model(Vehicle):
                try:
                    vehicle = Vehicle.objects.get(vehicle_number=object_id, fleet=asset)
                    stored_object_id = vehicle.vehicle_number

                    if event_type == 'location':
                        try:
                            lat, lon = map(float, data.split(','))
                            if self.is_valid_location(lat, lon):
                                vehicle.update_location(lat, lon)
                                # Create AssetEvent for valid location
                                AssetEvent.objects.create(
                                    asset=asset,
                                    content_type=content_type,
                                    object_id=stored_object_id,
                                    event_type=event_type,
                                    data=data,
                                    timestamp=timezone.now()
                                )
                                print(f"Updated location for vehicle {object_id}: lat={lat}, lon={lon}")
                            else:
                                print(f"Invalid or potentially dangerous location data: lat={lat}, lon={lon}")
                                return
                        except ValueError:
                            print(f"Invalid GPS data format: {data}")
                            return

                    else:
                        # For non-location events, create AssetEvent as before
                        AssetEvent.objects.create(
                            asset=asset,
                            content_type=content_type,
                            object_id=stored_object_id,
                            event_type=event_type,
                            data=data,
                            timestamp=timezone.now()
                        )
                        print(f"Successfully created AssetEvent: asset_number={asset_number}, vehicle={stored_object_id}, event_type={event_type}")

                except Vehicle.DoesNotExist:
                    print(f"Vehicle with number {object_id} does not exist for asset {asset_number}.")
                    return

            elif content_type == ContentType.objects.get_for_model(HotelRoom):
                try:
                    room = HotelRoom.objects.get(room_number=object_id, hotel=asset)
                    stored_object_id = room.room_number
                     
                     # Create AssetEvent for HotelRoom
                    AssetEvent.objects.create(
                        asset=asset,
                        content_type=content_type,
                        object_id=stored_object_id,
                        event_type=event_type,
                        data=data,
                        timestamp=timezone.now()
                    )
                except HotelRoom.DoesNotExist:
                    print(f"Hotel room with number {object_id} does not exist for asset {asset_number}.")
                    return
            else:
                print(f"Unsupported content type: {content_type}")
                return

            print(f"Successfully created AssetEvent for asset_number={asset_number}, {content_type.model}={stored_object_id}")

        except Exception as e:
            print(f"Error processing message: {str(e)}")

    def is_valid_location(self, lat, lon):
        """
        Validate the latitude and longitude values.
        """
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            return False
        
        # Check for exact 0,0 coordinates (null island)
        if math.isclose(lat, 0, abs_tol=1e-8) and math.isclose(lon, 0, abs_tol=1e-8):
            return False
        
        # Additional checks can be added here, e.g., for other known problematic coordinates
        
        return True

    def run(self):
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_forever()

def extract_event_info(topic):
    """
    Extract asset_number, object_id, event_type, and content_type from the topic string.
    Example topic: "vehicles/TAS-0001-001/001/passengers"
    """
    topic_parts = topic.split('/')
    asset_type = topic_parts[0]  # 'vehicles'
    asset_number = topic_parts[1]    # 'TAS-0001-001'
    object_id = topic_parts[2]   # '001'
    event_type = topic_parts[3]  # 'passengers'

    # Determine content type based on asset type
    if asset_type == 'rooms':
        content_type = ContentType.objects.get_for_model(HotelRoom)
    elif asset_type == 'vehicles':
        content_type = ContentType.objects.get_for_model(Vehicle)
    else:
        raise ValueError("Unsupported asset type")

    return asset_number, object_id, event_type, content_type


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
