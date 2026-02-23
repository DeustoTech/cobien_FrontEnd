# events/event_bus.py
from kivy.event import EventDispatcher

class EventBus(EventDispatcher):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_event_type('on_events_changed')

    # Evento que notifica cambios en la lista de eventos (altas/bajas/ediciones)
    def on_events_changed(self, *args, **kwargs):
        pass

    # Llamar a esto cuando termines de añadir/eliminar/editar en Mongo
    def notify_events_changed(self):
        self.dispatch('on_events_changed')

# Instancia global y reutilizable
event_bus = EventBus()
