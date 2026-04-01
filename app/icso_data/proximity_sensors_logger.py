"""Compatibility wrapper for legacy module naming.

The project uses ``proximity_sensor_logger.py`` (singular) as the real
implementation. Some documentation and external integrations refer to
``proximity_sensors_logger.py`` (plural). This wrapper keeps both names
working and points to the same functions.
"""

from .proximity_sensor_logger import *  # noqa: F401,F403

