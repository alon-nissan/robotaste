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
from robotaste.config.scales import (
    resolve_question,
    validate_answer,
    is_answered,
    get_default_transform,
    NUMERIC_QUESTION_TYPES,
)

logger = logging.getLogger(__name__)


# ============================================================================
# QUESTIONNAIRE TEMPLATES
# ============================================================================
# Reference templates for researchers building protocols.
# Protocols MUST include inline questionnaire configuration - these templates
# are for copying into protocol JSON, NOT for runtime lookup.

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


def get_questionnaire_config(questionnaire: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and return questionnaire configuration (inline only).

    Args:
        questionnaire: Questionnaire config dict (inline configuration)

    Returns:
        Questionnaire config dictionary

    Raises:
        TypeError: If questionnaire is not a dict
        ValueError: If questionnaire structure is invalid
    """
    if not isinstance(questionnaire, dict):
        raise TypeError(f"Questionnaire must be a dict, got {type(questionnaire).__name__}")

    # Basic validation
    if "questions" not in questionnaire or not questionnaire["questions"]:
        raise ValueError("Questionnaire must have at least one question")

    # bayesian_target is optional: only BO protocols need it (enforced in
    # protocols._validate_questionnaire_config).
    return questionnaire


def list_available_questionnaires() -> List[tuple]:
    """
    List all available questionnaire templates (for reference only).

    Note: These are templates for researchers to copy into protocols.
    They are NOT runtime options - protocols must include inline questionnaire config.

    Returns:
        List of tuples: (template_key, name, description)
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
    response: Dict[str, Any], questionnaire: Dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Validate a questionnaire response against the configuration.

    Questions are resolved against their scale preset (see
    ``robotaste.config.scales``) and every answer is type-checked: numeric
    range for sliders/line scales, membership for category/choice questions,
    list shape for multi-select and ranking, etc. Keys in the response that
    do not correspond to a question are ignored.

    Args:
        response: Dictionary of question_id -> answer
        questionnaire: Inline questionnaire config dict

    Returns:
        Tuple of (is_valid, error_message). error_message joins all problems.
    """
    config = get_questionnaire_config(questionnaire)
    if not isinstance(response, dict):
        return False, "Response must be an object of question_id -> answer"

    errors: List[str] = []
    for raw_question in config["questions"]:
        question = resolve_question(raw_question)
        question_id = question.get("id")
        value = response.get(question_id)

        if not is_answered(value):
            if question.get("required", False):
                errors.append(f"Required question '{question_id}' not answered")
            continue

        error = validate_answer(question, value)
        if error:
            errors.append(error)

    if errors:
        return False, "; ".join(errors)
    return True, None


def _find_question(
    questionnaire_config: Dict[str, Any], question_id: str
) -> Optional[Dict[str, Any]]:
    for question in questionnaire_config.get("questions", []) or []:
        if isinstance(question, dict) and question.get("id") == question_id:
            return question
    return None


TARGET_TRANSFORMS = ("identity", "log", "log10", "log10p1", "normalize", "ideal_point")


def extract_target_variable(
    response: Dict[str, Any], questionnaire_config: Dict[str, Any]
) -> Optional[float]:
    """
    Extract the target variable for Bayesian optimization from a response.

    Transforms (``bayesian_target.transform``):
        identity     value unchanged
        log          ln(value + 1)                       (legacy)
        log10        log10(value)                        (value must be > 0)
        log10p1      log10(value + 1)                    (gLMS, magnitude estimation)
        normalize    (value - lo) / (hi - lo) using expected_range
        ideal_point  -|value - ideal_value|              (JAR / ideal-intensity targets;
                                                          higher is always better)
    When ``transform`` is omitted, the target question's preset default is
    used (e.g. gLMS → log10p1), falling back to identity.

    Args:
        response: Dictionary of questionnaire answers
        questionnaire_config: Configuration for this questionnaire

    Returns:
        Target value as float, or None if extraction fails
    """
    try:
        target_config = questionnaire_config["bayesian_target"]
        target_variable = target_config["variable"]
        target_question = None

        # Handle composite targets (weighted combinations)
        if target_variable == "composite":
            formula = target_config["formula"]
            # Safely evaluate formula with response values using safe_eval
            target_value = safe_eval_expression(formula, response)
        else:
            # Simple single-variable target
            target_value = response.get(target_variable)
            target_question = _find_question(questionnaire_config, target_variable)

        if target_value is None:
            logger.warning(f"Target variable '{target_variable}' not found in response")
            return None
        if isinstance(target_value, bool) or not isinstance(target_value, (int, float)):
            logger.warning(
                f"Target variable '{target_variable}' is not numeric: {target_value!r}"
            )
            return None

        import numpy as np

        target_value = float(target_value)

        # Apply transformation (explicit, else preset default)
        transform = target_config.get("transform")
        if not transform:
            transform = (
                get_default_transform(target_question) if target_question else "identity"
            )

        if transform == "log":
            target_value = np.log(target_value + 1)  # +1 to avoid log(0)
        elif transform == "log10":
            if target_value <= 0:
                logger.warning(f"log10 transform needs value > 0, got {target_value}")
                return None
            target_value = np.log10(target_value)
        elif transform == "log10p1":
            if target_value <= -1:
                logger.warning(f"log10p1 transform needs value > -1, got {target_value}")
                return None
            target_value = np.log10(target_value + 1)
        elif transform == "normalize":
            # Normalize to [0, 1] based on expected range
            expected_range = target_config.get("expected_range", [1, 9])
            min_val, max_val = expected_range
            target_value = (target_value - min_val) / (max_val - min_val)
        elif transform == "ideal_point":
            ideal = target_config.get("ideal_value")
            if ideal is None and target_question:
                ideal = resolve_question(target_question).get("ideal_value")
            if ideal is None:
                logger.warning("ideal_point transform requires 'ideal_value'")
                return None
            # Distance from ideal: closer is better, so maximise the negative distance.
            return float(-abs(target_value - float(ideal)))
        elif transform != "identity":
            logger.warning(f"Unknown transform '{transform}', using identity")

        # If minimizing, negate the value
        if not target_config.get("higher_is_better", True):
            target_value = -target_value

        return float(target_value)

    except Exception as e:
        logger.error(f"Failed to extract target variable: {e}")
        return None


def is_numeric_question(question: Dict[str, Any]) -> bool:
    """True if the (resolved) question yields a single numeric answer."""
    resolved = resolve_question(question)
    q_type = resolved.get("type")
    if q_type != "pillbox":
        return q_type in NUMERIC_QUESTION_TYPES
    # Pillbox with string options yields strings; numeric range pillbox yields numbers.
    options = resolved.get("options") or []
    return all(
        isinstance(o.get("value") if isinstance(o, dict) else o, (int, float))
        for o in options
    )


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


# ============================================================================
# EXPORT / ANALYSIS FLATTENING
# ============================================================================

# Answer keys that are bookkeeping, not responses.
ANSWER_SKIP_KEYS = {"questionnaire_type", "participant_id", "timestamp", "is_final"}


def _option_values(question: Dict[str, Any]) -> List[Any]:
    values = []
    for opt in question.get("options") or []:
        values.append(opt.get("value") if isinstance(opt, dict) else opt)
    return values


def flatten_answers(
    answers: Optional[Dict[str, Any]],
    questions: Optional[List[Dict[str, Any]]] = None,
    answer_meta: Optional[Dict[str, Any]] = None,
    include_meta: bool = True,
) -> Dict[str, Any]:
    """
    Flatten one sample's answers into scalar columns for export/analysis.

    - Scalar answers (numbers, text) → ``{qid}``.
    - ``multi_select`` (CATA) → ``{qid}__{option}`` = 1/0 for every configured
      option (unselected options still get a 0), plus ``{qid}__n_selected``.
    - ``ranking`` → ``{qid}__rank__{option}`` = rank (1 = best).
    - ``answer_meta`` (if ``include_meta``) → ``{qid}__interacted`` (0/1),
      ``{qid}__rt_ms``, ``{qid}__n_changes``.

    Answers to questions not in ``questions`` pass through (lists are joined
    with "; "). Bookkeeping keys in ``ANSWER_SKIP_KEYS`` are dropped.
    Column order follows the questionnaire, then any extra keys.
    """
    answers = answers or {}
    out: Dict[str, Any] = {}
    by_id: Dict[str, Dict[str, Any]] = {}
    for q in questions or []:
        if isinstance(q, dict) and q.get("id"):
            by_id[q["id"]] = resolve_question(q)

    ordered_ids = [qid for qid in by_id if qid in answers or by_id[qid].get("type") == "multi_select"]
    extra_ids = [k for k in answers if k not in by_id and k not in ANSWER_SKIP_KEYS]

    for qid in ordered_ids:
        q = by_id[qid]
        q_type = q.get("type")
        value = answers.get(qid)

        if q_type == "multi_select":
            if value is None and qid not in answers:
                continue  # question not answered at all (e.g. older sample)
            selected = {str(v) for v in (value or [])} if isinstance(value, list) else set()
            options = _option_values(q)
            for opt in options:
                out[f"{qid}__{opt}"] = 1 if str(opt) in selected else 0
            for extra in sorted(selected - {str(o) for o in options}):
                out[f"{qid}__{extra}"] = 1
            out[f"{qid}__n_selected"] = len(selected)
        elif q_type == "ranking" and isinstance(value, list):
            ranks = {str(v): i for i, v in enumerate(value, start=1)}
            options = _option_values(q)
            for opt in options:  # configured order → stable columns across rows
                out[f"{qid}__rank__{opt}"] = ranks.get(str(opt))
            for extra in [v for v in value if str(v) not in {str(o) for o in options}]:
                out[f"{qid}__rank__{extra}"] = ranks[str(extra)]
        elif isinstance(value, list):
            out[qid] = "; ".join(str(v) for v in value)
        else:
            out[qid] = value

    for key in extra_ids:
        value = answers[key]
        out[key] = "; ".join(str(v) for v in value) if isinstance(value, list) else value

    if include_meta and isinstance(answer_meta, dict):
        for qid in list(by_id) + [k for k in answer_meta if k not in by_id]:
            meta = answer_meta.get(qid)
            if not isinstance(meta, dict):
                continue
            if "interacted" in meta:
                out[f"{qid}__interacted"] = 1 if meta.get("interacted") else 0
            if "rt_ms" in meta:
                out[f"{qid}__rt_ms"] = meta.get("rt_ms")
            if "n_changes" in meta:
                out[f"{qid}__n_changes"] = meta.get("n_changes")

    return out


def is_numeric_value(value: Any) -> bool:
    """True for real numbers (not bools / NaN)."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and value == value  # NaN check
    )


def questions_from_experiment_config(experiment_config: Any) -> List[Dict[str, Any]]:
    """Questions of a session's frozen questionnaire (handles JSON strings and missing data)."""
    import json as _json

    if isinstance(experiment_config, str):
        try:
            experiment_config = _json.loads(experiment_config)
        except (TypeError, ValueError):
            return []
    if not isinstance(experiment_config, dict):
        return []
    questionnaire = experiment_config.get("questionnaire") or {}
    questions = questionnaire.get("questions") if isinstance(questionnaire, dict) else None
    return questions if isinstance(questions, list) else []
