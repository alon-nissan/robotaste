"""
Hardware control module for RoboTaste.

This package provides interfaces for controlling physical hardware components
like syringe pumps used in automated liquid dispensing.
"""

from .pump_controller import NE4000Pump, PumpConnectionError, PumpCommandError, PumpTimeoutError

__all__ = [
    'NE4000Pump',
    'PumpConnectionError',
    'PumpCommandError',
    'PumpTimeoutError',
]
