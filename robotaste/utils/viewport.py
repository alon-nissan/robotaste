"""
Viewport detection and responsive sizing utilities.
Captures actual screen dimensions and calculates component sizes dynamically.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
from typing import Dict


def initialize_viewport_detection() -> Dict[str, any]:  # type: ignore
    """
    Detect and store viewport dimensions on page load.
    Returns viewport data dict with width, height, and breakpoint flags.
    """
    # Initialize with sensible defaults
    if "viewport_data" not in st.session_state:
        st.session_state.viewport_data = {
            "width": 1920,
            "height": 1080,
            "is_mobile": False,
            "is_tablet": False,
            "is_desktop": True,
            "detected": False,
        }

    # Skip if already detected this session
    if st.session_state.viewport_data.get("detected", False):
        return st.session_state.viewport_data

    try:
        from streamlit_javascript import st_javascript

        # Capture viewport dimensions
        viewport_width = st_javascript(
            "window.parent.document.documentElement.clientWidth || window.innerWidth"
        )
        viewport_height = st_javascript(
            "window.parent.document.documentElement.clientHeight || window.innerHeight"
        )

        # Only update if we got valid dimensions
        if viewport_width and viewport_height and viewport_width > 0:
            st.session_state.viewport_data = {
                "width": int(viewport_width),
                "height": int(viewport_height),
                "is_mobile": viewport_width < 768,
                "is_tablet": 768 <= viewport_width < 1024,
                "is_desktop": viewport_width >= 1024,
                "detected": True,
            }
    except ImportError:
        st.error(
            "⚠️ streamlit-javascript not installed. Run: pip install streamlit-javascript"
        )
    except Exception as e:
        # Fail silently, use defaults
        pass

    return st.session_state.viewport_data


def get_responsive_canvas_size() -> int:
    """
    Calculate optimal canvas size based on current viewport.
    Returns square canvas dimension that fits viewport without scrolling.
    """
    viewport = st.session_state.get("viewport_data", {"width": 1920, "height": 1080})

    # Get available dimensions (accounting for UI chrome)
    available_width = viewport["width"] - 100  # Margins/padding
    available_height = viewport["height"] - 300  # Header, buttons, instructions

    # Canvas must be square, so use smaller dimension
    available_space = min(available_width, available_height)

    # Default max size
    max_canvas = 500

    # Calculate responsive size
    responsive_size = min(max_canvas, int(available_space * 0.9))

    # Minimum canvas size for usability
    min_canvas = 300

    return max(min_canvas, responsive_size)


def get_responsive_font_scale() -> float:
    """
    Calculate font scale multiplier based on viewport width.
    Base: 1.0 at 1920px, scales down for smaller screens.
    """
    viewport = st.session_state.get("viewport_data", {"width": 1920})
    width = viewport["width"]

    if width < 480:
        return 0.8  # Mobile
    elif width < 768:
        return 0.85  # Large mobile
    elif width < 1024:
        return 0.9  # Tablet
    elif width < 1440:
        return 0.95  # Small desktop
    else:
        return 1.0  # Full desktop
