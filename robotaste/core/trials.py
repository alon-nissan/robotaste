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

# Setup logging
logger = logging.getLogger(__name__)


def start_trial(
    user_type: str,
    participant_id: str,
    method: str,
    num_ingredients: int = 2,
    selected_ingredients: Optional[list] = None,
    ingredient_configs: Optional[list] = None,
) -> bool:
    """
    Initialize a new trial with random starting position using new database schema.

    Args:
        user_type: 'mod' or 'sub'
        participant_id: Unique participant identifier
        method: Concentration mapping method
        num_ingredients: Number of ingredients
        selected_ingredients: List of selected ingredient names (e.g., ['Sugar', 'Salt', 'Citric Acid'])
        ingredient_configs: List of ingredient configuration dicts with custom ranges

    Returns:
        Success status
    """
    try:
        from robotaste.data.database import update_session_state

        # Generate random starting position for grid interface
        x, y = generate_random_position()

        # Determine interface type
        interface_type = (
            INTERFACE_2D_GRID if num_ingredients == 2 else INTERFACE_SINGLE_INGREDIENT
        )

        # Get session identifiers - session_id for DB, session_code for display
        session_id = st.session_state.get("session_id")
        session_code = st.session_state.get("session_code")
        if not session_id:
            st.error("No session ID found. Please create a session first.")
        use_random_start = st.session_state.get("use_random_start", False)

        # Get ingredient configuration - FIXED: Use moderator's actual ingredient selection
        if ingredient_configs:
            # Use moderator's custom configuration with custom concentration ranges
            ingredients = ingredient_configs
            logger.info(
                f"Using custom ingredient configuration: {[ing['name'] for ing in ingredients]}"
            )
        elif selected_ingredients:
            # Build configuration from selected ingredient names
            ingredients = [
                ing
                for ing in DEFAULT_INGREDIENT_CONFIG
                if ing["name"] in selected_ingredients
            ]
            logger.info(
                f"Using selected ingredients: {[ing['name'] for ing in ingredients]}"
            )
        else:
            # Fallback to defaults (for backward compatibility with old code)
            ingredients = DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
            logger.warning(
                f"Using default ingredient configuration (first {num_ingredients} ingredients)"
            )

        # Validate we have the correct number of ingredients
        if len(ingredients) != num_ingredients:
            logger.error(
                f"Ingredient count mismatch: expected {num_ingredients}, got {len(ingredients)}"
            )
            st.error(
                f"Configuration error: Expected {num_ingredients} ingredients, got {len(ingredients)}"
            )

        # Generate random starting positions if enabled
        random_slider_values = {}
        random_concentrations = {}
        if use_random_start and interface_type == INTERFACE_SINGLE_INGREDIENT:
            # Generate random starting positions for each ingredient (10-90%)
            mixture = MultiComponentMixture(ingredients)
            for ingredient in ingredients:
                random_percent = random.uniform(10.0, 90.0)
                random_slider_values[ingredient["name"]] = random_percent

            # Calculate actual concentrations from percentages
            concentrations = mixture.calculate_concentrations_from_sliders(
                random_slider_values
            )
            for ingredient_name, conc_data in concentrations.items():
                random_concentrations[ingredient_name] = round(
                    conc_data["actual_concentration_mM"], 3
                )

            # Initial random positions are stored in session state
            # (st.session_state.random_slider_values for single ingredient)
            # In the new 6-phase workflow, initial positions don't need separate DB storage
            # They will be included in selection_data when save_sample_cycle() is called

        # Update Streamlit session state
        st.session_state.trial_start_time = time.perf_counter()
        st.session_state.participant = participant_id
        st.session_state.method = method
        st.session_state.num_ingredients = num_ingredients
        st.session_state.interface_type = interface_type
        st.session_state.ingredients = (
            ingredients  # FIXED: Store for subject interface to use
        )

        # Store initial positions in session state for immediate use
        if random_slider_values:
            st.session_state.random_slider_values = random_slider_values
        else:
            st.session_state.random_slider_values = {}

        # Store initial position in session state (for backward compatibility)
        st.session_state.x = x
        st.session_state.y = y

        # Store the initial random concentration as the "current tasted sample" for cycle 1
        # This will be used when saving the first cycle's data after questionnaire
        if random_concentrations:
            # Slider interface - use calculated random concentrations
            st.session_state.current_tasted_sample = random_concentrations.copy()
        elif interface_type == INTERFACE_2D_GRID:
            # Grid interface - calculate concentrations from random x,y position
            sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
                x, y, method=method
            )
            st.session_state.current_tasted_sample = {
                "Sugar": round(sugar_mm, 3),
                "Salt": round(salt_mm, 3),
            }
        else:
            st.session_state.current_tasted_sample = {}

        # Note: Cycle 0 data is NOT saved here to avoid duplicate sample IDs.
        # The initial random sample will be saved with the first questionnaire answer,
        # creating a single sample ID that links the initial concentrations with the first response.

        # Store experiment configuration in session database for subject synchronization
        try:
            from robotaste.core.state_machine import ExperimentPhase
            from robotaste.core import state_helpers

            # Get questionnaire type from session state (set by moderator)
            from robotaste.config.questionnaire import get_default_questionnaire_type

            questionnaire_type = st.session_state.get(
                "selected_questionnaire_type", get_default_questionnaire_type()
            )

            experiment_config = {
                "num_ingredients": num_ingredients,
                "interface_type": interface_type,
                "method": method,
                "current_cycle": 0,  # Initialize cycle counter to 0
                "initial_concentrations": st.session_state.current_tasted_sample,  # Store for subject interface sync
                "initial_slider_values": random_slider_values,  # Store random slider positions for subject interface
                "questionnaire_type": questionnaire_type,  # Store selected questionnaire type
                "bayesian_optimization": st.session_state.get(
                    "bo_config", get_default_bo_config()
                ),  # Store BO configuration
                "ingredients": [
                    ing for ing in ingredients
                ],  # Store ingredient configuration
                "ingredient_metadata": {
                    "ingredient_names": [ing["name"] for ing in ingredients],
                    "ingredient_order": list(range(len(ingredients))),
                    "custom_ranges_used": ingredient_configs is not None,
                    "selected_by_moderator": selected_ingredients is not None,
                },
            }

            # Update experiment config in database
            # Get questionnaire_type_id from database
            question_type_id = sql.get_questionnaire_type_id(questionnaire_type)

            # Serialize ingredients to JSON
            ingredients_json = json.dumps([ing for ing in ingredients])

            with sql.get_database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE sessions
                    SET experiment_config = ?,
                        question_type_id = ?,
                        ingredients = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = ?
                """,
                    (
                        json.dumps(experiment_config),
                        question_type_id,
                        ingredients_json,
                        session_id,
                    ),  # Use session_id for DB
                )
                conn.commit()

            # Use state machine to transition to REGISTRATION phase
            # This follows the valid transition: WAITING → REGISTRATION
            try:
                current_phase = state_helpers.get_current_phase()
                state_helpers.transition(
                    current_phase=current_phase,
                    new_phase=ExperimentPhase.REGISTRATION,
                    session_id=session_id,  # Use session_id for DB
                )
            except Exception as sm_error:
                # Fallback: directly set phase if state machine fails
                logger.warning(
                    f"State machine transition failed: {sm_error}. Using direct assignment."
                )
                st.session_state.phase = "registration"

        except Exception as e:
            st.warning(f"Could not update session config: {e}")

        # Success message
        st.success(f"Trial started successfully for {participant_id}")
        return True

    except Exception as e:
        st.error(f"Error starting trial: {e}")
        import traceback

        st.error(f"Full traceback: {traceback.format_exc()}")
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
