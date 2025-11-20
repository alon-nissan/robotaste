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

from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# QUESTIONNAIRE DEFINITIONS
# ============================================================================

QUESTIONNAIRE_CONFIGS: Dict[str, Dict[str, Any]] = {

    # ========================================================================
    # DEFAULT: Hedonic Preference (9-point scale)
    # Standard in food science research
    # ========================================================================
    "hedonic_preference": {
        "name": "Hedonic Preference Test",
        "description": "Standard 9-point hedonic scale used in sensory evaluation",
        "version": "1.0",
        "citation": "Peryam & Pilgrim (1957) - Hedonic scale method of measuring food preferences",

        "questions": [
            {
                "id": "overall_liking",
                "type": "slider",
                "label": "How much do you like this sample?",
                "help_text": "Rate your overall liking from 1 (Dislike Extremely) to 9 (Like Extremely)",

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
                    9: "Like Extremely"
                },

                "min": 1,
                "max": 9,
                "default": 5,  # Neutral starting point
                "step": 1,
                "required": True,

                # Visual styling
                "display_type": "slider_with_labels",  # Show labels at key points
                "color_scale": "red_to_green"  # Visual gradient
            }
        ],

        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "overall_liking",
            "transform": "identity",  # No transformation needed
            "higher_is_better": True,
            "description": "Maximize overall liking score (1-9 scale)",
            "expected_range": [1, 9],
            "optimal_threshold": 7.0  # Scores ≥ 7 considered "well-liked"
        }
    },

    # ========================================================================
    # LEGACY: Unified Feedback (Current system)
    # For backward compatibility with existing experiments
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
                "required": True
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
                "required": True
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
                    "Other"
                ],
                "default": "Initial impression",
                "required": False
            }
        ],

        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "satisfaction",
            "transform": "identity",
            "higher_is_better": True,
            "description": "Maximize satisfaction score (1-7 scale)",
            "expected_range": [1, 7],
            "optimal_threshold": 5.5
        }
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
                "scale_labels": {1: "Dislike Extremely", 5: "Neutral", 9: "Like Extremely"}
            },
            {
                "id": "sweetness_liking",
                "type": "slider",
                "label": "How much do you like the sweetness level?",
                "min": 1,
                "max": 9,
                "default": 5,
                "step": 1,
                "required": True
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
                "required": False
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
                "scale_labels": {1: "Definitely would not buy", 3: "Maybe", 5: "Definitely would buy"}
            }
        ],

        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "overall_liking",
            "transform": "identity",
            "higher_is_better": True,
            "description": "Maximize overall liking score",
            "expected_range": [1, 9],
            "optimal_threshold": 7.0
        }
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
                "required": True
            },
            {
                "id": "healthiness_perception",
                "type": "slider",
                "label": "How healthy do you perceive this sample to be?",
                "min": 1,
                "max": 7,
                "default": 4,
                "step": 1,
                "required": True
            }
        ],

        # Bayesian Optimization Configuration
        "bayesian_target": {
            "variable": "composite",  # Special indicator for multi-objective
            "formula": "0.7 * liking + 0.3 * healthiness_perception",  # Weighted combination
            "transform": "identity",
            "higher_is_better": True,
            "description": "Maximize weighted combination: 70% liking + 30% healthiness",
            "expected_range": [1, 8.5],  # Approximate range of weighted score
            "optimal_threshold": 6.0
        }
    }
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_questionnaire_config(questionnaire_type: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve questionnaire configuration by type.

    Args:
        questionnaire_type: Key from QUESTIONNAIRE_CONFIGS

    Returns:
        Configuration dictionary or None if not found
    """
    config = QUESTIONNAIRE_CONFIGS.get(questionnaire_type)

    if config is None:
        logger.warning(f"Questionnaire type '{questionnaire_type}' not found. Using default.")
        return QUESTIONNAIRE_CONFIGS.get("hedonic_preference")

    return config


def get_default_questionnaire_type() -> str:
    """Return the default questionnaire type."""
    return "hedonic_preference"


def list_available_questionnaires() -> List[tuple]:
    """
    List all available questionnaires with metadata.

    Returns:
        List of tuples: (type_key, name, description)
    """
    questionnaires = []
    for key, config in QUESTIONNAIRE_CONFIGS.items():
        questionnaires.append((
            key,
            config.get("name", key),
            config.get("description", "No description available")
        ))
    return questionnaires


def validate_questionnaire_response(
    response: Dict[str, Any],
    questionnaire_type: str
) -> tuple[bool, Optional[str]]:
    """
    Validate a questionnaire response against the configuration.

    Args:
        response: Dictionary of question_id -> answer
        questionnaire_type: Type of questionnaire being validated

    Returns:
        Tuple of (is_valid, error_message)
    """
    config = get_questionnaire_config(questionnaire_type)
    if config is None:
        return False, f"Unknown questionnaire type: {questionnaire_type}"

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
                return False, f"Answer for '{question_id}' out of range [{min_val}, {max_val}]"

    return True, None


def extract_target_variable(
    response: Dict[str, Any],
    questionnaire_config: Dict[str, Any]
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
            # Safely evaluate formula with response values
            target_value = eval(formula, {"__builtins__": {}}, response)
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


def get_question_by_id(questionnaire_type: str, question_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific question configuration by ID.

    Args:
        questionnaire_type: Type of questionnaire
        question_id: ID of the question

    Returns:
        Question configuration dictionary or None
    """
    config = get_questionnaire_config(questionnaire_type)
    if config is None:
        return None

    for question in config["questions"]:
        if question["id"] == question_id:
            return question

    return None


# ============================================================================
# QUESTIONNAIRE METADATA
# ============================================================================

def get_questionnaire_metadata(questionnaire_type: str) -> Dict[str, Any]:
    """
    Get metadata about a questionnaire (name, description, version, etc.).

    Args:
        questionnaire_type: Type of questionnaire

    Returns:
        Dictionary with metadata
    """
    config = get_questionnaire_config(questionnaire_type)
    if config is None:
        return {}

    return {
        "type": questionnaire_type,
        "name": config.get("name", "Unknown"),
        "description": config.get("description", ""),
        "version": config.get("version", "1.0"),
        "num_questions": len(config.get("questions", [])),
        "has_bayesian_target": "bayesian_target" in config,
        "target_variable": config.get("bayesian_target", {}).get("variable", None)
    }
