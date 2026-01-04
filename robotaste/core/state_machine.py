"""
State Machine for Experiment Phase Management (Pure Python Version)

Manages experiment phase transitions and state validation.
NO external dependencies (no Streamlit, no SQL).

Workflow: WAITING → ROBOT_PREPARING → LOADING → QUESTIONNAIRE → SELECTION → COMPLETE

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture - Pure Python)
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# EXPERIMENT PHASE ENUM
# ============================================================================


class ExperimentPhase(Enum):
    """
    All possible phases in the experiment workflow.

    Workflow:
    1. WAITING: Session created, waiting for moderator to start
    2. REGISTRATION: Subject enters personal information
    3. INSTRUCTIONS: Subject reads instructions
    4. ROBOT_PREPARING: Robot is preparing the solution
    5. LOADING: Loading screen before questionnaire in cycles 1+
    6. QUESTIONNAIRE: Subject answering questionnaire
    7. SELECTION: Subject making selection for next cycle
    8. COMPLETE: Session finished
    9. CUSTOM: Custom phase defined in protocol (catch-all for custom phases)
    """

    WAITING = "waiting"
    REGISTRATION = "registration"
    INSTRUCTIONS = "instructions"
    ROBOT_PREPARING = "robot_preparing"
    LOADING = "loading"
    QUESTIONNAIRE = "questionnaire"
    SELECTION = "selection"
    COMPLETE = "complete"
    CUSTOM = "custom"

    @classmethod
    def from_string(cls, phase_str: str) -> Optional["ExperimentPhase"]:
        """
        Convert string to ExperimentPhase enum.

        Args:
            phase_str: Phase value as string

        Returns:
            ExperimentPhase enum or None if invalid

        Example:
            >>> ExperimentPhase.from_string("waiting")
            <ExperimentPhase.WAITING: 'waiting'>
        """
        for phase in cls:
            if phase.value == phase_str:
                return phase
        return None

    def __str__(self) -> str:
        """String representation returns the value."""
        return self.value


# ============================================================================
# EXCEPTIONS
# ============================================================================


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid phase transition."""

    pass


# ============================================================================
# STATE MACHINE (PURE PYTHON)
# ============================================================================


