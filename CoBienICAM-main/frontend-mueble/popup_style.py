from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp


def wrap_popup_content(content_widget, padding=28, radius=24):
    """Wrap popup content using the same visual language as AssistantOverlay."""
    wrapper = BoxLayout(
        orientation="vertical",
        padding=dp(padding),
    )

    with wrapper.canvas.before:
        # AssistantOverlay uses a soft white card over dark overlay.
        Color(1, 1, 1, 0.98)
        bg = RoundedRectangle(pos=wrapper.pos, size=wrapper.size, radius=[dp(radius)])

    def _sync(*_args):
        bg.pos = wrapper.pos
        bg.size = wrapper.size

    wrapper.bind(pos=_sync, size=_sync)
    wrapper.add_widget(content_widget)
    return wrapper


def popup_theme_kwargs():
    """Shared popup overlay style used across furniture UI (AssistantOverlay-like)."""
    return {
        "background": "",
        "background_color": (0, 0, 0, 0.55),
        "separator_height": 0,
        "title_align": "center",
    }
