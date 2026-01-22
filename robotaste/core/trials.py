"""
RoboTaste Trial Management

Handles trial initialization, click tracking, and sample saving.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
import random
import time
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from robotaste.config.bo_config import get_default_bo_config
from robotaste.data import database as sql
from robotaste.core.calculations import (
    ConcentrationMapper,
    MultiComponentMixture,
    generate_random_position,
    INTERFACE_2D_GRID,
    INTERFACE_SINGLE_INGREDIENT,
)
from robotaste.config.defaults import DEFAULT_INGREDIENT_CONFIG
from robotaste.config.protocol_schema import (
    get_selection_mode_for_cycle,
    get_predetermined_sample,
    get_sample_bank_config,
    get_schedule_index_for_cycle,
    normalize_selection_mode,
)

# Setup logging
logger = logging.getLogger(__name__)


def start_trial(
    user_type: str,
    participant_id: Optional[str] = None,
    method: Optional[str] = None,
    num_ingredients: Optional[int] = None,
    selected_ingredients: Optional[list] = None,
    ingredient_configs: Optional[list] = None,
    protocol_id: Optional[str] = None,
) -> bool:
    """
    Initialize a new trial, either from a protocol or manual configuration.

    Args:
        user_type: User type (moderator/subject)
        participant_id: Optional participant ID. If not provided, fetches from session's user_id.
        method: Concentration mapping method
        num_ingredients: Number of ingredients (1 or 2)
        selected_ingredients: List of ingredient names
        ingredient_configs: List of ingredient configuration dicts
        protocol_id: Optional protocol ID to use

    Returns:
        True if successful, False otherwise
    """
    try:
        from robotaste.data import protocol_repo
        from robotaste.data import database as db
        from robotaste.core.state_machine import ExperimentPhase
        from robotaste.core import state_helpers
        from robotaste.config.questionnaire import get_default_questionnaire_type

        session_id = st.session_state.get("session_id")
        if not session_id:
            st.error("No session ID found. Please create a session first.")
            return False

        # If participant_id not provided, fetch from session's user_id (may be None)
        if not participant_id:
            session = db.get_session(session_id)
            if session:
                participant_id = session.get("user_id")

            if participant_id:
                logger.info(f"Using participant {participant_id} from session {session_id}")
            else:
                logger.info(f"Starting trial without participant (will be linked after registration)")
        else:
            logger.info(f"Using provided participant_id: {participant_id}")

        # --- Configuration Loading ---
        # If a protocol is provided, it is the source of truth.
        if protocol_id:
            logger.info(f"Starting trial for participant {participant_id} using protocol {protocol_id}")
            protocol_config = protocol_repo.get_protocol_by_id(protocol_id)
            if not protocol_config:
                st.error(f"Protocol with ID '{protocol_id}' not found.")
                return False
            
            # Extract settings from protocol
            ingredient_configs = protocol_config.get("ingredients", [])
            num_ingredients = len(ingredient_configs)
            selected_ingredients = [ing['name'] for ing in ingredient_configs]
            # Method is part of the UI config, might be in a sub-dict. Assume linear default.
            method = protocol_config.get("method", "linear") 
            questionnaire_type = protocol_config.get("questionnaire_type", get_default_questionnaire_type())
            bo_config = protocol_config.get("bo_config", get_default_bo_config())
        
        # Otherwise, use manual parameters passed to the function.
        else:
            logger.info(f"Starting trial for participant {participant_id} with manual configuration.")
            if not all([method, num_ingredients is not None, ingredient_configs]):
                st.error("Manual configuration requires method, num_ingredients, and ingredient_configs.")
                return False
            
            # Get config from session state for manual mode
            questionnaire_type = st.session_state.get("selected_questionnaire_type", get_default_questionnaire_type())
            bo_config = st.session_state.get("bo_config", get_default_bo_config())
            protocol_config = {
                "num_ingredients": num_ingredients,
                "interface_type": INTERFACE_2D_GRID if num_ingredients == 2 else INTERFACE_SINGLE_INGREDIENT,
                "method": method,
                "ingredients": ingredient_configs,
                "questionnaire_type": questionnaire_type,
                "bayesian_optimization": bo_config,
            }

        # --- Universal Trial Setup ---

        st.session_state.trial_start_time = time.perf_counter()
        st.session_state.participant = participant_id
        st.session_state.method = method
        st.session_state.num_ingredients = num_ingredients
        st.session_state.ingredients = ingredient_configs
        st.session_state.interface_type = INTERFACE_2D_GRID if num_ingredients == 2 else INTERFACE_SINGLE_INGREDIENT
        
        # The start might not be random in a protocol. This is handled by prepare_cycle_sample.
        # For now, initialize as empty.
        st.session_state.current_tasted_sample = {}

        # Update database with the full config
        question_type_id = sql.get_questionnaire_type_id(questionnaire_type)
        if question_type_id is None:
            st.error(f"Questionnaire type '{questionnaire_type}' not found in database.")
            return False

        # The full config to be saved, whether from protocol or manual
        experiment_config_to_save = {
            **protocol_config,
            "current_cycle": 1,  # Start at cycle 1 (1-indexed)
            "created_at": datetime.now().isoformat(),
        }

        # update_session_with_config handles both creation and update logic
        success_db = sql.update_session_with_config(
            session_id=session_id,
            user_id=participant_id,
            num_ingredients=num_ingredients,
            interface_type=st.session_state.interface_type,
            method=method,
            ingredients=ingredient_configs,
            question_type_id=question_type_id,
            bo_config=bo_config,
            experiment_config=experiment_config_to_save
        )
        
        if not success_db:
            st.error("Failed to save session configuration to the database.")
            return False

        # Use state machine to transition to the next phase
        try:
            current_phase = state_helpers.get_current_phase()

            # If protocol has custom phase sequence, use PhaseEngine to determine next phase
            if protocol_id and protocol_config.get("phase_sequence"):
                from robotaste.core.phase_engine import PhaseEngine
                phase_engine = PhaseEngine(protocol_config, session_id)
                next_phase_str = phase_engine.get_next_phase(current_phase.value, current_cycle=0)
                next_phase = ExperimentPhase(next_phase_str)
                logger.info(f"Using PhaseEngine: {current_phase.value} → {next_phase_str}")
            else:
                # Default behavior: go to registration
                next_phase = ExperimentPhase.REGISTRATION

            state_helpers.transition(
                current_phase=current_phase,
                new_phase=next_phase,
                session_id=session_id,
            )
        except Exception as sm_error:
            logger.warning(f"State machine transition failed: {sm_error}. Using direct assignment.")
            st.session_state.phase = "registration" # Fallback

        st.success(f"Trial started successfully for {participant_id}")

        # === Early pump initialization ===
        # Initialize pumps in background while subject is registering
        # This eliminates the visible delay during ROBOT_PREPARING phase
        try:
            from robotaste.data.protocol_repo import get_protocol_by_id
            from robotaste.core.pump_manager import get_or_create_pumps
            from robotaste.data.database import get_database_connection

            # Get protocol to check if pumps are enabled
            if protocol_id:
                # We already loaded protocol_config above
                pump_config = protocol_config.get("pump_config", {})

                if pump_config.get("enabled", False):
                    logger.info(f"🔌 Pre-initializing pumps for session {session_id}")
                    pumps = get_or_create_pumps(session_id, pump_config)
                    logger.info(f"✅ Pumps pre-initialized ({len(pumps)} pump(s))")
        except Exception as e:
            # Non-fatal: pumps will be initialized later if early init fails
            logger.warning(f"Early pump initialization failed (will retry later): {e}")
        # === END early pump initialization ===

        return True

    except Exception as e:
        st.error(f"An unexpected error occurred while starting the trial: {e}")
        logger.error("start_trial failed", exc_info=True)
        return False


def save_click(
    participant_id: str,
    x: float,
    y: float,
    method: str,
    sample_id: Optional[str] = None,
) -> bool:
    """Save an intermediate click (part of the trajectory)."""
    try:
        # Calculate concentrations for every click
        from robotaste.core.calculations import ConcentrationMapper

        sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
            x, y, method=method
        )

        # Calculate reaction time from trial start
        reaction_time_ms = None

        if hasattr(st.session_state, "trial_start_time"):
            reaction_time_ms = int(
                (time.perf_counter() - st.session_state.trial_start_time) * 1000
            )

        # Create ingredient concentrations dictionary
        ingredient_concentrations = {
            "Sugar": round(sugar_mm, 3),
            "Salt": round(salt_mm, 3),
        }

        # Store click data in session state for trajectory tracking
        # This will be included in selection_data when save_sample_cycle() is called
        if not hasattr(st.session_state, "trajectory_clicks"):
            st.session_state.trajectory_clicks = []

        st.session_state.trajectory_clicks.append(
            {
                "x": x,
                "y": y,
                "concentrations": ingredient_concentrations,
                "reaction_time_ms": reaction_time_ms,
                "sample_id": sample_id,
                "timestamp": time.time(),
            }
        )

        return True

    except Exception as e:
        # logger.error(f"Error saving click: {e}")
        return False


def save_intermediate_click(
    participant_id: str,
    x: float,
    y: float,
    method: str,
    sample_id: Optional[str] = None,
) -> bool:
    """Save an intermediate click to track the subject's path."""
    try:
        return save_click(participant_id, x, y, method, sample_id)
    except Exception as e:
        st.error(f"Error saving intermediate click: {e}")
        return False


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
