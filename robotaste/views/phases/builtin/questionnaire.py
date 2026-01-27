"""
Questionnaire Phase Renderer

Displays rating questionnaire based on protocol configuration.
Saves responses to database and increments cycle counter.

Author: AI Agent (extracted from robotaste/views/subject.py)
Date: 2026-01-27
"""

import streamlit as st
import time
import logging
from typing import Dict, Any
from robotaste.data.database import (
    get_current_cycle,
    save_sample_cycle,
    increment_cycle,
)
from robotaste.views.questionnaire import render_questionnaire as render_questionnaire_ui
from robotaste.config.questionnaire import get_default_questionnaire_type

logger = logging.getLogger(__name__)


def _get_questionnaire_type_from_protocol(protocol: Dict[str, Any]) -> str:
    """
    Extract questionnaire type from protocol configuration.
    
    Args:
        protocol: Protocol dictionary
    
    Returns:
        Questionnaire type string
    """
    # Try experiment_config first
    experiment_config = protocol.get("experiment_config", {})
    questionnaire_type = experiment_config.get("questionnaire_type")
    if questionnaire_type:
        return questionnaire_type
    
    # Try session state as fallback
    if hasattr(st.session_state, "selected_questionnaire_type"):
        return st.session_state.selected_questionnaire_type
    
    # Default
    return get_default_questionnaire_type()


def render_questionnaire(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render questionnaire for current cycle.
    
    Displays rating questions based on protocol configuration.
    Saves responses to database and increments cycle counter.
    Sets phase_complete when questionnaire is submitted.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    cycle_num = get_current_cycle(session_id)
    
    st.info(
        f"Cycle {cycle_num}: Please answer the questionnaire about the "
        f"sample you just tasted"
    )
    
    # Get questionnaire type from protocol
    questionnaire_type = _get_questionnaire_type_from_protocol(protocol)
    
    # Get participant ID
    participant_id = st.session_state.get("participant")
    if not participant_id:
        st.error("No participant ID found. Please rejoin the session.")
        logger.error(f"Session {session_id}: No participant ID in questionnaire phase")
        return
    
    # Render questionnaire UI
    responses = render_questionnaire_ui(questionnaire_type, participant_id)
    
    if responses:
        # Store responses in session state
        st.session_state.questionnaire_responses = responses
        
        # Get sample information
        current_cycle = get_current_cycle(session_id)
        ingredient_concentrations = st.session_state.get("current_tasted_sample", {})
        selection_data = st.session_state.get("next_selection_data", {})
        
        # GUARD: Don't save if sample is empty (not yet prepared)
        if not ingredient_concentrations:
            logger.warning(
                f"Session {session_id}: Cycle {current_cycle}: "
                f"Sample not prepared yet, skipping save"
            )
            st.warning("Please wait for sample to be prepared...")
            time.sleep(1)
            st.rerun()
            return
        
        try:
            # Extract selection mode from selection_data or determine from protocol
            selection_mode = selection_data.get("selection_mode", "user_selected")
            if not selection_mode or selection_mode == "unknown":
                # Fall back to determining from protocol
                from robotaste.core.trials import get_selection_mode_for_cycle_runtime
                
                selection_mode = get_selection_mode_for_cycle_runtime(
                    session_id, current_cycle
                )
            
            # Save the questionnaire data for current cycle
            save_sample_cycle(
                session_id=session_id,
                cycle_number=current_cycle,
                ingredient_concentration=ingredient_concentrations,
                selection_data=selection_data,
                questionnaire_answer=responses,
                is_final=False,
                selection_mode=selection_mode,
            )
            
            logger.info(
                f"Session {session_id}: Saved questionnaire for cycle {current_cycle}"
            )
            
            # Increment cycle counter for next iteration
            increment_cycle(session_id)
            logger.info(
                f"Session {session_id}: Incremented cycle from {current_cycle} "
                f"to {current_cycle + 1}"
            )
            
            # Mark phase as complete
            st.session_state.phase_complete = True
            
            # Clear temporary data for next cycle
            if "current_tasted_sample" in st.session_state:
                del st.session_state.current_tasted_sample
            if "next_selection_data" in st.session_state:
                del st.session_state.next_selection_data
            
            # Don't call st.rerun() - let PhaseRouter handle navigation
        
        except Exception as e:
            st.error(f"Failed to save questionnaire: {e}")
            logger.error(
                f"Session {session_id}: Failed to save questionnaire for "
                f"cycle {current_cycle}: {e}",
                exc_info=True
            )
