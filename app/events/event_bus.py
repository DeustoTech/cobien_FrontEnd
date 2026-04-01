# events/event_bus.py
from kivy.event import EventDispatcher

class EventBus(EventDispatcher):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_event_type('on_events_changed')

    # Event notifying changes in the events list (add/remove/edit)
    def on_events_changed(self, *args, **kwargs):
        pass

    # Call this when you finish adding/removing/editing in MongoDB
    def notify_events_changed(self):
        self.dispatch('on_events_changed')

# Instancia global y reutilizable
event_bus = EventBus()
