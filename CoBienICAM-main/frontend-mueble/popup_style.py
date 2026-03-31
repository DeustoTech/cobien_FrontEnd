from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp


def wrap_popup_content(content_widget, padding=22, radius=20):
    """Wrap popup content using the same visual language as main UI cards."""
    wrapper = BoxLayout(
        orientation="vertical",
        padding=dp(padding),
    )

    with wrapper.canvas.before:
        # Same as cards used across screens: white panel + dark border.
        Color(1, 1, 1, 0.85)
        bg = RoundedRectangle(pos=wrapper.pos, size=wrapper.size, radius=[dp(radius)])
        Color(0, 0, 0, 0.85)
        border = Line(
            rounded_rectangle=(wrapper.x, wrapper.y, wrapper.width, wrapper.height, dp(radius)),
            width=2,
        )

    def _sync(*_args):
        bg.pos = wrapper.pos
        bg.size = wrapper.size
        border.rounded_rectangle = (wrapper.x, wrapper.y, wrapper.width, wrapper.height, dp(radius))

    wrapper.bind(pos=_sync, size=_sync)
    wrapper.add_widget(content_widget)
    return wrapper


def popup_theme_kwargs():
    """Shared popup overlay style aligned with the furniture UI."""
    return {
        "background": "",
        "background_color": (0, 0, 0, 0.48),
        "separator_height": 0,
        "title_align": "center",
    }
