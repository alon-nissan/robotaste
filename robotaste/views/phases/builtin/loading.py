"""
Loading Phase Renderer

Displays loading/waiting screen while sample is being prepared.
Shows progress bar and cycle information.

Author: AI Agent (extracted from robotaste/views/subject.py)
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any
from robotaste.data.database import get_current_cycle
from robotaste.utils.ui_helpers import get_loading_screen_config, render_loading_screen

logger = logging.getLogger(__name__)


def render_loading(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render loading/waiting screen.
    
    Displays loading animation with progress bar while sample is being prepared
    (typically by moderator in manual mode). Automatically transitions after
    configured duration.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    # Get current cycle
    cycle_num = get_current_cycle(session_id)
    
    # Get total cycles from protocol stopping criteria
    total_cycles = None
    stopping_criteria = protocol.get("stopping_criteria", {})
    total_cycles = stopping_criteria.get("max_cycles")
    
    # Get loading screen configuration from protocol
    loading_config = get_loading_screen_config(protocol)
    
    # Check if we should use dynamic pump time
    pump_config = protocol.get("pump_config", {})
    loading_screen_config = protocol.get("loading_screen", {})
    use_dynamic = loading_screen_config.get("use_dynamic_duration", False)
    
    if pump_config.get("enabled") and use_dynamic:
        # Use calculated pump time if available
        pump_time_key = f"pump_time_cycle_{cycle_num}"
        if pump_time_key in st.session_state:
            duration_seconds = (
                int(st.session_state[pump_time_key]) + 2
            )  # Add 2s for safety
            logger.info(
                f"Session {session_id}: Using dynamic loading duration: "
                f"{duration_seconds}s (from pump time)"
            )
        else:
            duration_seconds = loading_config.get("duration_seconds", 5)
    else:
        duration_seconds = loading_config.get("duration_seconds", 5)
    
    # Render dedicated loading screen
    render_loading_screen(
        cycle_number=cycle_num,
        total_cycles=total_cycles,
        duration_seconds=duration_seconds,
        **{k: v for k, v in loading_config.items() if k != "duration_seconds"},
    )
    
    # Mark phase as complete (PhaseRouter will handle transition)
    st.session_state.phase_complete = True
    logger.info(
        f"Session {session_id}: Loading phase complete (cycle {cycle_num})"
    )
