"""
RoboTaste UI Helper Functions

Utility functions for Streamlit UI operations.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
import time
from typing import Dict, Any, Optional


def cleanup_pending_results():
    """Clean up all pending result data from session state."""
    pending_keys = ["pending_canvas_result", "pending_slider_result", "pending_method"]

    for key in pending_keys:
        if hasattr(st.session_state, key):
            delattr(st.session_state, key)


def render_loading_spinner(message: str = "Loading...", load_time=5):
    """
    Render a loading spinner with a custom message.

    DEPRECATED: Use render_loading_screen() instead for better UX.
    """
    with st.spinner(message):
        time.sleep(load_time)  # Small delay to ensure spinner is visible
        # Phase transition handled by calling code using state machine


def get_loading_screen_config(protocol: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract loading screen configuration from protocol with fallback to defaults.

    Args:
        protocol: Protocol dictionary (optional)

    Returns:
        Dictionary with loading screen configuration including:
        - message: Instructions text
        - duration_seconds: Display duration
        - show_progress: Whether to show progress bar
        - show_cycle_info: Whether to show cycle number
        - message_size: Font size ("normal", "large", "extra_large")
    """
    defaults = {
        "message": "Rinse your mouth while the robot prepares the next sample.",
        "duration_seconds": 5,
        "show_progress": True,
        "show_cycle_info": True,
        "message_size": "large",
    }

    if not protocol:
        return defaults

    loading_config = protocol.get("loading_screen", {})

    # Merge with defaults (protocol values override defaults)
    return {
        "message": loading_config.get("message", defaults["message"]),
        "duration_seconds": loading_config.get("duration_seconds", defaults["duration_seconds"]),
        "show_progress": loading_config.get("show_progress", defaults["show_progress"]),
        "show_cycle_info": loading_config.get("show_cycle_info", defaults["show_cycle_info"]),
        "message_size": loading_config.get("message_size", defaults["message_size"]),
    }


def _render_progress_bar(container, duration_seconds: int) -> None:
    """
    Helper to render animated progress bar.

    Args:
        container: Streamlit container to render in
        duration_seconds: Total duration in seconds
    """
    progress_bar = container.progress(0)

    # Animate progress bar (update 10 times per second)
    steps = duration_seconds * 10
    for i in range(steps + 1):
        progress = i / steps
        progress_bar.progress(progress)
        time.sleep(duration_seconds / steps)

    # Ensure it reaches 100%
    progress_bar.progress(1.0)


def _render_loading_message(container, message: str, size: str) -> None:
    """
    Helper to render loading message with appropriate sizing.
    Matches clean, scientific aesthetic of reference site.

    Args:
        container: Streamlit container to render in
        message: Message text to display
        size: Size setting ("normal", "large", "extra_large")
    """
    size_map = {
        "normal": "1.5rem",
        "large": "2rem",
        "extra_large": "2.5rem"
    }

    font_size = size_map.get(size, "2rem")

    container.markdown(
        f"""
        <div style='text-align: center; font-size: {font_size};
        font-weight: 400; color: #34495E; margin: 3rem auto;
        max-width: 700px; line-height: 1.8; padding: 2rem;
        background: #F8F9FA; border-radius: 8px;
        border-left: 4px solid #521924;'>
        {message}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_loading_screen(
    cycle_number: int,
    total_cycles: Optional[int] = None,
    message: str = "Rinse your mouth while the robot prepares the next sample.",
    duration_seconds: int = 5,
    show_progress: bool = True,
    show_cycle_info: bool = True,
    message_size: str = "large",
) -> None:
    """
    Render a full-page loading screen with cycle information and progress.
    Matches the clean, scientific aesthetic of mashaniv.wixsite.com/niv-taste-lab

    This function displays a minimalist, centered loading view during the
    LOADING and ROBOT_PREPARING phases. It shows:
    - Cycle information (e.g., "Cycle 3 of 10")
    - Loading instructions
    - Progress bar with time remaining

    Args:
        cycle_number: Current cycle number (1-indexed)
        total_cycles: Total number of cycles (optional, from protocol)
        message: Instructions to display
        duration_seconds: How long to display the screen
        show_progress: Whether to show progress bar
        show_cycle_info: Whether to show cycle information
        message_size: Size of message text ("normal", "large", "extra_large")

    Note:
        - This function blocks for duration_seconds
        - Phase transition is handled by calling code
        - Uses st.empty() containers for better layout control
    """
    # Center content with columns (1:2:1 ratio)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # === CYCLE INFORMATION ===
        if show_cycle_info:
            if total_cycles:
                st.markdown(
                    f"""
                    <div style='text-align: center; font-size: 3rem;
                    font-weight: 300; color: #2C3E50; margin: 4rem 0 2rem 0;
                    letter-spacing: 0.05em;'>
                    Cycle <span style='font-weight: 600;'>{cycle_number}</span> of {total_cycles}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"""
                    <div style='text-align: center; font-size: 3rem;
                    font-weight: 300; color: #2C3E50; margin: 4rem 0 2rem 0;
                    letter-spacing: 0.05em;'>
                    Cycle <span style='font-weight: 600;'>{cycle_number}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # === MESSAGE ===
        message_placeholder = st.empty()
        _render_loading_message(message_placeholder, message, message_size)

        # === PROGRESS BAR WITH TIME REMAINING ===
        if show_progress:
            st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
            progress_container = st.empty()
            time_container = st.empty()

            for i in range(duration_seconds + 1):
                progress = i / duration_seconds

                # Update progress bar
                progress_container.progress(progress)

                # Update time remaining
                remaining = duration_seconds - i
                if remaining > 0:
                    time_container.markdown(
                        f"""
                        <div style='text-align: center; font-size: 1.25rem;
                        color: #7F8C8D; margin-top: 1rem; font-weight: 300;'>
                        {remaining} seconds remaining
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                else:
                    time_container.markdown(
                        f"""
                        <div style='text-align: center; font-size: 1.25rem;
                        color: #27AE60; margin-top: 1rem; font-weight: 400;'>
                        ✓ Ready
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                time.sleep(1)
        else:
            # Just sleep without progress bar
            time.sleep(duration_seconds)


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
