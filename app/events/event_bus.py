"""Application-level event bus for events module synchronization.

This module provides a lightweight reusable Kivy `EventDispatcher` used to
notify UI screens when event data changes (add/update/delete) and a refresh of
calendar/day views is required.
"""

from typing import Any
from kivy.event import EventDispatcher

class EventBus(EventDispatcher):
    """In-process pub/sub dispatcher for events-related refresh notifications."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the dispatcher and register custom event types.

        Args:
            **kwargs: Additional Kivy `EventDispatcher` keyword arguments.
        """
        super().__init__(**kwargs)
        self.register_event_type('on_events_changed')

    def on_events_changed(self, *args: Any, **kwargs: Any) -> None:
        """Default callback invoked when events data changes.

        Args:
            *args: Event positional payload.
            **kwargs: Event keyword payload.

        Returns:
            None.

        Examples:
            >>> # event_bus.bind(on_events_changed=my_refresh_handler)
        """
        pass

    def notify_events_changed(self) -> None:
        """Dispatch `on_events_changed` to all listeners.

        Returns:
            None.

        Examples:
            >>> event_bus.notify_events_changed()
        """
        self.dispatch('on_events_changed')

# Global reusable singleton instance.
event_bus = EventBus()
