"""
State Machine Streamlit Helpers

Provides Streamlit-aware wrapper functions for the pure Python state machine.
These helpers integrate session state and database syncing.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
import logging
from typing import Optional
from robotaste.core.state_machine import ExperimentStateMachine, ExperimentPhase

logger = logging.getLogger(__name__)


def get_current_phase() -> ExperimentPhase:
    """
    Get current phase from Streamlit session state.

    Returns:
        Current ExperimentPhase, defaults to WAITING if not set
    """
    phase_str = st.session_state.get("phase", "waiting")
    try:
        return ExperimentPhase(phase_str)
    except ValueError:
        logger.warning(f"Invalid phase in session state: {phase_str}, defaulting to WAITING")
        return ExperimentPhase.WAITING


def transition(
    current_phase: ExperimentPhase,
    new_phase: ExperimentPhase,
    session_id: Optional[str] = None
) -> bool:
    """
    Transition to a new phase with Streamlit session state and database sync.

    Args:
        current_phase: Current phase
        new_phase: Phase to transition to
        session_id: Optional session ID for database sync

    Returns:
        True if transition succeeded, False otherwise

    Raises:
        InvalidTransitionError: If transition is not allowed
    """
    from robotaste.data.database import update_current_phase, update_session_state

    # Validate transition
    ExperimentStateMachine.validate_transition(current_phase, new_phase)

    # Update session state
    st.session_state.phase = new_phase.value

    # Sync to database for multi-device coordination
    if session_id:
        try:
            # Always update current_phase for device sync
            update_current_phase(session_id, new_phase.value)

            # Additionally update session state if completing
            if new_phase == ExperimentPhase.COMPLETE:
                update_session_state(session_id, "completed")
                logger.info(
                    f"Session state synced to database: completed "
                    f"(session_id={session_id})"
                )

        except Exception as e:
            logger.error(f"Failed to sync phase to database: {e}")
            # Don't fail the transition if database sync fails
            # Session state is updated, database will catch up

    # Log transition
    logger.info(
        f"Phase transition: {current_phase.value} -> {new_phase.value} "
        f"(session_id={session_id})"
    )

    return True


def should_show_setup() -> bool:
    """
    Check if moderator should see experiment setup UI.

    Returns:
        True if phase is WAITING (setup mode), False otherwise
    """
    current_phase = get_current_phase()
    return ExperimentStateMachine.should_show_setup(current_phase)


def should_show_monitoring() -> bool:
    """
    Check if moderator should see monitoring UI.

    Returns:
        True if trial is in progress, False otherwise
    """
    current_phase = get_current_phase()
    return ExperimentStateMachine.should_show_monitoring(current_phase)


def should_show_selection() -> bool:
    """
    Check if UI should show selection interface (grid/sliders).

    Returns:
        True if phase is SELECTION
    """
    current_phase = get_current_phase()
    return current_phase == ExperimentPhase.SELECTION
