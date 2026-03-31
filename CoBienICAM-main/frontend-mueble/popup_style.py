from kivy.uix.boxlayout import BoxLayout
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.metrics import dp


def wrap_popup_content(content_widget, padding=18, radius=20):
    """Wrap popup content in a white rounded card with border."""
    wrapper = BoxLayout(
        orientation="vertical",
        padding=dp(padding),
    )

    with wrapper.canvas.before:
        Color(1, 1, 1, 1)
        bg = RoundedRectangle(pos=wrapper.pos, size=wrapper.size, radius=[dp(radius)])
        Color(0, 0, 0, 0.2)
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
    """Shared popup overlay style used across furniture UI."""
    return {
        "background": "",
        "background_color": (0, 0, 0, 0.55),
        "separator_height": 0,
        "title_align": "center",
    }

