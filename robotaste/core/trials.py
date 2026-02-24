"""
RoboTaste Trial Management

Handles mixed-mode sample selection and cycle preparation.

Author: RoboTaste Team
Version: 4.0 (React + API Architecture)
"""

import logging
from typing import Dict, Any

from robotaste.data import database as sql
from robotaste.config.protocol_schema import (
    get_selection_mode_for_cycle,
    get_predetermined_sample,
    get_sample_bank_config,
    get_schedule_index_for_cycle,
    normalize_selection_mode,
)

# Setup logging
logger = logging.getLogger(__name__)

# =============================================================================
# Mixed-Mode Sample Selection (Protocol-Driven)
# =============================================================================


def get_selection_mode_for_cycle_runtime(session_id: str, cycle_number: int) -> str:
    """
    Determine selection mode for current cycle from session's protocol.

    Args:
        session_id: Session UUID
        cycle_number: Current cycle number (1-indexed)

    Returns:
        Selection mode: "user_selected", "bo_selected", or "predetermined"
        Falls back to "user_selected" if no protocol or cycle not in schedule.
    """
    try:
        # Load session to get protocol
        session = sql.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found, defaulting to user_selected mode")
            return "user_selected"

        # Check if session has a protocol_id
        # First check experiment_config for protocol data
        experiment_config = session.get("experiment_config", {})
        protocol = None

        # Protocol might be embedded in experiment_config or referenced by protocol_id
        if "sample_selection_schedule" in experiment_config:
            # Protocol data is embedded in experiment_config
            protocol = experiment_config
        else:
            # Try to load protocol from database using protocol_id
            from robotaste.data import protocol_repo

            # Get protocol_id from session (stored during session creation)
            protocol_id_from_session = experiment_config.get("protocol_id")
            if protocol_id_from_session:
                protocol_obj = protocol_repo.get_protocol_by_id(protocol_id_from_session)
                if protocol_obj:
                    protocol = protocol_obj.get("protocol_json", {})

        if not protocol or "sample_selection_schedule" not in protocol:
            logger.info(f"No protocol with sample_selection_schedule found for session {session_id}, using user_selected mode")
            return "user_selected"

        # Use protocol_schema helper to get mode
        mode = get_selection_mode_for_cycle(protocol, cycle_number)
        logger.info(f"Session {session_id}, cycle {cycle_number}: mode = {mode}")
        return mode

    except Exception as e:
        logger.error(f"Error determining selection mode: {e}", exc_info=True)
        return "user_selected"