class ExperimentStateMachine:
    """
    Pure Python state machine for managing experiment phases.

    This is the REFACTORED version with NO Streamlit/SQL dependencies.
    UI layer should handle session state and database synchronization separately.
    """

    # Define valid transitions (phase -> list of allowed next phases)
    VALID_TRANSITIONS = {
        ExperimentPhase.WAITING: [
            ExperimentPhase.REGISTRATION,  # Moderator starts -> Subject enters info
            ExperimentPhase.COMPLETE,  # Moderator can force-end
        ],
        ExperimentPhase.REGISTRATION: [
            ExperimentPhase.INSTRUCTIONS,  # Subject finishes info
            ExperimentPhase.COMPLETE,
        ],
        ExperimentPhase.INSTRUCTIONS: [
            ExperimentPhase.LOADING,  # Old flow: direct to loading
            ExperimentPhase.SELECTION,  # New flow: enter loop at selection
            ExperimentPhase.COMPLETE,
        ],
        ExperimentPhase.ROBOT_PREPARING: [
            ExperimentPhase.QUESTIONNAIRE,  # Robot finished
            ExperimentPhase.COMPLETE,  # Moderator can force-end
        ],
        ExperimentPhase.LOADING: [
            ExperimentPhase.QUESTIONNAIRE,  # Loading screen (5s) before questionnaire
            ExperimentPhase.COMPLETE,  # Moderator can force-end
        ],
        ExperimentPhase.QUESTIONNAIRE: [
            ExperimentPhase.SELECTION,  # Subject finished questionnaire
            ExperimentPhase.COMPLETE,  # Moderator can force-end
        ],
        ExperimentPhase.SELECTION: [
            ExperimentPhase.LOADING,  # All selections go to loading screen
            ExperimentPhase.COMPLETE,  # Subject/moderator chooses to finish
        ],
        ExperimentPhase.COMPLETE: [
            ExperimentPhase.WAITING  # Session reset (new session)
        ],
    }

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

        Example:
            >>> ExperimentStateMachine.can_transition(
            ...     ExperimentPhase.WAITING,
            ...     ExperimentPhase.REGISTRATION
            ... )
            True
            >>> ExperimentStateMachine.can_transition(
            ...     ExperimentPhase.WAITING,
            ...     ExperimentPhase.QUESTIONNAIRE
            ... )
            False
        """
        allowed_transitions = ExperimentStateMachine.VALID_TRANSITIONS.get(
            current_phase, []
        )
        return new_phase in allowed_transitions

    @staticmethod
    def validate_transition(
        current_phase: ExperimentPhase, new_phase: ExperimentPhase
    ) -> None:
        """
        Validate a transition is allowed, raise exception if not.

        Args:
            current_phase: Current phase
            new_phase: Desired new phase

        Raises:
            InvalidTransitionError: If transition is not allowed

        Example:
            >>> try:
            ...     ExperimentStateMachine.validate_transition(
            ...         ExperimentPhase.WAITING,
            ...         ExperimentPhase.QUESTIONNAIRE
            ...     )
            ... except InvalidTransitionError as e:
            ...     print("Invalid transition")
            Invalid transition
        """
        if not ExperimentStateMachine.can_transition(current_phase, new_phase):
            allowed = [
                p.value
                for p in ExperimentStateMachine.VALID_TRANSITIONS.get(current_phase, [])
            ]
            error_msg = (
                f"Invalid transition: {current_phase.value} -> {new_phase.value}. "
                f"Allowed transitions from {current_phase.value}: {allowed}"
            )
            logger.error(error_msg)
            raise InvalidTransitionError(error_msg)

    @staticmethod
    def get_allowed_transitions(
        current_phase: ExperimentPhase,
    ) -> List[ExperimentPhase]:
        """
        Get list of phases that can be transitioned to from current phase.

        Args:
            current_phase: Current phase

        Returns:
            List of allowed next phases

        Example:
            >>> ExperimentStateMachine.get_allowed_transitions(ExperimentPhase.WAITING)
            [<ExperimentPhase.REGISTRATION: 'registration'>, <ExperimentPhase.COMPLETE: 'complete'>]
        """
        return ExperimentStateMachine.VALID_TRANSITIONS.get(current_phase, [])

    @staticmethod
    def get_phase_display_name(phase: ExperimentPhase) -> str:
        """
        Get human-readable display name for phase.

        Args:
            phase: ExperimentPhase enum

        Returns:
            Display-friendly phase name

        Example:
            >>> ExperimentStateMachine.get_phase_display_name(ExperimentPhase.WAITING)
            'Waiting to Start'
        """
        display_names = {
            ExperimentPhase.WAITING: "Waiting to Start",
            ExperimentPhase.REGISTRATION: "User Registration",
            ExperimentPhase.INSTRUCTIONS: "Showing Instructions",
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
            Color name for display

        Example:
            >>> ExperimentStateMachine.get_phase_color(ExperimentPhase.SELECTION)
            'green'
        """
        colors = {
            ExperimentPhase.WAITING: "gray",
            ExperimentPhase.REGISTRATION: "orange",
            ExperimentPhase.INSTRUCTIONS: "orange",
            ExperimentPhase.ROBOT_PREPARING: "blue",
            ExperimentPhase.LOADING: "blue",
            ExperimentPhase.QUESTIONNAIRE: "purple",
            ExperimentPhase.SELECTION: "green",
            ExperimentPhase.COMPLETE: "gray",
        }
        return colors.get(phase, "gray")

    @staticmethod
    def is_trial_active(phase: ExperimentPhase) -> bool:
        """
        Check if phase represents an active trial (not waiting, not complete).

        Args:
            phase: Phase to check

        Returns:
            True if trial is active, False otherwise

        Example:
            >>> ExperimentStateMachine.is_trial_active(ExperimentPhase.QUESTIONNAIRE)
            True
            >>> ExperimentStateMachine.is_trial_active(ExperimentPhase.WAITING)
            False
        """
        return phase in [
            ExperimentPhase.REGISTRATION,
            ExperimentPhase.INSTRUCTIONS,
            ExperimentPhase.ROBOT_PREPARING,
            ExperimentPhase.LOADING,
            ExperimentPhase.QUESTIONNAIRE,
            ExperimentPhase.SELECTION,
        ]

    @staticmethod
    def should_show_setup(phase: ExperimentPhase) -> bool:
        """
        Check if moderator should see experiment setup UI.

        Args:
            phase: Current phase

        Returns:
            True if phase is WAITING (setup mode), False otherwise
        """
        return phase == ExperimentPhase.WAITING

    @staticmethod
    def should_show_monitoring(phase: ExperimentPhase) -> bool:
        """
        Check if moderator should see monitoring UI.

        Args:
            phase: Current phase

        Returns:
            True if trial is in any active phase, False if waiting or complete
        """
        return ExperimentStateMachine.is_trial_active(phase)

    @staticmethod
    def should_show_robot_preparing(phase: ExperimentPhase) -> bool:
        """
        Check if UI should show robot preparing message.

        Args:
            phase: Current phase

        Returns:
            True if phase is ROBOT_PREPARING
        """
        return phase == ExperimentPhase.ROBOT_PREPARING

    @staticmethod
    def should_show_questionnaire(phase: ExperimentPhase) -> bool:
        """
        Check if UI should show questionnaire.

        Args:
            phase: Current phase

        Returns:
            True if phase is QUESTIONNAIRE
        """
        return phase == ExperimentPhase.QUESTIONNAIRE

    @staticmethod
    def should_show_selection(phase: ExperimentPhase) -> bool:
        """
        Check if UI should show selection interface (grid/sliders).

        Args:
            phase: Current phase

        Returns:
            True if phase is SELECTION
        """
        return phase == ExperimentPhase.SELECTION

    @staticmethod
    def get_next_phase_with_protocol(
        current_phase: str,
        protocol: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        current_cycle: Optional[int] = None,
    ) -> str:
        """
        Get next phase considering protocol configuration.

        This method provides protocol-aware phase transitions using PhaseEngine
        when a protocol with phase_sequence is provided. Otherwise, falls back
        to standard VALID_TRANSITIONS logic for backward compatibility.

        Args:
            current_phase: Current phase as string (e.g., "waiting", "custom")
            protocol: Optional protocol dict with phase_sequence
            session_id: Optional session ID for PhaseEngine initialization
            current_cycle: Optional current cycle number (for loop logic)

        Returns:
            Next phase ID as string

        Example:
            >>> # With protocol
            >>> protocol = {"phase_sequence": {"phases": [...]}}
            >>> next_phase = ExperimentStateMachine.get_next_phase_with_protocol(
            ...     "waiting",
            ...     protocol=protocol,
            ...     session_id="session-123"
            ... )

            >>> # Without protocol (uses VALID_TRANSITIONS)
            >>> next_phase = ExperimentStateMachine.get_next_phase_with_protocol("waiting")
            'registration'
        """
        # Import PhaseEngine here to avoid circular imports
        try:
            from robotaste.core.phase_engine import PhaseEngine
        except ImportError:
            logger.error(
                "Failed to import PhaseEngine, falling back to VALID_TRANSITIONS"
            )
            protocol = None

        # If protocol has phase_sequence, use PhaseEngine
        if protocol and "phase_sequence" in protocol:
            try:
                engine = PhaseEngine(protocol, session_id or "")
                next_phase = engine.get_next_phase(
                    current_phase, current_cycle=current_cycle
                )
                logger.info(
                    f"Protocol-based transition: {current_phase} → {next_phase} "
                    f"(session: {session_id})"
                )
                return next_phase
            except Exception as e:
                logger.error(
                    f"PhaseEngine failed for session {session_id}: {e}. "
                    f"Falling back to VALID_TRANSITIONS"
                )
                # Fall through to default logic

        # Use existing VALID_TRANSITIONS logic (backward compatible)
        try:
            current_phase_enum = ExperimentPhase(current_phase)
            allowed = ExperimentStateMachine.get_allowed_transitions(current_phase_enum)

            if allowed:
                # Return first allowed transition as string
                next_phase = allowed[0].value
                logger.debug(f"Standard transition: {current_phase} → {next_phase}")
                return next_phase

            # No allowed transitions, stay in current phase
            logger.warning(
                f"No allowed transitions from {current_phase}, staying in current phase"
            )
            return current_phase

        except ValueError:
            # Unknown phase (e.g., custom phase not in enum)
            logger.warning(
                f"Unknown phase '{current_phase}', cannot determine next phase. "
                f"Staying in current phase."
            )
            return current_phase


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_default_phase() -> ExperimentPhase:
    """
    Get the default initial phase for a new session.

    Returns:
        ExperimentPhase.WAITING
    """
    return ExperimentPhase.WAITING


