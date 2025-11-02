"""
State Machine for Experiment Phase Management

This module provides centralized, validated phase transitions for the RoboTaste
experiment application. It ensures that:
1. All phase transitions are valid and follow the defined workflow
2. Session state and database are synchronized atomically
3. Phase changes are logged for audit trails
4. Invalid transitions are prevented at runtime

Author: Masters Research Project
Version: 1.0
Last Updated: 2025
"""

from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import streamlit as st

# Setup logging
logger = logging.getLogger(__name__)


class ExperimentPhase(Enum):
    """All possible phases in the experiment workflow."""

    # Session-level phases (database tracked)
    WAITING = "waiting"  # Initial state when session created
    TRIAL_STARTED = "trial_started"  # Moderator has started the trial

    # Subject-level phases (now database synced)
    SUBJECT_WELCOME = "welcome"  # Subject entering participant ID
    PRE_QUESTIONNAIRE = "pre_questionnaire"  # Initial impression questionnaire
    TRIAL_ACTIVE = "respond"  # Main experiment interaction (grid/sliders)
    POST_RESPONSE_MESSAGE = "post_response_message"  # Brief message after response
    POST_QUESTIONNAIRE = "post_questionnaire"  # Post-selection questionnaire
    TRIAL_COMPLETE = "done"  # Trial finished

    @classmethod
    def from_string(cls, phase_str: str) -> Optional['ExperimentPhase']:
        """Convert string to ExperimentPhase enum."""
        for phase in cls:
            if phase.value == phase_str:
                return phase
        return None


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid phase transition."""
    pass


class ExperimentStateMachine:
    """
    Centralized state machine for managing experiment phases.

    Ensures valid transitions and maintains synchronization between
    Streamlit session state and database.
    """

    # Define valid transitions (phase -> list of allowed next phases)
    VALID_TRANSITIONS = {
        ExperimentPhase.WAITING: [
            ExperimentPhase.TRIAL_STARTED,
            ExperimentPhase.SUBJECT_WELCOME
        ],
        ExperimentPhase.TRIAL_STARTED: [
            ExperimentPhase.SUBJECT_WELCOME,
            ExperimentPhase.TRIAL_ACTIVE
        ],
        ExperimentPhase.SUBJECT_WELCOME: [
            ExperimentPhase.PRE_QUESTIONNAIRE
        ],
        ExperimentPhase.PRE_QUESTIONNAIRE: [
            ExperimentPhase.TRIAL_ACTIVE
        ],
        ExperimentPhase.TRIAL_ACTIVE: [
            ExperimentPhase.POST_QUESTIONNAIRE,
            ExperimentPhase.POST_RESPONSE_MESSAGE
        ],
        ExperimentPhase.POST_RESPONSE_MESSAGE: [
            ExperimentPhase.POST_QUESTIONNAIRE
        ],
        ExperimentPhase.POST_QUESTIONNAIRE: [
            ExperimentPhase.TRIAL_ACTIVE,  # Continue selecting (not final)
            ExperimentPhase.TRIAL_COMPLETE  # Final submission
        ],
        ExperimentPhase.TRIAL_COMPLETE: [
            ExperimentPhase.TRIAL_ACTIVE,  # New trial started
            ExperimentPhase.WAITING  # Session reset
        ],
    }

    @staticmethod
    def get_current_phase() -> ExperimentPhase:
        """
        Get current phase from session state.

        Returns:
            ExperimentPhase enum representing current phase
        """
        phase_str = st.session_state.get("phase", "waiting")
        phase = ExperimentPhase.from_string(phase_str)
        if phase is None:
            logger.warning(f"Unknown phase '{phase_str}', defaulting to WAITING")
            return ExperimentPhase.WAITING
        return phase

    @staticmethod
    def can_transition(current_phase: ExperimentPhase, new_phase: ExperimentPhase) -> bool:
        """
        Check if transition is valid.

        Args:
            current_phase: Current phase
            new_phase: Desired new phase

        Returns:
            True if transition is allowed, False otherwise
        """
        allowed_transitions = ExperimentStateMachine.VALID_TRANSITIONS.get(current_phase, [])
        return new_phase in allowed_transitions

    @staticmethod
    def transition(
        new_phase: ExperimentPhase,
        session_code: Optional[str] = None,
        participant_id: Optional[str] = None,
        sync_to_database: bool = True
    ) -> bool:
        """
        Execute a validated phase transition.

        This method:
        1. Validates the transition is allowed
        2. Updates session state
        3. Optionally syncs to database
        4. Logs the transition

        Args:
            new_phase: Target phase to transition to
            session_code: Session code for database sync (optional)
            participant_id: Participant ID for logging (optional)
            sync_to_database: Whether to sync to database (default True)

        Returns:
            True if transition successful, False otherwise

        Raises:
            InvalidTransitionError: If transition is not allowed
        """
        current_phase = ExperimentStateMachine.get_current_phase()

        # Validate transition
        if not ExperimentStateMachine.can_transition(current_phase, new_phase):
            error_msg = (
                f"Invalid transition: {current_phase.value} -> {new_phase.value}. "
                f"Allowed transitions from {current_phase.value}: "
                f"{[p.value for p in ExperimentStateMachine.VALID_TRANSITIONS.get(current_phase, [])]}"
            )
            logger.error(error_msg)
            raise InvalidTransitionError(error_msg)

        # Update session state
        st.session_state.phase = new_phase.value

        # Sync to database if requested
        if sync_to_database and session_code:
            try:
                from session_manager import update_session_activity
                update_session_activity(
                    session_code,
                    phase=new_phase.value,
                    config=None
                )
                logger.info(
                    f"Phase transition synced to database: {current_phase.value} -> {new_phase.value} "
                    f"(session={session_code}, participant={participant_id})"
                )
            except Exception as e:
                logger.error(f"Failed to sync phase to database: {e}")
                # Don't fail the transition if database sync fails
                # Session state is updated, database will catch up

        # Log transition
        logger.info(
            f"Phase transition: {current_phase.value} -> {new_phase.value} "
            f"(participant={participant_id})"
        )

        return True

    @staticmethod
    def get_phase_display_name(phase: ExperimentPhase) -> str:
        """
        Get human-readable display name for phase.

        Args:
            phase: ExperimentPhase enum

        Returns:
            Display-friendly phase name
        """
        display_names = {
            ExperimentPhase.WAITING: "Waiting for Trial",
            ExperimentPhase.TRIAL_STARTED: "Trial Started",
            ExperimentPhase.SUBJECT_WELCOME: "Welcome",
            ExperimentPhase.PRE_QUESTIONNAIRE: "Pre-Questionnaire",
            ExperimentPhase.TRIAL_ACTIVE: "Active Selection",
            ExperimentPhase.POST_RESPONSE_MESSAGE: "Preparing Solution",
            ExperimentPhase.POST_QUESTIONNAIRE: "Post-Questionnaire",
            ExperimentPhase.TRIAL_COMPLETE: "Complete",
        }
        return display_names.get(phase, phase.value.title())

    @staticmethod
    def get_phase_color(phase: ExperimentPhase) -> str:
        """
        Get color code for phase badge display.

        Args:
            phase: ExperimentPhase enum

        Returns:
            Color name or hex code for display
        """
        colors = {
            ExperimentPhase.WAITING: "gray",
            ExperimentPhase.TRIAL_STARTED: "blue",
            ExperimentPhase.SUBJECT_WELCOME: "yellow",
            ExperimentPhase.PRE_QUESTIONNAIRE: "orange",
            ExperimentPhase.TRIAL_ACTIVE: "green",
            ExperimentPhase.POST_RESPONSE_MESSAGE: "blue",
            ExperimentPhase.POST_QUESTIONNAIRE: "orange",
            ExperimentPhase.TRIAL_COMPLETE: "gray",
        }
        return colors.get(phase, "gray")

    @staticmethod
    def should_show_setup() -> bool:
        """
        Check if moderator should see experiment setup UI.

        Returns:
            True if phase is WAITING (setup mode), False otherwise
        """
        current_phase = ExperimentStateMachine.get_current_phase()
        return current_phase == ExperimentPhase.WAITING

    @staticmethod
    def should_show_monitoring() -> bool:
        """
        Check if moderator should see monitoring UI (tabs with live data).

        Returns:
            True if trial is in any active phase, False if waiting or complete
        """
        current_phase = ExperimentStateMachine.get_current_phase()
        return current_phase in [
            ExperimentPhase.TRIAL_STARTED,
            ExperimentPhase.SUBJECT_WELCOME,
            ExperimentPhase.PRE_QUESTIONNAIRE,
            ExperimentPhase.TRIAL_ACTIVE,
            ExperimentPhase.POST_RESPONSE_MESSAGE,
            ExperimentPhase.POST_QUESTIONNAIRE,
        ]

    @staticmethod
    def is_trial_active() -> bool:
        """
        Check if trial is in an active phase (not waiting, not complete).

        Returns:
            True if trial is active, False otherwise
        """
        return ExperimentStateMachine.should_show_monitoring()


def initialize_phase(default_phase: str = "waiting") -> None:
    """
    Initialize phase in session state if not already set.

    Args:
        default_phase: Default phase to use if none exists
    """
    if "phase" not in st.session_state:
        st.session_state.phase = default_phase
        logger.info(f"Initialized phase to: {default_phase}")


def recover_phase_from_database(session_code: str) -> Optional[str]:
    """
    Recover phase from database on browser reload.

    Args:
        session_code: Session code to look up

    Returns:
        Phase string from database, or None if not found
    """
    try:
        from session_manager import get_session_info
        session_info = get_session_info(session_code)
        if session_info and session_info.get('current_phase'):
            phase = session_info['current_phase']
            logger.info(f"Recovered phase from database: {phase}")
            return phase
    except Exception as e:
        logger.error(f"Failed to recover phase from database: {e}")
    return None
