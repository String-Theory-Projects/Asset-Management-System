from django.core.management.base import BaseCommand
import paho.mqtt.client as mqtt
import time


"""Django command to test MQTT Communication within Docker environment"""

class Command(BaseCommand):
    help = 'Test MQTT connection and publish message'

    def handle(self, *args, **kwargs):
        # Define the on_connect callback
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.stdout.write(self.style.SUCCESS('Connected with result code ' + str(rc)))
                # Publish a test message to the topic
                client.publish("test/topic", "Hello from Django!")
            else:
                self.stdout.write(self.style.ERROR('Failed to connect, result code ' + str(rc)))

        # Define the on_publish callback
        def on_publish(client, userdata, mid):
            self.stdout.write(self.style.SUCCESS(f"Message published with mid {mid}"))

        # Setup MQTT client
        client = mqtt.Client()

        # Bind callbacks
        client.on_connect = on_connect
        client.on_publish = on_publish

        # Connect to the MQTT broker
        # client.connect("mqtt", 1883, 60)  # Replace "localhost" with your broker's IP/hostname
        for _ in range(5):  # Retry up to 5 times
            try:
                client.connect("mqtt", 1883, 60)
                print("Connected to MQTT broker")
                break
            except ConnectionRefusedError:
                print("Connection refused, retrying in 5 seconds...")
                time.sleep(5)
        else:
            print("Failed to connect after 5 retries")
            exit(1)

        # Start the loop to process callbacks
        client.loop_start()

        # Wait a few seconds for the message to be published
        time.sleep(5)
        client.loop_stop()
        self.stdout.write(self.style.SUCCESS('MQTT test completed'))
