"""
State Machine for Experiment Phase Management
==============================================

Manages experiment phase transitions and state validation.

Workflow: WAITING → ROBOT_PREPARING → LOADING → QUESTIONNAIRE → SELECTION → COMPLETE

Author: Masters Research Project
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

    WAITING = "waiting"  # Session created, waiting for moderator to start
    ROBOT_PREPARING = "robot_preparing"  # Robot is preparing the solution
    LOADING = "loading"  # Loading screen before questionnaire in cycles 1+
    QUESTIONNAIRE = "questionnaire"  # Subject answering questionnaire
    SELECTION = "selection"  # Subject making selection for next cycle
    COMPLETE = "complete"  # Session finished

    @classmethod
    def from_string(cls, phase_str: str) -> Optional["ExperimentPhase"]:
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

    Ensures valid transitions and maintains Streamlit session state.
    Note: DB only stores session-level state (active/completed/cancelled),
    not fine-grained phases.
    """

    # Define valid transitions (phase -> list of allowed next phases)
    VALID_TRANSITIONS = {
        ExperimentPhase.WAITING: [
            ExperimentPhase.LOADING,  # Moderator starts first cycle
            ExperimentPhase.COMPLETE,  # Moderator can force-end from any phase
        ],
        ExperimentPhase.ROBOT_PREPARING: [
            ExperimentPhase.QUESTIONNAIRE,  # Robot finished, go directly to questionnaire (TASTING removed)
            ExperimentPhase.COMPLETE,  # Moderator can force-end from any phase
        ],
        ExperimentPhase.LOADING: [
            ExperimentPhase.QUESTIONNAIRE,  # Loading screen (5s) before questionnaire in cycles 1+
            ExperimentPhase.COMPLETE,  # Moderator can force-end from any phase
        ],
        ExperimentPhase.QUESTIONNAIRE: [
            ExperimentPhase.SELECTION,  # Subject finished questionnaire (cycle increments here)
            ExperimentPhase.COMPLETE,  # Moderator can force-end from any phase
        ],
        ExperimentPhase.SELECTION: [
            ExperimentPhase.LOADING,  # All selections (cycle 1+) go to loading screen
            ExperimentPhase.COMPLETE,  # Subject/moderator chooses to finish
        ],
        ExperimentPhase.COMPLETE: [
            ExperimentPhase.WAITING  # Session reset (new session)
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
    def can_transition(
        current_phase: ExperimentPhase, new_phase: ExperimentPhase
    ) -> bool:
        """
        Check if transition is valid.

        Args:
            current_phase: Current phase
            new_phase: Desired new phase

        Returns:
            True if transition is allowed, False otherwise
        """
        allowed_transitions = ExperimentStateMachine.VALID_TRANSITIONS.get(
            current_phase, []
        )
        return new_phase in allowed_transitions

    @staticmethod
    def transition(
        new_phase: ExperimentPhase, session_id: Optional[str] = None
    ) -> bool:
        """
        Execute a validated phase transition.

        This method:
        1. Validates the transition is allowed
        2. Updates session state
        3. Syncs current_phase to database for multi-device sync
        4. Updates session state to 'completed' if transitioning to COMPLETE
        5. Logs the transition

        Args:
            new_phase: Target phase to transition to
            session_id: Session ID for database sync (required for sync)

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

        # Sync to database for multi-device coordination
        if session_id:
            try:
                import sql_handler as sql

                # Always update current_phase for device sync
                sql.update_current_phase(session_id, new_phase.value)

                # Additionally update session state if completing
                if new_phase == ExperimentPhase.COMPLETE:
                    sql.update_session_state(session_id, "completed")
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
            ExperimentPhase.WAITING: "Waiting to Start",
            ExperimentPhase.ROBOT_PREPARING: "Robot Preparing Solution",
            ExperimentPhase.LOADING: "Preparing Sample",
            ExperimentPhase.QUESTIONNAIRE: "Answering Questionnaire",
            ExperimentPhase.SELECTION: "Making Selection",
            ExperimentPhase.COMPLETE: "Session Complete",
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
            ExperimentPhase.ROBOT_PREPARING: "blue",
            ExperimentPhase.LOADING: "blue",
            # ExperimentPhase.TASTING: "orange", stage removed
            ExperimentPhase.QUESTIONNAIRE: "purple",
            ExperimentPhase.SELECTION: "green",
            ExperimentPhase.COMPLETE: "gray",
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
            ExperimentPhase.ROBOT_PREPARING,
            ExperimentPhase.LOADING,
            # ExperimentPhase.TASTING, stage removed
            ExperimentPhase.QUESTIONNAIRE,
            ExperimentPhase.SELECTION,
        ]

    @staticmethod
    def is_trial_active() -> bool:
        """
        Check if trial is in an active phase (not waiting, not complete).

        Returns:
            True if trial is active, False otherwise
        """
        return ExperimentStateMachine.should_show_monitoring()

    @staticmethod
    def should_show_robot_preparing() -> bool:
        """
        Check if UI should show robot preparing message.

        Returns:
            True if phase is ROBOT_PREPARING
        """
        current_phase = ExperimentStateMachine.get_current_phase()
        return current_phase == ExperimentPhase.ROBOT_PREPARING

    @staticmethod
    def should_show_questionnaire() -> bool:
        """
        Check if UI should show questionnaire.

        Returns:
            True if phase is QUESTIONNAIRE
        """
        current_phase = ExperimentStateMachine.get_current_phase()
        return current_phase == ExperimentPhase.QUESTIONNAIRE

    @staticmethod
    def should_show_selection() -> bool:
        """
        Check if UI should show selection interface (grid/sliders).

        Returns:
            True if phase is SELECTION
        """
        current_phase = ExperimentStateMachine.get_current_phase()
        return current_phase == ExperimentPhase.SELECTION


def initialize_phase(default_phase: str = "waiting") -> None:
    """
    Initialize phase in session state if not already set.

    Args:
        default_phase: Default phase to use if none exists
    """
    if "phase" not in st.session_state:
        st.session_state.phase = default_phase
        logger.info(f"Initialized phase to: {default_phase}")


def recover_phase_from_database(session_id: str) -> Optional[str]:
    """
    Recover phase from database on browser reload.

    Note: In new architecture, only session-level state is persisted.
    Fine-grained phases are UI-only. On reload, default to WAITING or SELECTION
    depending on whether session is active or completed.

    Args:
        session_id: Session ID to look up

    Returns:
        Phase string to initialize, or None if not found
    """
    try:
        import sql_handler as sql

        session = sql.get_session(session_id)

        if not session:
            return None

        # Map session state to phase
        state = session.get("state")
        if state == "completed":
            return ExperimentPhase.COMPLETE.value
        elif state == "cancelled":
            return ExperimentPhase.COMPLETE.value
        elif state == "active":
            # Check if any cycles completed
            current_cycle = session.get("experiment_config", {}).get("current_cycle", 0)
            if current_cycle == 0:
                # No cycles yet, start from waiting
                return ExperimentPhase.WAITING.value
            else:
                # Mid-session, default to selection (safe re-entry point)
                return ExperimentPhase.SELECTION.value

        return ExperimentPhase.WAITING.value

    except Exception as e:
        logger.error(f"Failed to recover phase from database: {e}")

    return None
