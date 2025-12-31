"""
RoboTaste UI Helper Functions

Utility functions for Streamlit UI operations.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
import time
from typing import Dict, Any


def cleanup_pending_results():
    """Clean up all pending result data from session state."""
    pending_keys = ["pending_canvas_result", "pending_slider_result", "pending_method"]

    for key in pending_keys:
        if hasattr(st.session_state, key):
            delattr(st.session_state, key)


def render_loading_spinner(message: str = "Loading...", load_time=5):
    """Render a loading spinner with a custom message."""
    with st.spinner(message):
        time.sleep(load_time)  # Small delay to ensure spinner is visible
        # Phase transition handled by calling code using state machine


def get_concentration_display(x: float, y: float, method: str) -> Dict[str, Any]:
    """
    Get formatted concentration display for UI.

    Args:
        x, y: Canvas coordinates
        method: Mapping method ('linear', 'logarithmic', 'exponential')

    Returns:
        Dictionary with concentration values and coordinates
    """
    from robotaste.core.calculations import ConcentrationMapper

    try:
        sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
            x, y, method=method
        )

        sugar_g, salt_g = ConcentrationMapper.concentrations_to_masses(
            sugar_mm, salt_mm
        )

        return {
            "sugar_mm": sugar_mm,
            "salt_mm": salt_mm,
            "sugar_g_per_100ml": sugar_g,
            "salt_g_per_100ml": salt_g,
            "coordinates": {"x": round(x, 1), "y": round(y, 1)},
        }

    except Exception as e:
        return {
            "error": f"Calculation error: {e}",
            "coordinates": {"x": round(x, 1), "y": round(y, 1)},
        }
