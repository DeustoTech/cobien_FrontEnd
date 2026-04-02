"""Confirmation modal shown after sending a video-call request.

This module provides a reusable Kivy popup used to acknowledge that a call
request notification has been sent to a selected contact.
"""

from typing import Any

from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Line
from translation import _


class CallConfirmationPopup(ModalView):
    """Modal confirmation popup for outgoing call-request actions.

    The popup auto-dismisses after a short timeout and can also be dismissed
    manually by the user.
    """
    
    def __init__(self, contact_name: str = "", **kwargs: Any) -> None:
        """Initialize popup content and lifecycle callbacks.

        Args:
            contact_name: Display name of the contact receiving the call request.
            **kwargs: Additional keyword arguments accepted by ``ModalView``.
        """
        super().__init__(
            size_hint=(None, None),
            size=(dp(800), dp(400)),
            auto_dismiss=True,
            background='',
            background_color=(0, 0, 0, 0.5),
            **kwargs
        )
        
        self.contact_name = contact_name
        
        # Auto-close timer handle.
        self.auto_close_timer = None
        
        self._build_content()
        
        self.bind(on_open=self._start_timer)
        self.bind(on_dismiss=self._cancel_timer)
    
    def _build_content(self) -> None:
        """Build popup layout and interactive controls.

        Returns:
            None.
        """
        
        container = BoxLayout(
            orientation='vertical',
            padding=dp(40),
            spacing=dp(30)
        )
        
        # White container with subtle border.
        with container.canvas.before:
            Color(1, 1, 1, 1)
            self.bg_rect = RoundedRectangle(
                pos=container.pos,
                size=container.size,
                radius=[dp(24)]
            )
            Color(0, 0, 0, 0.2)
            self.border_line = Line(
                rounded_rectangle=(
                    container.x, container.y,
                    container.width, container.height,
                    dp(24)
                ),
                width=3
            )
        
        container.bind(pos=self._update_bg, size=self._update_bg)
        
        # Top spacer.
        container.add_widget(BoxLayout(size_hint_y=0.2))
        
        # Primary message.
        message = Label(
            text=_("Notificación enviada"),
            font_size=sp(40),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(50)
        )
        container.add_widget(message)
        
        # Secondary message with contact name.
        if self.contact_name:
            submessage = Label(
                text=f"{self.contact_name} {_('recibirá tu llamada')}",
                font_size=sp(28),
                color=(0.3, 0.3, 0.3, 1),
                size_hint_y=None,
                height=dp(40)
            )
            container.add_widget(submessage)
        
        # Middle spacer.
        container.add_widget(BoxLayout(size_hint_y=0.3))
        
        # Confirmation button.
        btn_ok = Button(
            text="OK",
            size_hint=(None, None),
            size=(dp(200), dp(70)),
            pos_hint={'center_x': 0.5},
            background_normal='',
            background_color=(0.15, 0.55, 0.95, 1),  # Bleu
            color=(1, 1, 1, 1),
            font_size=sp(32),
            bold=True
        )
        btn_ok.bind(on_release=self._close)
        
        # Wrapper to center button.
        btn_wrapper = BoxLayout(size_hint_y=None, height=dp(70))
        btn_wrapper.add_widget(BoxLayout())
        btn_wrapper.add_widget(btn_ok)
        btn_wrapper.add_widget(BoxLayout())
        
        container.add_widget(btn_wrapper)
        
        self.add_widget(container)
    
    def _update_bg(self, instance: Any, value: Any) -> None:
        """Update background geometry when container position or size changes.

        Args:
            instance: Widget instance that triggered the callback.
            value: New Kivy property value.
        """
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        self.border_line.rounded_rectangle = (
            instance.x, instance.y,
            instance.width, instance.height,
            dp(24)
        )
    
    def _start_timer(self, *args: Any) -> None:
        """Start the auto-dismiss timer when the popup is opened.

        Args:
            *args: Kivy event callback arguments.
        """
        print("[POPUP] ⏱️ Timer auto-fermeture démarré (5s)")
        self.auto_close_timer = Clock.schedule_once(self._auto_close, 5)
    
    def _cancel_timer(self, *args: Any) -> None:
        """Cancel the auto-dismiss timer when the popup is dismissed.

        Args:
            *args: Kivy event callback arguments.
        """
        if self.auto_close_timer:
            print("[POPUP] 🛑 Timer annulé")
            self.auto_close_timer.cancel()
            self.auto_close_timer = None
    
    def _auto_close(self, dt: float) -> None:
        """Dismiss popup automatically after timeout.

        Args:
            dt: Elapsed scheduler time in seconds.
        """
        print("[POPUP] ⏰ Auto-fermeture (5s écoulées)")
        self.dismiss()
    
    def _close(self, *args: Any) -> None:
        """Dismiss popup from explicit user action.

        Args:
            *args: Kivy callback arguments.
        """
        print("[POPUP] ✅ Fermeture manuelle (bouton OK)")
        self.dismiss()


def show_call_sent_popup(contact_name: str = "") -> CallConfirmationPopup:
    """Open and return a sent-call confirmation popup.

    Args:
        contact_name: Called contact display name.

    Returns:
        Opened popup instance.

    Examples:
        >>> show_call_sent_popup("Mamie")
    """
    popup = CallConfirmationPopup(contact_name=contact_name)
    popup.open()
    return popup
