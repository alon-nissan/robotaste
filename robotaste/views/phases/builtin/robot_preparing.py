"""
Robot Preparing Phase Renderer

Shows "Robot is preparing your sample" message and executes pump operations.
Polls for pump operation completion if using hardware pumps.

Author: AI Agent (extracted from robotaste/views/subject.py)
Date: 2026-01-27
"""

import streamlit as st
import time
import logging
from typing import Dict, Any
from robotaste.data.database import get_current_cycle
from robotaste.utils.ui_helpers import (
    get_loading_screen_config,
    render_loading_screen,
    render_cycle_info,
    render_loading_message,
    init_async_progress,
    complete_async_progress,
)

logger = logging.getLogger(__name__)


def render_robot_preparing(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render robot preparing screen.
    
    If pumps are enabled: Executes pump operations and shows progress.
    If pumps are disabled: Falls back to standard loading screen.
    
    Sets phase_complete when pump operation is done or loading finishes.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    # Get current cycle
    cycle_num = get_current_cycle(session_id)
    
    # Check if pump control is enabled
    pump_config = protocol.get("pump_config", {})
    pump_enabled = pump_config.get("enabled", False)
    
    if pump_enabled:
        # Check if pump operation already exists for this cycle
        from robotaste.core.pump_integration import get_pump_operation_for_cycle
        
        existing_operation = get_pump_operation_for_cycle(session_id, cycle_num)
        
        # Only execute if no existing operation (fresh entry to phase)
        if existing_operation is None:
            # Get loading screen configuration
            loading_config = get_loading_screen_config(protocol)
            
            # Get total cycles for display
            total_cycles = None
            stopping_criteria = protocol.get("stopping_criteria", {})
            total_cycles = stopping_criteria.get("max_cycles")
            
            # Display cycle information with unified styling
            if loading_config.get("show_cycle_info", True):
                render_cycle_info(cycle_num, total_cycles)
            
            # Display loading message with unified styling
            message = loading_config.get(
                "message", "Rinse your mouth while the robot prepares the next sample."
            )
            message_size = loading_config.get("message_size", "large")
            render_loading_message(message, message_size)
            
            # Get estimated duration for progress display
            from robotaste.core.pump_integration import get_pump_operation_duration
            estimated_duration = get_pump_operation_duration(session_id, cycle_num)
            
            # Initialize progress display (matches LOADING phase styling)
            progress_containers = init_async_progress(
                estimated_duration=estimated_duration,
                show_progress=loading_config.get("show_progress", True),
            )
            
            # Execute pumps (synchronous - blocks until complete)
            from robotaste.core.pump_integration import execute_pumps_synchronously
            result = execute_pumps_synchronously(
                session_id=session_id,
                cycle_number=cycle_num,
                streamlit_container=None,  # Disable UI logging
            )
            
            # Show completion state
            complete_async_progress(progress_containers)
            time.sleep(1)  # Brief pause to show "✓ Ready"
            
            # Check result
            if result["success"]:
                st.session_state.phase_complete = True
                logger.info(
                    f"Session {session_id}: Robot preparing complete "
                    f"(cycle {cycle_num})"
                )
            else:
                st.error(f"❌ Pump operation failed: {result['error']}")
                logger.error(
                    f"Session {session_id}: Pump operation failed: {result['error']}"
                )
                st.stop()
        
        else:
            # Operation already exists (this is a resume)
            operation_status = existing_operation.get("status", "unknown")
            
            if operation_status == "completed":
                st.success("✅ Sample already prepared (resumed session)")
                st.session_state.phase_complete = True
                logger.info(
                    f"Session {session_id}: Robot preparing already complete "
                    f"(resumed, cycle {cycle_num})"
                )
            
            elif operation_status in ["pending", "in_progress"]:
                st.warning("⏳ Pump operation in progress... Please wait.")
                st.info("If this message persists, please contact the moderator.")
                logger.warning(
                    f"Session {session_id}: Pump operation still in progress "
                    f"(cycle {cycle_num})"
                )
                st.stop()
            
            elif operation_status == "failed":
                error_msg = existing_operation.get("error_message", "Unknown error")
                st.error(f"❌ Previous pump operation failed: {error_msg}")
                st.error("Please contact the moderator to reset the session.")
                logger.error(
                    f"Session {session_id}: Previous pump operation failed: "
                    f"{error_msg} (cycle {cycle_num})"
                )
                st.stop()
            
            else:
                st.warning(f"⚠️ Unknown pump operation status: {operation_status}")
                st.error("Please contact the moderator.")
                logger.error(
                    f"Session {session_id}: Unknown pump status: {operation_status} "
                    f"(cycle {cycle_num})"
                )
                st.stop()
    
    else:
        # Pump control disabled, use standard loading screen
        # Get total cycles from protocol stopping criteria
        total_cycles = None
        stopping_criteria = protocol.get("stopping_criteria", {})
        total_cycles = stopping_criteria.get("max_cycles")
        
        # Get loading screen configuration from protocol
        loading_config = get_loading_screen_config(protocol)
        
        # Render dedicated loading screen
        render_loading_screen(
            cycle_number=cycle_num, total_cycles=total_cycles, **loading_config
        )
        
        # Mark phase as complete
        st.session_state.phase_complete = True
        logger.info(
            f"Session {session_id}: Robot preparing complete (no pumps, cycle {cycle_num})"
        )
