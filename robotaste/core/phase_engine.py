"""
Phase Engine for Custom Phase Sequences

This module provides the PhaseEngine class that manages dynamic phase sequences
from protocols, enabling custom phase flows, phase skipping, and auto-advance functionality.

Author: Claude Sonnet 4.5
Date: January 2026
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


# Default phase sequence used when protocol has no custom phase_sequence
DEFAULT_PHASES = [
    {"phase_id": "waiting", "phase_type": "builtin", "required": True},
    {"phase_id": "registration", "phase_type": "builtin", "required": False},
    {"phase_id": "instructions", "phase_type": "builtin", "required": True},
    {"phase_id": "experiment_loop", "phase_type": "loop", "required": True},
    {"phase_id": "completion", "phase_type": "builtin", "required": True},
]


@dataclass
class PhaseDefinition:
    """Single phase configuration from protocol.

    Attributes:
        phase_id: Unique identifier for the phase (e.g., "waiting", "custom_intro")
        phase_type: Type of phase ("builtin", "custom", "loop")
        required: If False, phase can be skipped
        duration_ms: Duration in milliseconds for auto-advance
        auto_advance: If True, automatically transition after duration_ms
        content: Custom phase content (for custom phases)
        loop_config: Configuration for loop phases
    """

    phase_id: str
    phase_type: str
    required: bool = True
    duration_ms: Optional[int] = None
    auto_advance: bool = False
    content: Optional[Dict[str, Any]] = None
    loop_config: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Validate phase definition after initialization."""
        if self.auto_advance and not self.duration_ms:
            raise ValueError(
                f"Phase {self.phase_id}: auto_advance=True requires duration_ms"
            )

        if self.duration_ms is not None and self.duration_ms <= 0:
            raise ValueError(f"Phase {self.phase_id}: duration_ms must be positive")