def parse_phase(phase_str: Optional[str]) -> ExperimentPhase:
    """
    Parse phase string with fallback to default.

    Args:
        phase_str: Phase value as string or None

    Returns:
        ExperimentPhase enum (defaults to WAITING if invalid/None)

    Example:
        >>> parse_phase("selection")
        <ExperimentPhase.SELECTION: 'selection'>
        >>> parse_phase("invalid")
        <ExperimentPhase.WAITING: 'waiting'>
        >>> parse_phase(None)
        <ExperimentPhase.WAITING: 'waiting'>
    """
    if not phase_str:
        return ExperimentPhase.WAITING

    phase = ExperimentPhase.from_string(phase_str)
    if phase is None:
        logger.warning(f"Unknown phase '{phase_str}', defaulting to WAITING")
        return ExperimentPhase.WAITING

    return phase


def create_phase_transition_log(
    current_phase: ExperimentPhase,
    new_phase: ExperimentPhase,
    session_id: Optional[str] = None,
    participant_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a structured log entry for phase transitions.

    Useful for tracking and debugging phase changes.

    Args:
        current_phase: Phase before transition
        new_phase: Phase after transition
        session_id: Optional session identifier
        participant_id: Optional participant identifier
        metadata: Optional additional metadata

    Returns:
        Dict with transition details

    Example:
        >>> log = create_phase_transition_log(
        ...     ExperimentPhase.WAITING,
        ...     ExperimentPhase.LOADING,
        ...     session_id="session_123"
        ... )
        >>> log["transition"]
        'waiting -> loading'
    """
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "transition": f"{current_phase.value} -> {new_phase.value}",
        "from_phase": current_phase.value,
        "to_phase": new_phase.value,
        "session_id": session_id,
        "participant_id": participant_id,
        "valid": ExperimentStateMachine.can_transition(current_phase, new_phase),
        "metadata": metadata or {},
    }
