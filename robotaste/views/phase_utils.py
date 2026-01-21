"""
Phase transition utility functions for views.

This module contains shared utilities for managing phase transitions
across different view modules, preventing circular imports.
"""

import logging
from robotaste.core.state_machine import ExperimentPhase
from robotaste.core import state_helpers
from robotaste.data.database import get_session_protocol
from robotaste.core.phase_engine import PhaseEngine

logger = logging.getLogger(__name__)


def transition_to_next_phase(
    current_phase_str: str,
    default_next_phase: ExperimentPhase,
    session_id: str,
    current_cycle: int = None,  # type: ignore
) -> None:
    """
    Transition to next phase using PhaseEngine if available, otherwise use default.

    Args:
        current_phase_str: Current phase as string
        default_next_phase: Default next phase (fallback if no protocol)
        session_id: Session ID
        current_cycle: Current cycle number (optional, for loop logic)
    """
    # Try to load protocol and use PhaseEngine
    protocol = get_session_protocol(session_id)

    if protocol and "phase_sequence" in protocol:
        try:
            phase_engine = PhaseEngine(protocol, session_id)
            next_phase_str = phase_engine.get_next_phase(
                current_phase_str, current_cycle=current_cycle
            )
            next_phase = ExperimentPhase(next_phase_str)
            logger.info(
                f"PhaseEngine transition: {current_phase_str} → {next_phase_str}"
            )
        except Exception as e:
            logger.error(f"PhaseEngine transition failed: {e}, using default")
            next_phase = default_next_phase
    else:
        next_phase = default_next_phase

    # Execute transition
    state_helpers.transition(
        state_helpers.get_current_phase(),
        new_phase=next_phase,
        session_id=session_id,
    )