class PhaseEngine:
    """Manages dynamic phase sequences from protocols.

    The PhaseEngine handles:
    - Parsing protocol phase sequences
    - Determining next phase based on protocol rules
    - Handling phase skipping (optional phases)
    - Managing experiment loops (LOADING → QUESTIONNAIRE → SELECTION cycle)
    - Auto-advance functionality
    - Circuit breaker to prevent infinite loops

    Example:
        >>> protocol = {
        ...     "phase_sequence": {
        ...         "phases": [
        ...             {"phase_id": "waiting", "phase_type": "builtin", "required": True},
        ...             {"phase_id": "custom_intro", "phase_type": "custom", "content": {...}},
        ...             {"phase_id": "experiment_loop", "phase_type": "loop"},
        ...             {"phase_id": "completion", "phase_type": "builtin"}
        ...         ]
        ...     }
        ... }
        >>> engine = PhaseEngine(protocol, "session-123")
        >>> next_phase = engine.get_next_phase("waiting")
        >>> print(next_phase)  # "custom_intro"
    """

    MAX_TRANSITIONS = 100  # Circuit breaker limit

    def __init__(self, protocol: Dict[str, Any], session_id: str):
        """Initialize PhaseEngine with protocol and session.

        Args:
            protocol: Protocol dictionary containing phase_sequence (optional)
            session_id: Session ID for logging and state tracking
        """
        self.protocol = protocol
        self.session_id = session_id
        self.transition_count = 0

        # Parse phase sequence from protocol or use default
        try:
            self.phase_sequence: List[PhaseDefinition] = self._parse_phase_sequence()
            logger.info(
                f"PhaseEngine initialized for session {session_id} "
                f"with {len(self.phase_sequence)} phases"
            )
        except Exception as e:
            logger.error(
                f"Failed to parse phase sequence for session {session_id}: {e}. "
                f"Falling back to DEFAULT_PHASES"
            )
            self.phase_sequence = self._parse_default_phases()

    def _parse_default_phases(self) -> List[PhaseDefinition]:
        """Parse DEFAULT_PHASES into PhaseDefinition objects.

        Returns:
            List of PhaseDefinition objects from DEFAULT_PHASES
        """
        phases = []
        for phase_dict in DEFAULT_PHASES:
            try:
                phases.append(PhaseDefinition(**phase_dict))
            except Exception as e:
                logger.error(f"Error parsing default phase {phase_dict}: {e}")
        return phases

    def _parse_phase_sequence(self) -> List[PhaseDefinition]:
        """Parse protocol's phase_sequence into PhaseDefinition objects.

        Returns:
            List of PhaseDefinition objects

        Raises:
            ValueError: If phase_sequence structure is invalid
        """
        # If no phase_sequence in protocol, use DEFAULT_PHASES
        if "phase_sequence" not in self.protocol:
            logger.info("No phase_sequence in protocol, using DEFAULT_PHASES")
            return self._parse_default_phases()

        phase_sequence_config = self.protocol["phase_sequence"]

        # Handle both dict with 'phases' key and direct list
        if isinstance(phase_sequence_config, dict):
            phases_list = phase_sequence_config.get("phases", [])
        elif isinstance(phase_sequence_config, list):
            phases_list = phase_sequence_config
        else:
            logger.warning("Invalid phase_sequence format, using DEFAULT_PHASES")
            return self._parse_default_phases()

        if not phases_list:
            logger.info("Empty phase_sequence, using DEFAULT_PHASES")
            return self._parse_default_phases()

        # Parse each phase dict into PhaseDefinition
        phases = []
        for idx, phase_dict in enumerate(phases_list):
            try:
                phase_def = PhaseDefinition(
                    phase_id=phase_dict.get("phase_id", f"phase_{idx}"),
                    phase_type=phase_dict.get("phase_type", "builtin"),
                    required=phase_dict.get("required", True),
                    duration_ms=phase_dict.get("duration_ms"),
                    auto_advance=phase_dict.get("auto_advance", False),
                    content=phase_dict.get("content"),
                    loop_config=phase_dict.get("loop_config"),
                )
                phases.append(phase_def)
            except ValueError as e:
                logger.error(f"Invalid phase definition at index {idx}: {e}")
                # Skip invalid phases

        # Validate that we have at least one phase
        if not phases:
            logger.warning("No valid phases in sequence, using DEFAULT_PHASES")
            return self._parse_default_phases()

        return phases

    def _find_phase_index(self, phase_id: str) -> int:
        """Find index of phase in sequence by phase_id.

        Args:
            phase_id: Phase ID to find

        Returns:
            Index of phase in sequence, or -1 if not found
        """
        for idx, phase in enumerate(self.phase_sequence):
            if phase.phase_id == phase_id:
                return idx
        return -1

    def _is_in_loop(self, phase_id: str) -> bool:
        """Check if phase is part of experiment loop.

        The experiment loop consists of: loading → questionnaire → selection

        Args:
            phase_id: Phase ID to check

        Returns:
            True if phase is part of loop
        """
        return phase_id in ["loading", "questionnaire", "selection", "robot_preparing"]

    def _should_stop_experiment(self, current_cycle: int) -> bool:
        """Determine if experiment should stop based on stopping criteria.

        Args:
            current_cycle: Current cycle number

        Returns:
            True if experiment should stop
        """
        # Check stopping criteria from protocol
        stopping_criteria = self.protocol.get("stopping_criteria", {})

        # Max cycles check
        max_cycles = stopping_criteria.get("max_cycles")
        if max_cycles and current_cycle >= max_cycles:
            logger.info(f"Stopping experiment: reached max_cycles ({max_cycles})")
            return True

        # Additional stopping criteria can be added here
        # For now, use max_cycles as primary criterion

        return False

    def _get_phase_after_loop(self) -> str:
        """Get the phase that comes after the experiment loop.

        Returns:
            Phase ID that follows the experiment_loop in sequence
        """
        # Find experiment_loop in sequence
        loop_idx = self._find_phase_index("experiment_loop")

        if loop_idx == -1:
            # No explicit loop phase, default to completion
            return "completion"

        # Return next phase after loop
        if loop_idx + 1 < len(self.phase_sequence):
            return self.phase_sequence[loop_idx + 1].phase_id

        # No phase after loop, default to completion
        return "completion"

    def _get_next_loop_phase(self, current_phase: str, current_cycle: int) -> str:
        """Determine next phase within experiment loop.

        Args:
            current_phase: Current phase ID
            current_cycle: Current cycle number

        Returns:
            Next phase ID in loop
        """
        # Standard loop progression
        # NOTE: Stopping check is now handled in subject.py after QUESTIONNAIRE
        if current_phase == "selection":
            return "loading"
        elif current_phase == "loading" or current_phase == "robot_preparing":
            return "questionnaire"
        elif current_phase == "questionnaire":
            # Always return to selection - stopping is handled before transition
            return "selection"

        # Unknown loop phase, exit loop
        logger.warning(f"Unknown loop phase: {current_phase}, exiting loop")
        return self._get_phase_after_loop()

    def get_next_phase(
        self,
        current_phase: str,
        skip_optional: bool = False,
        current_cycle: Optional[int] = None,
    ) -> str:
        """Determine next phase based on protocol sequence.

        Handles:
        - Sequential phase progression
        - Optional phase skipping
        - Experiment loop entry/exit
        - Circuit breaker for infinite loops

        Args:
            current_phase: Current phase ID as string
            skip_optional: If True, skip optional (non-required) phases
            current_cycle: Current cycle number (for loop logic)

        Returns:
            Next phase ID as string
        """
        # Circuit breaker check
        self.transition_count += 1
        if self.transition_count > self.MAX_TRANSITIONS:
            logger.error(
                f"PhaseEngine circuit breaker triggered: "
                f"{self.transition_count} transitions. Forcing completion."
            )
            return "completion"

        # Check if we're in experiment loop
        if self._is_in_loop(current_phase):
            next_phase = self._get_next_loop_phase(current_phase, current_cycle or 0)
            logger.info(
                f"Session {self.session_id}: Loop phase transition "
                f"{current_phase} → {next_phase} (cycle {current_cycle})"
            )
            return next_phase

        # Find current phase in sequence
        current_idx = self._find_phase_index(current_phase)

        if current_idx == -1:
            # Current phase not in sequence, check if it's CUSTOM
            if current_phase == "custom":
                # Need to handle custom phases differently
                # For now, find first phase after custom phases
                logger.warning(
                    f"Custom phase handling needed for session {self.session_id}"
                )
                # Default to going to next phase in sequence
                current_idx = 0

        # Find next phase
        next_idx = current_idx + 1

        while next_idx < len(self.phase_sequence):
            next_phase_def = self.phase_sequence[next_idx]

            # Check if this phase is the experiment loop
            if next_phase_def.phase_type == "loop":
                # Enter the loop - start with selection (prepare sample first)
                logger.info(f"Session {self.session_id}: Entering experiment loop")
                return "selection"

            # If skipping optional phases and this phase is optional, skip it
            if skip_optional and not next_phase_def.required:
                logger.info(
                    f"Session {self.session_id}: Skipping optional phase "
                    f"{next_phase_def.phase_id}"
                )
                next_idx += 1
                continue

            # Found next phase
            logger.info(
                f"Session {self.session_id}: Phase transition "
                f"{current_phase} → {next_phase_def.phase_id}"
            )
            return next_phase_def.phase_id

        # No more phases, go to completion
        logger.info(
            f"Session {self.session_id}: Reached end of sequence, going to completion"
        )
        return "completion"

    def should_auto_advance(self, current_phase: str) -> Tuple[bool, int]:
        """Check if phase should auto-advance.

        Args:
            current_phase: Current phase ID

        Returns:
            Tuple of (should_advance, duration_ms)
            - should_advance: True if phase has auto_advance enabled
            - duration_ms: Duration in milliseconds (0 if no auto-advance)
        """
        # Find phase in sequence
        phase_idx = self._find_phase_index(current_phase)

        if phase_idx == -1:
            return (False, 0)

        phase_def = self.phase_sequence[phase_idx]

        if phase_def.auto_advance and phase_def.duration_ms:
            return (True, phase_def.duration_ms)

        return (False, 0)

    def can_skip_phase(self, phase: str) -> bool:
        """Check if phase is optional (can be skipped).

        Args:
            phase: Phase ID to check

        Returns:
            True if phase is optional (not required)
        """
        phase_idx = self._find_phase_index(phase)

        if phase_idx == -1:
            return False

        phase_def = self.phase_sequence[phase_idx]
        return not phase_def.required

    def get_phase_content(self, phase: str) -> Optional[Dict[str, Any]]:
        """Get custom content for phase, if any.

        Args:
            phase: Phase ID

        Returns:
            Content dictionary for custom phases, None for builtin phases
        """
        phase_idx = self._find_phase_index(phase)

        if phase_idx == -1:
            return None

        phase_def = self.phase_sequence[phase_idx]

        # Only custom phases have content
        if phase_def.phase_type == "custom" and phase_def.content:
            return phase_def.content

        return None
