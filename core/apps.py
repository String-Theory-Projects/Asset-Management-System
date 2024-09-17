from django.apps import AppConfig

class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from .mqtt_client import start_mqtt
        import core.signals 
        start_mqtt()
