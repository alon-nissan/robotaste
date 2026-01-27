"""
Completion Phase Renderer

Displays thank you screen with session summary.
Provides completion message and option to return home.

Author: AI Agent (extracted from robotaste/views/completion.py)
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any
from datetime import datetime
from robotaste.data.database import get_session, get_session_stats

logger = logging.getLogger(__name__)


def render_completion(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render session completion screen.
    
    Shows thank you message with basic session statistics and
    option to return to landing page. This is the subject-facing
    completion screen.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    try:
        # Get session data
        session = get_session(session_id)
        if not session:
            st.error("Session not found. Please return to the home page.")
            if st.button("Return to Home", type="primary"):
                st.query_params.clear()
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
            return
        
        stats = get_session_stats(session_id)
        
        # Calculate session duration
        duration_str = "Unknown"
        if stats.get("created_at") and stats.get("last_cycle_at"):
            try:
                start = datetime.fromisoformat(stats["created_at"])
                end = datetime.fromisoformat(stats["last_cycle_at"])
                duration = end - start
                minutes = int(duration.total_seconds() // 60)
                seconds = int(duration.total_seconds() % 60)
                duration_str = f"{minutes} min {seconds} sec"
            except Exception as e:
                logger.warning(f"Could not calculate duration: {e}")
        
        # Display completion message
        st.markdown("# 🎉 Session Complete!")
        st.markdown("---")
        
        st.success("### Thank you for participating in this taste experiment!")
        
        st.markdown(
            """
        Your responses have been successfully recorded and will contribute
        to understanding taste preferences.
        """
        )
        
        # Session summary
        st.markdown("### Session Summary")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Samples Tasted", stats.get("total_cycles", 0))
        
        with col2:
            st.metric("Session Duration", duration_str)
        
        st.markdown("---")
        
        # Return button
        if st.button("🏠 Return to Home", type="primary", use_container_width=True):
            # Clear session state
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        # Mark phase as complete
        st.session_state.phase_complete = True
        logger.info(f"Session {session_id}: Completion screen displayed")
    
    except Exception as e:
        logger.error(
            f"Session {session_id}: Error displaying completion screen: {e}",
            exc_info=True
        )
        st.error("An error occurred while displaying the completion screen.")
        if st.button("Return to Home", type="primary"):
            st.query_params.clear()
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
