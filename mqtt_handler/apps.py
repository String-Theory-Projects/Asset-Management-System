from django.apps import AppConfig

class MqttHandlerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mqtt_handler'

    def ready(self):
        from .management.commands.mqtt_subscriber import start_mqtt_subscriber
        start_mqtt_subscriber()  # Start the MQTT subscriber thread
