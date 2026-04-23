"""Popups used by the outgoing video-call request flow."""

from typing import Any

from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle, Line
from translation import _


class CallRequestProgressPopup(ModalView):
    """Blocking progress popup shown while the call request is being sent."""

    def __init__(self, contact_name: str = "", **kwargs: Any) -> None:
        super().__init__(
            size_hint=(None, None),
            size=(dp(900), dp(430)),
            auto_dismiss=False,
            background='',
            background_color=(0, 0, 0, 0.5),
            **kwargs
        )
        self.contact_name = contact_name
        self._pulse_event = None
        self._pulse_step = 0
        self._build_content()
        self.bind(on_open=self._start_pulse, on_dismiss=self._stop_pulse)

    def _build_content(self) -> None:
        container = BoxLayout(
            orientation='vertical',
            padding=dp(40),
            spacing=dp(24)
        )

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
        container.add_widget(BoxLayout(size_hint_y=0.15))

        title = Label(
            text=_("Solicitando videollamada"),
            font_size=sp(40),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(54)
        )
        container.add_widget(title)

        subtitle = _("Espera un momento…")
        if self.contact_name:
            subtitle = f"{_('Solicitando llamada con')} {self.contact_name}"

        self.message_label = Label(
            text=subtitle,
            font_size=sp(28),
            color=(0.3, 0.3, 0.3, 1),
            size_hint_y=None,
            height=dp(44)
        )
        container.add_widget(self.message_label)

        self.status_label = Label(
            text=_("Enviando solicitud"),
            font_size=sp(34),
            color=(0.1, 0.1, 0.1, 1),
            size_hint_y=None,
            height=dp(52)
        )
        container.add_widget(self.status_label)

        container.add_widget(BoxLayout(size_hint_y=0.35))

        cancel_hint = Label(
            text=_("La pantalla se actualizará cuando haya respuesta"),
            font_size=sp(22),
            color=(0.4, 0.4, 0.4, 1),
            size_hint_y=None,
            height=dp(36)
        )
        container.add_widget(cancel_hint)
        self.add_widget(container)

    def _update_bg(self, instance: Any, value: Any) -> None:
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        self.border_line.rounded_rectangle = (
            instance.x, instance.y,
            instance.width, instance.height,
            dp(24)
        )

    def _tick_pulse(self, _dt: float) -> None:
        dots = "." * ((self._pulse_step % 3) + 1)
        self.status_label.text = f"{_('Enviando solicitud')}{dots}"
        self._pulse_step += 1

    def _start_pulse(self, *_args: Any) -> None:
        self._pulse_step = 0
        self._tick_pulse(0)
        self._pulse_event = Clock.schedule_interval(self._tick_pulse, 0.55)

    def _stop_pulse(self, *_args: Any) -> None:
        if self._pulse_event is not None:
            self._pulse_event.cancel()
            self._pulse_event = None


