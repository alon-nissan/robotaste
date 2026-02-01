"""
Questionnaire Configuration System for RoboTaste

This module provides a centralized configuration system for all questionnaires
used in taste preference experiments. Each questionnaire includes:
- Question definitions (type, labels, scales, validation)
- Bayesian optimization target variable configuration
- Metadata for rendering and data extraction

Author: RoboTaste Team
Version: 2.1 (Bayesian Optimization Support)
"""

from typing import Dict, List, Any, Optional, Union
import logging

from robotaste.utils.safe_eval import safe_eval_expression

logger = logging.getLogger(__name__)


# ============================================================================
# QUESTIONNAIRE DEFINITIONS
# ============================================================================
# Example questionnaire templates. Use these as starting points for custom questionnaires
# or reference them by name for legacy compatibility.

QUESTIONNAIRE_EXAMPLES: Dict[str, Dict[str, Any]] = {
    # ========================================================================
    # DEFAULT: Continuous Hedonic Scale
    # Continuous 1-9 scale for fine-grained preference measurement
    # ========================================================================
    "hedonic_continuous": {
        "name": "Hedonic Test (Continuous)",
        "description": "Continuous 9-point hedonic scale with 0.01 precision for detailed preference measurement",
        "version": "2.0",
        "citation": "Peryam & Pilgrim (1957) - Hedonic scale method of measuring food preferences",
        "questions": [
            {
                "id": "overall_liking",
                "type": "slider",
                "label": "How much do you like this sample?",
                "help_text": "Rate your overall liking from 1.00 (Dislike Extremely) to 9.00 (Like Extremely)",
                # 9-point hedonic scale labels (shown at key anchor points)
                "scale_labels": {
                    1: "Dislike Extremely",
                    2: "Dislike Very Much",
                    3: "Dislike Moderately",
                    4: "Dislike Slightly",
                    5: "Neither Like nor Dislike",
                    6: "Like Slightly",
                    7: "Like Moderately",
                    8: "Like Very Much",
                    9: "Like Extremely",
                },
                "min": 1.0,
                "max": 9.0,
                "default": 5.0,  # Neutral starting point
                "step": 0.01,  # Continuous scale with 0.01 precision
                "required": True,
                # Visual styling
                "display_type": "slider_continuous",  # Continuous slider with decimal display
                "color_scale": "red_to_green",  # Visual gradient
            }
        ],
        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "overall_liking",
            "transform": "identity",  # No transformation needed
            "higher_is_better": True,
            "description": "Maximize overall liking score (1.0-9.0 continuous scale)",
            "expected_range": [1.0, 9.0],
            "optimal_threshold": 7.0,  # Scores ≥ 7.0 considered "well-liked"
        },
    },
    # ========================================================================
    # Discrete Hedonic (9-point scale)
    # Standard discrete scale with pillbox/radio button interface
    # ========================================================================
    "hedonic_discrete": {
        "name": "Hedonic Test (9-Point Discrete)",
        "description": "Standard 9-point discrete hedonic scale with radio button selection",
        "version": "1.1",
        "citation": "Peryam & Pilgrim (1957) - Hedonic scale method of measuring food preferences",
        "questions": [
            {
                "id": "overall_liking",
                "type": "slider",
                "label": "How much do you like this sample?",
                "help_text": "Select your overall liking from 1 (Dislike Extremely) to 9 (Like Extremely)",
                # 9-point hedonic scale labels
                "scale_labels": {
                    1: "Dislike Extremely",
                    2: "Dislike Very Much",
                    3: "Dislike Moderately",
                    4: "Dislike Slightly",
                    5: "Neither Like nor Dislike",
                    6: "Like Slightly",
                    7: "Like Moderately",
                    8: "Like Very Much",
                    9: "Like Extremely",
                },
                "min": 1,
                "max": 9,
                "default": 5,  # Neutral starting point
                "step": 1,
                "required": True,
                # Visual styling
                "display_type": "pillboxes",  # Radio buttons (pillbox style)
                "color_scale": "red_to_green",  # Visual gradient
            }
        ],
        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "overall_liking",
            "transform": "identity",  # No transformation needed
            "higher_is_better": True,
            "description": "Maximize overall liking score (1-9 scale)",
            "expected_range": [1, 9],
            "optimal_threshold": 7.0,  # Scores ≥ 7 considered "well-liked"
        },
    },

    # ========================================================================
    # NEW: Continuous Intensity Scale (Sweetness)
    # Continuous slider with markers at odd integers.
    # ========================================================================
    "intensity_continuous": {
        "name": "Intensity Scale (Continuous)",
        "description": "Continuous 9-point intensity scale for measuring attribute strength.",
        "version": "1.0",
        "questions": [
            {
                "id": "sweetness_intensity",
                "type": "slider",
                "label": "How sweet is this sample?",
                "help_text": "Rate the sweetness intensity from 1 (No sweet) to 9 (Very strong).",
                "scale_labels": {
                    1: "No sweet",
                    3: "Light",
                    5: "Medium",
                    7: "Strong",
                    9: "Very strong",
                },
                "min": 1.0,
                "max": 9.0,
                "default": 5.0,
                "step": 0.01,  # Continuous scale
                "required": True,
                "display_type": "slider_continuous",
            }
        ],
        "bayesian_target": {
            "variable": "sweetness_intensity",
            "transform": "identity",
            "higher_is_better": True,  # Maximize intensity (corrected)
            "description": "Measure sweetness intensity.",
            "expected_range": [1.0, 9.0],
            "optimal_threshold": 5.0,  # Example target intensity
        },
    },

    # ========================================================================
    # Unified Feedback (Multi-dimensional feedback)
    # ========================================================================
    "unified_feedback": {
        "name": "Unified Feedback Questionnaire",
        "description": "Multi-dimensional feedback with confidence and strategy",
        "version": "1.0",
        "questions": [
            {
                "id": "satisfaction",
                "type": "slider",
                "label": "How satisfied are you with this selection?",
                "help_text": "Rate your satisfaction from 1 (Not at all) to 7 (Extremely)",
                "min": 1,
                "max": 7,
                "default": 4,
                "step": 1,
                "required": True,
            },
            {
                "id": "confidence",
                "type": "slider",
                "label": "How confident are you in this selection?",
                "help_text": "Rate your confidence from 1 (Not confident) to 7 (Very confident)",
                "min": 1,
                "max": 7,
                "default": 4,
                "step": 1,
                "required": True,
            },
            {
                "id": "strategy",
                "type": "dropdown",
                "label": "What guided your selection?",
                "help_text": "Select the strategy that best describes your approach",
                "options": [
                    "Initial impression",
                    "Random selection",
                    "Based on previous selections",
                    "Systematic approach",
                    "Intuition/gut feeling",
                    "Other",
                ],
                "default": "Initial impression",
                "required": False,
            },
        ],
        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "satisfaction",
            "transform": "identity",
            "higher_is_better": True,
            "description": "Maximize satisfaction score (1-7 scale)",
            "expected_range": [1, 7],
            "optimal_threshold": 5.5,
        },
    },
    # ========================================================================
    # MULTI-ATTRIBUTE: Extended sensory evaluation
    # For research examining multiple preference dimensions
    # ========================================================================
    "multi_attribute": {
        "name": "Multi-Attribute Sensory Evaluation",
        "description": "Comprehensive evaluation across multiple sensory dimensions",
        "version": "1.0",
        "questions": [
            {
                "id": "overall_liking",
                "type": "slider",
                "label": "Overall, how much do you like this sample?",
                "min": 1,
                "max": 9,
                "default": 5,
                "step": 1,
                "required": True,
                "scale_labels": {
                    1: "Dislike Extremely",
                    5: "Neutral",
                    9: "Like Extremely",
                },
            },
            {
                "id": "sweetness_liking",
                "type": "slider",
                "label": "How much do you like the sweetness level?",
                "min": 1,
                "max": 9,
                "default": 5,
                "step": 1,
                "required": True,
            },
            {
                "id": "flavor_intensity",
                "type": "slider",
                "label": "How intense is the flavor?",
                "help_text": "1 = Very Weak, 9 = Very Strong",
                "min": 1,
                "max": 9,
                "default": 5,
                "step": 1,
                "required": False,
            },
            {
                "id": "purchase_intent",
                "type": "slider",
                "label": "How likely would you be to purchase this product?",
                "min": 1,
                "max": 5,
                "default": 3,
                "step": 1,
                "required": False,
                "scale_labels": {
                    1: "Definitely would not buy",
                    3: "Maybe",
                    5: "Definitely would buy",
                },
            },
        ],
        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "overall_liking",
            "transform": "identity",
            "higher_is_better": True,
            "description": "Maximize overall liking score",
            "expected_range": [1, 9],
            "optimal_threshold": 7.0,
        },
    },
    # ========================================================================
    # COMPOSITE: Multi-objective optimization example
    # Demonstrates weighted combination of multiple targets
    # ========================================================================
    "composite_preference": {
        "name": "Composite Preference (Liking + Healthiness)",
        "description": "Optimize for both liking and perceived healthiness",
        "version": "1.0",
        "questions": [
            {
                "id": "liking",
                "type": "slider",
                "label": "How much do you like this sample?",
                "min": 1,
                "max": 9,
                "default": 5,
                "step": 1,
                "required": True,
            },
            {
                "id": "healthiness_perception",
                "type": "slider",
                "label": "How healthy do you perceive this sample to be?",
                "min": 1,
                "max": 7,
                "default": 4,
                "step": 1,
                "required": True,
            },
        ],
        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "composite",  # Special indicator for multi-objective
            "formula": "0.7 * liking + 0.3 * healthiness_perception",  # Weighted combination
            "transform": "identity",
            "higher_is_better": True,
            "description": "Maximize weighted combination: 70% liking + 30% healthiness",
            "expected_range": [1, 8.5],  # Approximate range of weighted score
            "optimal_threshold": 6.0,
        },
    },
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_questionnaire_config(questionnaire: Union[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Retrieve questionnaire configuration.

    Args:
        questionnaire: Either a string (legacy questionnaire type name) or
                      a questionnaire config dict (inline configuration)

    Returns:
        Questionnaire config dictionary
    """
    # If already a dict, return it
    if isinstance(questionnaire, dict):
        return questionnaire

    # Legacy: string lookup in QUESTIONNAIRE_EXAMPLES
    if isinstance(questionnaire, str):
        config = QUESTIONNAIRE_EXAMPLES.get(questionnaire)
        if config is None:
            logger.warning(
                f"Questionnaire type '{questionnaire}' not found. Using default."
            )
            return QUESTIONNAIRE_EXAMPLES.get("hedonic_continuous")
        return config

    # Fallback
    logger.warning("Invalid questionnaire parameter type. Using default.")
    return QUESTIONNAIRE_EXAMPLES.get("hedonic_continuous")


def get_default_questionnaire_type() -> str:
    """Return the default questionnaire type."""
    return "hedonic_continuous"


def list_available_questionnaires() -> List[tuple]:
    """
    List all available questionnaire examples with metadata.

    Returns:
        List of tuples: (type_key, name, description)
    """
    questionnaires = []
    for key, config in QUESTIONNAIRE_EXAMPLES.items():
        questionnaires.append(
            (
                key,
                config.get("name", key),
                config.get("description", "No description available"),
            )
        )
    return questionnaires


def validate_questionnaire_response(
    response: Dict[str, Any], questionnaire: Union[str, Dict[str, Any]]
) -> tuple[bool, Optional[str]]:
    """
    Validate a questionnaire response against the configuration.

    Args:
        response: Dictionary of question_id -> answer
        questionnaire: Either questionnaire config dict (preferred) or
                      string type name (legacy)

    Returns:
        Tuple of (is_valid, error_message)
    """
    config = get_questionnaire_config(questionnaire)
    if config is None:
        return False, f"Invalid questionnaire configuration"

    # Check all required questions are answered
    for question in config["questions"]:
        question_id = question["id"]

        if question.get("required", False):
            if question_id not in response or response[question_id] is None:
                return False, f"Required question '{question_id}' not answered"

        # Validate answer is within range (for sliders)
        if question_id in response and question["type"] == "slider":
            value = response[question_id]
            min_val = question["min"]
            max_val = question["max"]

            if not (min_val <= value <= max_val):
                return (
                    False,
                    f"Answer for '{question_id}' out of range [{min_val}, {max_val}]",
                )

    return True, None


def extract_target_variable(
    response: Dict[str, Any], questionnaire_config: Dict[str, Any]
) -> Optional[float]:
    """
    Extract the target variable for Bayesian optimization from a response.

    Args:
        response: Dictionary of questionnaire answers
        questionnaire_config: Configuration for this questionnaire

    Returns:
        Target value as float, or None if extraction fails
    """
    try:
        target_config = questionnaire_config["bayesian_target"]
        target_variable = target_config["variable"]

        # Handle composite targets (weighted combinations)
        if target_variable == "composite":
            formula = target_config["formula"]
            # Safely evaluate formula with response values using safe_eval
            target_value = safe_eval_expression(formula, response)
        else:
            # Simple single-variable target
            target_value = response.get(target_variable)

        if target_value is None:
            logger.warning(f"Target variable '{target_variable}' not found in response")
            return None

        # Apply transformation if specified
        transform = target_config.get("transform", "identity")
        if transform == "log":
            import numpy as np

            target_value = np.log(target_value + 1)  # +1 to avoid log(0)
        elif transform == "normalize":
            # Normalize to [0, 1] based on expected range
            expected_range = target_config.get("expected_range", [1, 9])
            min_val, max_val = expected_range
            target_value = (target_value - min_val) / (max_val - min_val)

        # If minimizing, negate the value
        if not target_config.get("higher_is_better", True):
            target_value = -target_value

        return float(target_value)

    except Exception as e:
        logger.error(f"Failed to extract target variable: {e}")
        return None


def get_question_by_id(
    questionnaire: Union[str, Dict[str, Any]], question_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a specific question configuration by ID.

    Args:
        questionnaire: Either questionnaire config dict or string type name
        question_id: ID of the question

    Returns:
        Question configuration dictionary or None
    """
    config = get_questionnaire_config(questionnaire)
    if config is None:
        return None

    for question in config["questions"]:
        if question["id"] == question_id:
            return question

    return None


# ============================================================================
# QUESTIONNAIRE METADATA
# ============================================================================


def get_questionnaire_metadata(questionnaire: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get metadata about a questionnaire (name, description, version, etc.).

    Args:
        questionnaire: Either questionnaire config dict or string type name

    Returns:
        Dictionary with metadata
    """
    config = get_questionnaire_config(questionnaire)
    if config is None:
        return {}

    # Determine type key - use name if dict, or the string key if legacy
    type_key = questionnaire if isinstance(questionnaire, str) else config.get("name", "custom")

    return {
        "type": type_key,
        "name": config.get("name", "Unknown"),
        "description": config.get("description", ""),
        "version": config.get("version", "1.0"),
        "num_questions": len(config.get("questions", [])),
        "has_bayesian_target": "bayesian_target" in config,
        "target_variable": config.get("bayesian_target", {}).get("variable", None),
    }


def get_questionnaire_example(name: str) -> Optional[Dict[str, Any]]:
    """
    Get an example questionnaire template by name.

    Args:
        name: Name of the example template

    Returns:
        Example questionnaire config dict or None if not found
    """
    return QUESTIONNAIRE_EXAMPLES.get(name)