def prepare_cycle_sample(session_id: str, cycle_number: int) -> Dict[str, Any]:
    """
    Unified function to prepare sample for any cycle based on protocol.

    This is the main API for Developer B's UI to determine what to show.

    Args:
        session_id: Session UUID
        cycle_number: Current cycle number (1-indexed)

    Returns:
        Dictionary with:
        {
            "mode": str,  # "user_selected", "bo_selected", "predetermined"
            "concentrations": Dict[str, float] | None,  # Concentrations if predetermined/BO
            "metadata": {
                "is_predetermined": bool,
                "allows_override": bool,
                "show_suggestion": bool,
                "acquisition_function": str | None,  # For BO mode
                "acquisition_params": dict | None,  # For BO mode
                "predicted_value": float | None,  # For BO mode
                "uncertainty": float | None  # For BO mode
            }
        }
    """
    try:
        # Determine mode from protocol
        mode = get_selection_mode_for_cycle_runtime(session_id, cycle_number)

        # Normalize mode for backward compatibility (predetermined -> predetermined_absolute)
        normalized_mode = normalize_selection_mode(mode)

        # Initialize result
        result = {
            "mode": normalized_mode,
            "concentrations": None,
            "metadata": {
                "is_predetermined": False,
                "allows_override": False,
                "show_suggestion": False
            }
        }

        # Handle each mode
        if normalized_mode == "predetermined_absolute":
            # Get predetermined concentrations from protocol
            session = sql.get_session(session_id)
            if session:
                experiment_config = session.get("experiment_config", {})
                protocol = None

                # Get protocol (same logic as get_selection_mode_for_cycle_runtime)
                if "sample_selection_schedule" in experiment_config:
                    protocol = experiment_config
                else:
                    from robotaste.data import protocol_repo
                    protocol_id_from_session = experiment_config.get("protocol_id")
                    if protocol_id_from_session:
                        protocol_obj = protocol_repo.get_protocol_by_id(protocol_id_from_session)
                        if protocol_obj:
                            protocol = protocol_obj.get("protocol_json", {})

                if protocol:
                    concentrations = get_predetermined_sample(protocol, cycle_number)
                    if concentrations:
                        result["concentrations"] = concentrations
                        result["metadata"]["is_predetermined"] = True
                        logger.info(f"Predetermined sample for cycle {cycle_number}: {concentrations}")
                    else:
                        logger.warning(f"No predetermined sample found for cycle {cycle_number}")

        elif normalized_mode == "predetermined_randomized":
            # Get sample from randomized bank
            from robotaste.core.sample_bank import get_next_sample_from_bank

            session = sql.get_session(session_id)
            if session:
                experiment_config = session.get("experiment_config", {})
                protocol = None

                # Get protocol (same logic as predetermined_absolute)
                if "sample_selection_schedule" in experiment_config:
                    protocol = experiment_config
                else:
                    from robotaste.data import protocol_repo
                    protocol_id_from_session = experiment_config.get("protocol_id")
                    if protocol_id_from_session:
                        protocol_obj = protocol_repo.get_protocol_by_id(protocol_id_from_session)
                        if protocol_obj:
                            protocol = protocol_obj.get("protocol_json", {})

                if protocol:
                    # Get sample bank config and schedule index
                    bank_config = get_sample_bank_config(protocol, cycle_number)
                    schedule_index = get_schedule_index_for_cycle(protocol, cycle_number)

                    if bank_config and schedule_index >= 0:
                        try:
                            # Get cycle_range_start from the schedule entry
                            schedule = protocol.get("sample_selection_schedule", [])
                            cycle_range_start = 1  # Default
                            if schedule_index < len(schedule):
                                cycle_range = schedule[schedule_index].get("cycle_range", {})
                                cycle_range_start = cycle_range.get("start", 1)

                            concentrations = get_next_sample_from_bank(
                                session_id,
                                schedule_index,
                                bank_config,
                                cycle_number,
                                cycle_range_start
                            )
                            result["concentrations"] = concentrations
                            result["metadata"]["is_predetermined"] = True
                            result["metadata"]["from_bank"] = True
                            logger.info(f"Sample from bank for cycle {cycle_number}: {concentrations}")
                        except Exception as e:
                            logger.error(f"Error getting sample from bank: {e}", exc_info=True)
                    else:
                        logger.warning(f"No sample bank config found for cycle {cycle_number}")

        elif normalized_mode == "bo_selected":
            # Get BO suggestion
            from robotaste.core.bo_integration import get_bo_suggestion_for_session

            session = sql.get_session(session_id)
            if session:
                participant_id = session.get("user_id", "unknown")
                bo_suggestion = get_bo_suggestion_for_session(session_id, participant_id)

                if bo_suggestion:
                    result["concentrations"] = bo_suggestion.get("concentrations")
                    result["metadata"]["show_suggestion"] = True

                    # Check protocol config for allow_override
                    experiment_config = session.get("experiment_config", {})
                    schedule = experiment_config.get("sample_selection_schedule", [])

                    for entry in schedule:
                        cycle_range = entry.get("cycle_range", {})
                        if cycle_range.get("start", 0) <= cycle_number <= cycle_range.get("end", 0):
                            config = entry.get("config", {})
                            result["metadata"]["allows_override"] = config.get("allow_override", True)
                            break

                    # Include BO metadata
                    result["metadata"]["acquisition_function"] = bo_suggestion.get("acquisition_function")
                    result["metadata"]["acquisition_params"] = bo_suggestion.get("acquisition_params", {})
                    result["metadata"]["predicted_value"] = bo_suggestion.get("predicted_value")
                    result["metadata"]["uncertainty"] = bo_suggestion.get("uncertainty")

                    logger.info(f"BO suggestion for cycle {cycle_number}: {result['concentrations']}")
                else:
                    logger.info(f"BO not ready for cycle {cycle_number}, falling back to user selection")
                    result["mode"] = "user_selected"

        else:  # user_selected
            # No concentrations needed, user chooses
            logger.info(f"User selection mode for cycle {cycle_number}")

        return result

    except Exception as e:
        logger.error(f"Error preparing cycle sample: {e}", exc_info=True)
        # Fallback to user selection on error
        return {
            "mode": "user_selected",
            "concentrations": None,
            "metadata": {
                "is_predetermined": False,
                "allows_override": False,
                "show_suggestion": False
            }
        }


def should_use_bo_for_cycle(session_id: str, cycle_number: int) -> bool:
    """
    Check if Bayesian Optimization should be used for a specific cycle.

    This is a convenience wrapper around prepare_cycle_sample() that returns
    a simple boolean for checking if BO mode is active.

    Args:
        session_id: Session UUID
        cycle_number: Cycle number (1-indexed)

    Returns:
        True if mode is "bo_selected", False otherwise

    Example:
        >>> if should_use_bo_for_cycle(session_id, 5):
        ...     print("Using BO for cycle 5")
        ... else:
        ...     print("Not using BO for cycle 5")
    """
    try:
        cycle_data = prepare_cycle_sample(session_id, cycle_number)
        return cycle_data['mode'] == 'bo_selected'
    except Exception as e:
        logger.error(f"Error checking BO mode for cycle: {e}")
        return False