class CallResultPopup(ModalView):
    """Result popup shown after the outbound request finishes."""

    def __init__(
        self,
        title_text: str,
        message_text: str = "",
        detail_text: str = "",
        accent_color=(0.15, 0.55, 0.95, 1),
        **kwargs: Any
    ) -> None:
        super().__init__(
            size_hint=(None, None),
            size=(dp(860), dp(520)),
            auto_dismiss=True,
            background='',
            background_color=(0, 0, 0, 0.5),
            **kwargs
        )
        self.title_text = title_text
        self.message_text = message_text
        self.detail_text = detail_text
        self.accent_color = accent_color
        self.auto_close_timer = None
        self._details_visible = False
        self._build_content()
        self.bind(on_open=self._start_timer)
        self.bind(on_dismiss=self._cancel_timer)

    def _build_content(self) -> None:
        container = BoxLayout(
            orientation='vertical',
            padding=dp(40),
            spacing=dp(30)
        )

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
        container.add_widget(BoxLayout(size_hint_y=0.18))
        container.add_widget(Label(
            text=self.title_text,
            font_size=sp(40),
            bold=True,
            color=(0, 0, 0, 1),
            size_hint_y=None,
            height=dp(50)
        ))

        if self.message_text:
            container.add_widget(Label(
                text=self.message_text,
                font_size=sp(28),
                color=(0.3, 0.3, 0.3, 1),
                size_hint_y=None,
                height=dp(70)
            ))

        if self.detail_text:
            self.details_toggle_btn = Button(
                text=_("Mostrar detalles"),
                size_hint=(None, None),
                size=(dp(320), dp(64)),
                pos_hint={'center_x': 0.5},
                background_normal='',
                background_color=(0.65, 0.65, 0.65, 1),
                color=(1, 1, 1, 1),
                font_size=sp(26),
                bold=True
            )
            self.details_toggle_btn.bind(on_release=self._toggle_details)
            toggle_wrapper = BoxLayout(size_hint_y=None, height=dp(64))
            toggle_wrapper.add_widget(BoxLayout())
            toggle_wrapper.add_widget(self.details_toggle_btn)
            toggle_wrapper.add_widget(BoxLayout())
            container.add_widget(toggle_wrapper)

            self.details_label = Label(
                text="",
                font_size=sp(22),
                color=(0.35, 0.35, 0.35, 1),
                size_hint_y=None,
                height=0,
                opacity=0,
            )
            self.details_label.bind(size=lambda inst, value: setattr(inst, "text_size", value))
            container.add_widget(self.details_label)

        container.add_widget(BoxLayout(size_hint_y=0.3))

        btn_ok = Button(
            text="OK",
            size_hint=(None, None),
            size=(dp(220), dp(72)),
            pos_hint={'center_x': 0.5},
            background_normal='',
            background_color=self.accent_color,
            color=(1, 1, 1, 1),
            font_size=sp(32),
            bold=True
        )
        btn_ok.bind(on_release=self._close)

        btn_wrapper = BoxLayout(size_hint_y=None, height=dp(72))
        btn_wrapper.add_widget(BoxLayout())
        btn_wrapper.add_widget(btn_ok)
        btn_wrapper.add_widget(BoxLayout())
        container.add_widget(btn_wrapper)
        self.add_widget(container)

    def _update_bg(self, instance: Any, value: Any) -> None:
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        self.border_line.rounded_rectangle = (
            instance.x, instance.y,
            instance.width, instance.height,
            dp(24)
        )

    def _start_timer(self, *args: Any) -> None:
        self.auto_close_timer = Clock.schedule_once(self._auto_close, 5)

    def _cancel_timer(self, *args: Any) -> None:
        if self.auto_close_timer:
            self.auto_close_timer.cancel()
            self.auto_close_timer = None

    def _auto_close(self, dt: float) -> None:
        self.dismiss()

    def _close(self, *args: Any) -> None:
        self.dismiss()

    def _toggle_details(self, *_args: Any) -> None:
        self._details_visible = not self._details_visible
        if self._details_visible:
            self.details_toggle_btn.text = _("Ocultar detalles")
            self.details_label.text = self.detail_text
            self.details_label.height = dp(120)
            self.details_label.opacity = 1
            return

        self.details_toggle_btn.text = _("Mostrar detalles")
        self.details_label.text = ""
        self.details_label.height = 0
        self.details_label.opacity = 0


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
        print("[POPUP] Auto-close timer started (5s)")
        self.auto_close_timer = Clock.schedule_once(self._auto_close, 5)
    
    def _cancel_timer(self, *args: Any) -> None:
        """Cancel the auto-dismiss timer when the popup is dismissed.

        Args:
            *args: Kivy event callback arguments.
        """
        if self.auto_close_timer:
            print("[POPUP] Timer cancelled")
            self.auto_close_timer.cancel()
            self.auto_close_timer = None
    
    def _auto_close(self, dt: float) -> None:
        """Dismiss popup automatically after timeout.

        Args:
            dt: Elapsed scheduler time in seconds.
        """
        print("[POPUP] Auto-close triggered (5s elapsed)")
        self.dismiss()
    
    def _close(self, *args: Any) -> None:
        """Dismiss popup from explicit user action.

        Args:
            *args: Kivy callback arguments.
        """
        print("[POPUP] Manual close (OK button)")
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


def show_call_request_progress_popup(contact_name: str = "") -> CallRequestProgressPopup:
    popup = CallRequestProgressPopup(contact_name=contact_name)
    popup.open()
    return popup


def show_call_failed_popup(contact_name: str = "", error_code: str = "", detail: str = "") -> CallResultPopup:
    message = _("No se ha podido enviar la solicitud de videollamada.")
    if contact_name:
        message = f"{message}\n{contact_name}"
    detail_lines = []
    if error_code:
        detail_lines.append(f"{_('Código')}: {error_code}")
    if detail:
        detail_lines.append(detail)
    popup = CallResultPopup(
        title_text=_("Solicitud no enviada"),
        message_text=message,
        detail_text="\n".join(detail_lines),
        accent_color=(0.85, 0.18, 0.18, 1),
    )
    popup.open()
    return popup
