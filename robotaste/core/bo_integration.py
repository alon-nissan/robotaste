"""
RoboTaste Bayesian Optimization Integration

Handles BO suggestion generation for sessions.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import logging
from typing import Optional, Dict, Any

from robotaste.data import database as sql
from robotaste.core.calculations import ConcentrationMapper
from robotaste.components.canvas import CANVAS_SIZE

# Setup logging
logger = logging.getLogger(__name__)


def should_use_bo_for_cycle(session_id: str, cycle_number: int) -> bool:
    """
    Check if current cycle should use BO mode per protocol.

    Args:
        session_id: Session UUID
        cycle_number: Current cycle number (1-indexed)

    Returns:
        True if BO should be used for this cycle, False otherwise
    """
    try:
        from robotaste.core.trials import get_selection_mode_for_cycle_runtime

        mode = get_selection_mode_for_cycle_runtime(session_id, cycle_number)
        return mode == "bo_selected"

    except Exception as e:
        logger.error(f"Error checking BO mode for cycle: {e}")
        return False


def get_bo_suggestion_for_session(
    session_id: str, participant_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get Bayesian Optimization suggestion for the next sample.

    This function checks if BO should be active (cycle >= 3), trains the BO model
    from existing data, generates candidate samples, and returns the best suggestion
    with interface-specific coordinates.

    Args:
        session_id: Session identifier for database queries
        participant_id: Participant identifier

    Returns:
        Dictionary with BO suggestion or None if BO not ready/active:
        {
            "concentrations": {"Sugar": 42.3, "Salt": 6.7, ...},
            "predicted_value": 7.8,
            "uncertainty": 0.5,
            "acquisition_value": 0.0234,
            "grid_coordinates": {"x": 250, "y": 300},  # For 2D grid only
            "slider_values": {"Sugar": 65, "Salt": 42, ...},  # For sliders only
            "mode": "bayesian_optimization",
            "is_protocol_driven": bool,  # True if from protocol bo_selected mode
            "allows_override": bool  # True if user can override (from protocol config)
        }
    """
    try:
        from robotaste.core.bo_utils import train_bo_model_for_participant
        from robotaste.core.bo_engine import (
            generate_candidate_grid_2d,
            generate_candidates_latin_hypercube,
        )

        # Get current cycle and experiment config
        current_cycle = sql.get_current_cycle(session_id)
        session = sql.get_session(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found")
            return None

        experiment_config = session.get("experiment_config", {})
        bo_config = experiment_config.get("bayesian_optimization", {})

        # Check if BO is enabled
        if not bo_config.get("enabled", True):
            logger.info("BO disabled for this session")
            return None

        # Check if we have enough samples (default: 3, meaning cycle >= 3)
        min_samples = bo_config.get("min_samples_for_bo", 3)
        if current_cycle < min_samples:
            logger.info(f"BO not ready: cycle {current_cycle} < min {min_samples}")
            return None

        # Train BO model
        logger.info(f"Training BO model for cycle {current_cycle}")
        bo_model = train_bo_model_for_participant(
            participant_id=participant_id, session_id=session_id, bo_config=bo_config
        )

        if bo_model is None:
            logger.warning("BO model training failed")
            return None

        # Get ingredient configuration
        ingredients = experiment_config.get("ingredients", [])
        num_ingredients = len(ingredients)

        # Generate candidates based on interface type
        if num_ingredients == 2:
            # 2D Grid interface - use grid sampling
            ingredient_ranges = {
                ing["name"]: (ing["min_concentration"], ing["max_concentration"])
                for ing in ingredients
            }

            # Get concentration ranges for the two ingredients
            ranges_list = list(ingredient_ranges.values())
            candidates = generate_candidate_grid_2d(
                sugar_range=ranges_list[0],
                salt_range=ranges_list[1],
                n_points=bo_config.get("n_candidates_grid", 20),
            )
        else:
            # Slider interface - use Latin Hypercube Sampling
            ingredient_ranges = {
                ing["name"]: (ing["min_concentration"], ing["max_concentration"])
                for ing in ingredients
            }
            candidates = generate_candidates_latin_hypercube(
                ranges=ingredient_ranges,
                n_candidates=bo_config.get("n_candidates_lhs", 1000),
                random_state=bo_config.get("random_state", 42),
            )

        # Determine max_cycles based on dimensionality
        stopping_criteria = bo_config.get("stopping_criteria", {})
        if num_ingredients == 2:
            max_cycles = stopping_criteria.get("max_cycles_2d", 50)
        else:
            max_cycles = stopping_criteria.get("max_cycles_1d", 30)

        # Get BO suggestion with adaptive acquisition parameters
        suggestion = bo_model.suggest_next_sample(
            candidates=candidates,
            acquisition=bo_config.get("acquisition_function", "ei"),
            current_cycle=current_cycle,
            max_cycles=max_cycles,
            # Note: xi/kappa will be computed adaptively if adaptive_acquisition=True
            # Otherwise, config defaults will be used
        )

        if not suggestion:
            logger.warning("BO suggestion failed")
            return None

        # Extract concentrations
        concentrations = suggestion["best_candidate_dict"]

        # Build result dictionary
        result = {
            "concentrations": concentrations,
            "predicted_value": suggestion.get("predicted_value"),
            "uncertainty": suggestion.get("uncertainty"),
            "acquisition_value": suggestion.get("acquisition_value"),
            "acquisition_function": suggestion.get("acquisition_function"),  # ei or ucb
            "acquisition_params": suggestion.get(
                "acquisition_params", {}
            ),  # Store xi/kappa for tracking
            "current_cycle": current_cycle,
            "max_cycles": max_cycles,
            "mode": "bayesian_optimization",
        }

        # Convert to interface-specific coordinates
        if num_ingredients == 2:
            # Convert concentrations to grid coordinates (x, y)
            ingredient_names = list(concentrations.keys())
            sugar_conc = concentrations[ingredient_names[0]]
            salt_conc = concentrations[ingredient_names[1]]

            # Get the mapping method from config
            method = experiment_config.get("method", "logarithmic")

            # Get concentration ranges
            ingredient_ranges_dict = {
                ing["name"]: (ing["min_concentration"], ing["max_concentration"])
                for ing in ingredients
            }
            sugar_range = ingredient_ranges_dict[ingredient_names[0]]
            salt_range = ingredient_ranges_dict[ingredient_names[1]]

            # Use ConcentrationMapper to convert back to coordinates
            x, y = ConcentrationMapper.map_concentrations_to_coordinates(
                sugar_mm=sugar_conc,
                salt_mm=salt_conc,
                method=method,
                sugar_range=sugar_range,
                salt_range=salt_range,
                canvas_size=CANVAS_SIZE,
            )

            # Clamp coordinates to canvas bounds [0, CANVAS_SIZE-1] to ensure visibility
            # Canvas is 0-indexed, so valid range is [0, 499] not [0, 500]
            result["grid_coordinates"] = {
                "x": max(0, min(CANVAS_SIZE - 1, int(x))),
                "y": max(0, min(CANVAS_SIZE - 1, int(y))),
            }

        else:
            # Convert concentrations to slider percentages (0-100)
            slider_values = {}
            for ing in ingredients:
                ing_name = ing["name"]
                conc = concentrations.get(ing_name, 0)
                min_conc = ing["min_concentration"]
                max_conc = ing["max_concentration"]

                # Convert to percentage (0-100)
                if max_conc > min_conc:
                    percentage = ((conc - min_conc) / (max_conc - min_conc)) * 100
                    slider_values[ing_name] = max(0, min(100, int(percentage)))
                else:
                    slider_values[ing_name] = 0

            result["slider_values"] = slider_values

        # Check convergence and add to result
        try:
            from robotaste.core.bo_utils import check_convergence

            stopping_criteria = bo_config.get("stopping_criteria")
            convergence = check_convergence(session_id, stopping_criteria)

            # Add convergence info to result for subject interface
            result["convergence"] = {
                "converged": convergence.get("converged", False),
                "recommendation": convergence.get("recommendation", "continue"),
                "reason": convergence.get("reason", ""),
                "confidence": convergence.get("confidence", 0.0),
                "status_emoji": convergence.get("status_emoji", "🔴"),
                "current_cycle": convergence["metrics"].get(
                    "current_cycle", current_cycle
                ),
                "max_cycles": convergence["thresholds"].get("max_cycles", 30),
            }

            logger.info(
                f"Convergence check: {convergence.get('recommendation')} - {convergence.get('reason')}"
            )

        except Exception as e:
            logger.warning(f"Could not check convergence: {e}")
            result["convergence"] = {
                "converged": False,
                "recommendation": "continue",
                "reason": "Error checking convergence",
                "confidence": 0.0,
                "status_emoji": "🔴",
                "current_cycle": current_cycle,
                "max_cycles": 30,
            }

        # Add protocol-driven metadata
        is_protocol_driven = should_use_bo_for_cycle(session_id, current_cycle)
        result["is_protocol_driven"] = is_protocol_driven

        # Check if override is allowed (from protocol config)
        allows_override = True  # Default to allowing override
        if is_protocol_driven:
            schedule = experiment_config.get("sample_selection_schedule", [])
            for entry in schedule:
                cycle_range = entry.get("cycle_range", {})
                if cycle_range.get("start", 0) <= current_cycle <= cycle_range.get("end", 0):
                    config = entry.get("config", {})
                    allows_override = config.get("allow_override", True)
                    break

        result["allows_override"] = allows_override

        logger.info(
            f"BO suggestion generated for cycle {current_cycle}: "
            f"predicted={result['predicted_value']:.2f}, "
            f"protocol_driven={is_protocol_driven}, allows_override={allows_override}"
        )
        return result

    except Exception as e:
        logger.error(f"Error getting BO suggestion: {e}", exc_info=True)
        return None
