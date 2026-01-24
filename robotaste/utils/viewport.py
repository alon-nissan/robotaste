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

    Target devices:
    - Moderator: 13" laptop (1366x768 or 1440x900)
    - Subject: 11" tablet (1024x768)
    """
    viewport = st.session_state.get("viewport_data", {"width": 1024, "height": 768})

    viewport_width = viewport.get("width", 1024)
    viewport_height = viewport.get("height", 768)

    # Calculate based on device type
    # Tablets (subject): More screen space for canvas
    if viewport_width <= 1024:
        # 11" tablet - use larger portion of screen
        canvas_size = min(int(viewport_width * 0.65), 500)

    # Small laptops (moderator)
    elif viewport_width <= 1440:
        # 13" laptop - moderate canvas size
        canvas_size = min(int(viewport_width * 0.45), 500)

    # Larger screens
    else:
        canvas_size = 600

    # Ensure minimum size for usability
    return max(400, canvas_size)


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
