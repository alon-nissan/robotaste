"""
Scale Registry for RoboTaste Questionnaires

Single source of truth for psychophysical / hedonic rating scales and the
question types that render them. Protocol questions may reference a preset
(``"preset": "glms"``) and override any field; ``resolve_question()`` merges
the preset with the question so every downstream consumer (validation,
response checking, BO target extraction, frontend rendering) sees one fully
specified question dict.

Question types
--------------
Legacy (unchanged behaviour):
    slider, pillbox, dropdown, text_input, text_area
New:
    line_scale            Continuous line with anchors placed at their numeric
                          value (VAS, gVAS, gLMS, LMS, LAM, LHS, hedonic gLMS).
    category_scale        Discrete labelled points (9-pt hedonic, Likert, JAR,
                          facial scales).
    magnitude_estimation  Free numeric entry (free or fixed modulus).
    multi_select          Check-all-that-apply (CATA). Answer: list of values.
    ranking               Order all options. Answer: list of values, best first.

Anchor values
-------------
Line-scale anchor positions are on the scale's own [min, max] range
(0–100 for unipolar scales, -100–100 for bipolar ratio scales). Presets carry
a ``version``; bump it whenever anchor values change so stored data
(``answer_meta.preset_version``) stays interpretable.

Presets flagged ``anchors_verified: False`` use positions that could not be
checked against the original publication — verify before relying on them.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional

# ============================================================================
# QUESTION TYPES
# ============================================================================

LEGACY_QUESTION_TYPES = {"slider", "pillbox", "dropdown", "text_input", "text_area"}
SCALE_QUESTION_TYPES = {
    "line_scale",
    "category_scale",
    "magnitude_estimation",
    "multi_select",
    "ranking",
}
QUESTION_TYPES = LEGACY_QUESTION_TYPES | SCALE_QUESTION_TYPES

# Types whose answer is a single number and can therefore be a BO target.
NUMERIC_QUESTION_TYPES = {
    "slider",
    "pillbox",
    "line_scale",
    "category_scale",
    "magnitude_estimation",
}

ORIENTATIONS = {"horizontal", "vertical"}
POLARITIES = {"unipolar", "bipolar"}
CATEGORY_LAYOUTS = {"horizontal", "vertical", "grid"}
CATEGORY_STYLES = {"buttons", "radio", "faces"}

# Type-level defaults applied before preset/question fields.
TYPE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "line_scale": {
        "orientation": "horizontal",
        "polarity": "unipolar",
        "anchors": [],
        "show_value": False,
        "start_unmarked": True,
        "show_ticks": True,
        "inset_anchors": False,
        "require_interaction": True,
    },
    "category_scale": {
        "layout": "horizontal",
        "style": "buttons",
        "require_interaction": True,
    },
    "magnitude_estimation": {
        "allow_zero": False,
    },
    "multi_select": {
        "randomize_order": True,
        "min_selected": 0,
    },
    "ranking": {
        "randomize_order": True,
    },
}


# ============================================================================
# PRESETS
# ============================================================================

_GLMS_INTENSITY_ANCHORS = [
    {"value": 0, "label": "No sensation"},
    {"value": 1.4, "label": "Barely detectable"},
    {"value": 6, "label": "Weak"},
    {"value": 17, "label": "Moderate"},
    {"value": 35, "label": "Strong"},
    {"value": 53, "label": "Very strong"},
    {"value": 100, "label": "Strongest imaginable sensation of any kind"},
]

SCALE_PRESETS: Dict[str, Dict[str, Any]] = {
    # ------------------------------------------------------------------
    # Continuous line scales
    # ------------------------------------------------------------------
    "vas": {
        "name": "VAS (Visual Analogue Scale)",
        "category": "intensity",
        "version": "1.0",
        "description": (
            "Unstructured line labelled only at its ends. Interval-level data; "
            "best for within-subject comparisons. Edit the end labels to the "
            "attribute being rated."
        ),
        "recommended_use": "Within-subject intensity or liking ratings.",
        "citation": "Stone et al. (1974) Food Technol 28:24-34",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "line_scale",
            "min": 0,
            "max": 100,
            "orientation": "horizontal",
            "polarity": "unipolar",
            "anchors": [
                {"value": 0, "label": "Not at all"},
                {"value": 100, "label": "Extremely"},
            ],
            "show_ticks": False,
            "inset_anchors": True,
        },
    },
    "hedonic_vas": {
        "name": "Hedonic VAS",
        "category": "hedonic",
        "version": "1.0",
        "description": "Unstructured line from 'dislike extremely' to 'like extremely'.",
        "recommended_use": "Within-subject liking ratings.",
        "citation": "Lawless & Heymann (2010) Sensory Evaluation of Food, ch. 7",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "line_scale",
            "min": 0,
            "max": 100,
            "orientation": "horizontal",
            "polarity": "bipolar",
            "anchors": [
                {"value": 0, "label": "Dislike extremely"},
                {"value": 50, "label": "Neither like nor dislike"},
                {"value": 100, "label": "Like extremely"},
            ],
            "show_ticks": False,
            "inset_anchors": True,
        },
    },
    "gvas": {
        "name": "gVAS (generalized VAS)",
        "category": "intensity",
        "version": "1.0",
        "description": (
            "VAS whose top anchor is 'strongest imaginable sensation of any kind', "
            "so ratings can be compared across groups. No intermediate labels."
        ),
        "recommended_use": "Cross-group intensity comparisons (e.g. taster status).",
        "citation": "Hayes, Allen & Bennett (2013) Food Qual Prefer 28:36-44",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "line_scale",
            "min": 0,
            "max": 100,
            "orientation": "horizontal",
            "polarity": "unipolar",
            "anchors": [
                {"value": 0, "label": "No sensation"},
                {"value": 100, "label": "Strongest imaginable sensation of any kind"},
            ],
            "show_ticks": False,
        },
    },
    "glms": {
        "name": "gLMS (general Labeled Magnitude Scale)",
        "category": "intensity",
        "version": "1.0",
        "description": (
            "Vertical line with quasi-logarithmically spaced intensity labels and "
            "top anchor 'strongest imaginable sensation of any kind'. Ratio-like "
            "data; log-transformed by default for BO."
        ),
        "recommended_use": "Intensity ratings with cross-group validity (supertasters, clinical groups).",
        "citation": "Bartoshuk et al. (2004) Physiol Behav 82:109-114",
        "default_transform": "log10p1",
        "anchors_verified": True,
        "question": {
            "type": "line_scale",
            "min": 0,
            "max": 100,
            "orientation": "vertical",
            "polarity": "unipolar",
            "anchors": _GLMS_INTENSITY_ANCHORS,
        },
    },
    "lms": {
        "name": "LMS (oral Labeled Magnitude Scale)",
        "category": "intensity",
        "version": "1.0",
        "description": (
            "Original LMS with top anchor bound to oral sensation. Prefer gLMS "
            "for cross-group comparisons."
        ),
        "recommended_use": "Within-study oral intensity ratings; replication of LMS studies.",
        "citation": "Green, Shaffer & Gilmore (1993) Chem Senses 18:683-702",
        "default_transform": "log10p1",
        "anchors_verified": False,
        "question": {
            "type": "line_scale",
            "min": 0,
            "max": 100,
            "orientation": "vertical",
            "polarity": "unipolar",
            "anchors": [
                {"value": 0, "label": "No sensation"},
                {"value": 1.4, "label": "Barely detectable"},
                {"value": 6.1, "label": "Weak"},
                {"value": 17.2, "label": "Moderate"},
                {"value": 35.4, "label": "Strong"},
                {"value": 53.3, "label": "Very strong"},
                {"value": 100, "label": "Strongest imaginable oral sensation"},
            ],
        },
    },
    "hedonic_glms": {
        "name": "Hedonic gLMS (bipolar)",
        "category": "hedonic",
        "version": "1.0",
        "description": (
            "Bipolar liking scale anchored at the most intense liking/disliking "
            "of any kind ever experienced. Reduces ceiling effects of food-bound scales."
        ),
        "recommended_use": "Cross-group liking comparisons.",
        "citation": "Bartoshuk et al. (2006) Ann N Y Acad Sci; Kalva et al. (2014) J Food Sci 79:S238",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "line_scale",
            "min": -100,
            "max": 100,
            "orientation": "vertical",
            "polarity": "bipolar",
            "anchors": [
                {"value": -100, "label": "Strongest imaginable disliking of any kind"},
                {"value": 0, "label": "Neutral"},
                {"value": 100, "label": "Strongest imaginable liking of any kind"},
            ],
        },
    },
    "lhs": {
        "name": "LHS (Labeled Hedonic Scale)",
        "category": "hedonic",
        "version": "1.0",
        "description": (
            "Bipolar ratio-level liking scale, symmetric around neutral. "
            "Inner anchor positions should be verified against Lim et al. (2009) Table 3."
        ),
        "recommended_use": "Ratio-level liking ratings with low ceiling effects.",
        "citation": "Lim, Wood & Green (2009) Chem Senses 34:739-751",
        "default_transform": "identity",
        "anchors_verified": False,
        "question": {
            "type": "line_scale",
            "min": -100,
            "max": 100,
            "orientation": "vertical",
            "polarity": "bipolar",
            "anchors": [
                {"value": -100, "label": "Most disliked sensation imaginable"},
                {"value": -65.7, "label": "Dislike extremely"},
                {"value": -44.4, "label": "Dislike very much"},
                {"value": -17.8, "label": "Dislike moderately"},
                {"value": -6.3, "label": "Dislike slightly"},
                {"value": 0, "label": "Neutral"},
                {"value": 6.3, "label": "Like slightly"},
                {"value": 17.8, "label": "Like moderately"},
                {"value": 44.4, "label": "Like very much"},
                {"value": 65.7, "label": "Like extremely"},
                {"value": 100, "label": "Most liked sensation imaginable"},
            ],
        },
    },
    "lam": {
        "name": "LAM (Labeled Affective Magnitude scale)",
        "category": "hedonic",
        "version": "1.0",
        "description": (
            "0–100 liking scale with the nine hedonic labels at magnitude-derived "
            "positions. Discriminates well among liked products. Inner positions "
            "should be verified against Cardello & Schutz (2004)."
        ),
        "recommended_use": "Liking of well-liked products where the 9-pt scale hits the ceiling.",
        "citation": "Schutz & Cardello (2001) J Sens Stud 16:117-159; Cardello & Schutz (2004) J Sens Stud 19:341-346",
        "default_transform": "identity",
        "anchors_verified": False,
        "question": {
            "type": "line_scale",
            "min": 0,
            "max": 100,
            "orientation": "vertical",
            "polarity": "bipolar",
            "anchors": [
                {"value": 0, "label": "Greatest imaginable dislike"},
                {"value": 13.24, "label": "Dislike extremely"},
                {"value": 21.59, "label": "Dislike very much"},
                {"value": 33.10, "label": "Dislike moderately"},
                {"value": 44.16, "label": "Dislike slightly"},
                {"value": 50, "label": "Neither like nor dislike"},
                {"value": 56.11, "label": "Like slightly"},
                {"value": 68.12, "label": "Like moderately"},
                {"value": 78.06, "label": "Like very much"},
                {"value": 87.11, "label": "Like extremely"},
                {"value": 100, "label": "Greatest imaginable like"},
            ],
        },
    },
    # ------------------------------------------------------------------
    # Category scales
    # ------------------------------------------------------------------
    "hedonic_9pt": {
        "name": "9-point hedonic scale",
        "category": "hedonic",
        "version": "1.0",
        "description": "Industry-standard liking scale, 1 = dislike extremely … 9 = like extremely.",
        "recommended_use": "Consumer liking; comparable with decades of normative data.",
        "citation": "Peryam & Pilgrim (1957) Food Technol 11(9):9-14",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "vertical",
            "style": "radio",
            "options": [
                {"value": 9, "label": "Like extremely"},
                {"value": 8, "label": "Like very much"},
                {"value": 7, "label": "Like moderately"},
                {"value": 6, "label": "Like slightly"},
                {"value": 5, "label": "Neither like nor dislike"},
                {"value": 4, "label": "Dislike slightly"},
                {"value": 3, "label": "Dislike moderately"},
                {"value": 2, "label": "Dislike very much"},
                {"value": 1, "label": "Dislike extremely"},
            ],
        },
    },
    "intensity_5pt": {
        "name": "5-point category intensity scale",
        "category": "intensity",
        "version": "1.0",
        "description": "Labelled category intensity scale (ordinal).",
        "recommended_use": "Quick within-subject intensity screening.",
        "citation": "Lawless & Heymann (2010) Sensory Evaluation of Food, ch. 7",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "buttons",
            "options": [
                {"value": 1, "label": "None"},
                {"value": 2, "label": "Weak"},
                {"value": 3, "label": "Moderate"},
                {"value": 4, "label": "Strong"},
                {"value": 5, "label": "Very strong"},
            ],
        },
    },
    "likert_5": {
        "name": "5-point Likert (agreement)",
        "category": "attitude",
        "version": "1.0",
        "description": "Agreement with a statement. Put the statement in the question label.",
        "recommended_use": "Attitudes, perceived healthiness, purchase intent statements.",
        "citation": "Likert (1932) Arch Psychol 140:1-55",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "buttons",
            "options": [
                {"value": 1, "label": "Strongly disagree"},
                {"value": 2, "label": "Disagree"},
                {"value": 3, "label": "Neither agree nor disagree"},
                {"value": 4, "label": "Agree"},
                {"value": 5, "label": "Strongly agree"},
            ],
        },
    },
    "likert_7": {
        "name": "7-point Likert (agreement)",
        "category": "attitude",
        "version": "1.0",
        "description": "Agreement with a statement, finer resolution than 5-point.",
        "recommended_use": "Attitudes and statements where more resolution is needed.",
        "citation": "Likert (1932) Arch Psychol 140:1-55",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "buttons",
            "options": [
                {"value": 1, "label": "Strongly disagree"},
                {"value": 2, "label": "Disagree"},
                {"value": 3, "label": "Somewhat disagree"},
                {"value": 4, "label": "Neither agree nor disagree"},
                {"value": 5, "label": "Somewhat agree"},
                {"value": 6, "label": "Agree"},
                {"value": 7, "label": "Strongly agree"},
            ],
        },
    },
    "jar_5": {
        "name": "JAR (Just-About-Right), 5-point",
        "category": "ideal_point",
        "version": "1.0",
        "description": (
            "Bipolar scale centred on the ideal (3 = just about right). Use the "
            "'ideal_point' transform with ideal = 3 to optimise toward JAR."
        ),
        "recommended_use": "Diagnosing attribute deviations from ideal; penalty analysis.",
        "citation": "Rothman & Parker (2009) ASTM MNL63",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "buttons",
            "ideal_value": 3,
            "options": [
                {"value": 1, "label": "Much too weak"},
                {"value": 2, "label": "Somewhat too weak"},
                {"value": 3, "label": "Just about right"},
                {"value": 4, "label": "Somewhat too strong"},
                {"value": 5, "label": "Much too strong"},
            ],
        },
    },
    "faces_3": {
        "name": "Facial hedonic scale, 3-point",
        "category": "hedonic",
        "version": "1.0",
        "description": "Smiley-face liking scale for young children (~3 years).",
        "recommended_use": "Children around 3 years old.",
        "citation": "Chen, Resurreccion & Paguio (1996) J Sens Stud 11:141-163",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "faces",
            "options": [
                {"value": 1, "label": "Bad", "icon": "☹️"},
                {"value": 2, "label": "Maybe good or maybe bad", "icon": "😐"},
                {"value": 3, "label": "Good", "icon": "🙂"},
            ],
        },
    },
    "faces_5": {
        "name": "Facial hedonic scale, 5-point",
        "category": "hedonic",
        "version": "1.0",
        "description": "Smiley-face liking scale for children (~4 years) or low-literacy panels.",
        "recommended_use": "Children around 4 years old.",
        "citation": "Chen, Resurreccion & Paguio (1996) J Sens Stud 11:141-163",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "faces",
            "options": [
                {"value": 1, "label": "Super bad", "icon": "😖"},
                {"value": 2, "label": "Bad", "icon": "☹️"},
                {"value": 3, "label": "Maybe good or maybe bad", "icon": "😐"},
                {"value": 4, "label": "Good", "icon": "🙂"},
                {"value": 5, "label": "Super good", "icon": "😄"},
            ],
        },
    },
    "faces_7": {
        "name": "Facial hedonic scale, 7-point",
        "category": "hedonic",
        "version": "1.0",
        "description": "Smiley-face liking scale for children aged ~5 and older.",
        "recommended_use": "Children aged 5 and older.",
        "citation": "Chen, Resurreccion & Paguio (1996) J Sens Stud 11:141-163",
        "default_transform": "identity",
        "anchors_verified": True,
        "question": {
            "type": "category_scale",
            "layout": "horizontal",
            "style": "faces",
            "options": [
                {"value": 1, "label": "Super bad", "icon": "😖"},
                {"value": 2, "label": "Really bad", "icon": "😣"},
                {"value": 3, "label": "Bad", "icon": "☹️"},
                {"value": 4, "label": "Maybe good or maybe bad", "icon": "😐"},
                {"value": 5, "label": "Good", "icon": "🙂"},
                {"value": 6, "label": "Really good", "icon": "😊"},
                {"value": 7, "label": "Super good", "icon": "😄"},
            ],
        },
    },
    # ------------------------------------------------------------------
    # Other response formats
    # ------------------------------------------------------------------
    "magnitude_estimation": {
        "name": "Magnitude estimation (free modulus)",
        "category": "intensity",
        "version": "1.0",
        "description": (
            "Subject assigns any positive number proportional to perceived "
            "intensity. Set 'modulus' for fixed-modulus ME. Log-transformed by default."
        ),
        "recommended_use": "Ratio-scaled intensity with trained panels.",
        "citation": "Stevens (1956) Am J Psychol 69:1-25",
        "default_transform": "log10p1",
        "anchors_verified": True,
        "question": {
            "type": "magnitude_estimation",
            "allow_zero": False,
        },
    },
    "cata_basic_tastes": {
        "name": "CATA – basic tastes",
        "category": "descriptive",
        "version": "1.0",
        "description": "Check-all-that-apply list of basic tastes. Edit the options freely.",
        "recommended_use": "Quick qualitative profiling alongside a liking question.",
        "citation": "Ares & Jaeger (2013) Food Qual Prefer 28:141-153",
        "default_transform": None,
        "anchors_verified": True,
        "question": {
            "type": "multi_select",
            "randomize_order": True,
            "options": [
                {"value": "sweet", "label": "Sweet"},
                {"value": "sour", "label": "Sour"},
                {"value": "salty", "label": "Salty"},
                {"value": "bitter", "label": "Bitter"},
                {"value": "umami", "label": "Umami (savory)"},
            ],
        },
    },
}


# ============================================================================
# RESOLUTION
# ============================================================================


def get_scale_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    """Return a deep copy of a preset, or None if unknown."""
    preset = SCALE_PRESETS.get(preset_id)
    return copy.deepcopy(preset) if preset else None


def list_scale_presets() -> List[Dict[str, Any]]:
    """Return all presets as a list (deep-copied) with their ids included."""
    return [{"id": pid, **copy.deepcopy(p)} for pid, p in SCALE_PRESETS.items()]


def _normalize_options(options: Any) -> Any:
    """Turn ['a', 'b'] into [{'value': 'a', 'label': 'a'}, ...]; leave dicts as-is."""
    if not isinstance(options, list):
        return options
    normalized = []
    for opt in options:
        if isinstance(opt, dict):
            normalized.append(opt)
        else:
            normalized.append({"value": opt, "label": str(opt)})
    return normalized


def resolve_question(question: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge a question with its preset (if any) and type defaults.

    Precedence (lowest → highest): type defaults, preset question fields,
    question fields. Unknown presets are left unresolved (validation reports them).
    Legacy question types are returned unchanged (deep-copied).
    """
    q = copy.deepcopy(question)
    preset_id = q.get("preset")
    preset = SCALE_PRESETS.get(preset_id) if preset_id else None

    merged: Dict[str, Any] = {}
    if preset:
        merged.update(copy.deepcopy(preset["question"]))
    merged.update(q)

    q_type = merged.get("type")
    if q_type in TYPE_DEFAULTS:
        for key, value in TYPE_DEFAULTS[q_type].items():
            merged.setdefault(key, copy.deepcopy(value))

    if preset:
        merged.setdefault("preset_version", preset.get("version"))

    if q_type in ("category_scale", "multi_select", "ranking"):
        merged["options"] = _normalize_options(merged.get("options"))

    return merged


def resolve_questionnaire(questionnaire: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the questionnaire with every question resolved."""
    resolved = copy.deepcopy(questionnaire)
    questions = resolved.get("questions")
    if isinstance(questions, list):
        resolved["questions"] = [
            resolve_question(q) if isinstance(q, dict) else q for q in questions
        ]
    return resolved


def get_default_transform(question: Dict[str, Any]) -> str:
    """Default BO transform for a question (from its preset), else 'identity'."""
    preset = SCALE_PRESETS.get(question.get("preset") or "")
    if preset and preset.get("default_transform"):
        return preset["default_transform"]
    return "identity"


# ============================================================================
# VALIDATION
# ============================================================================


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _option_values(question: Dict[str, Any]) -> List[Any]:
    values = []
    for opt in question.get("options") or []:
        values.append(opt.get("value") if isinstance(opt, dict) else opt)
    return values


def validate_question_config(question: Dict[str, Any]) -> List[str]:
    """
    Validate a single (raw, unresolved) question definition.

    Returns a list of human-readable error strings (empty if valid).
    """
    errors: List[str] = []
    q_id = question.get("id", "?")

    preset_id = question.get("preset")
    if preset_id and preset_id not in SCALE_PRESETS:
        errors.append(f"Question '{q_id}': unknown scale preset '{preset_id}'")
        return errors

    q = resolve_question(question)
    q_type = q.get("type")

    if not q_type:
        errors.append(f"Question '{q_id}' missing 'type' field")
        return errors
    if q_type not in QUESTION_TYPES:
        errors.append(
            f"Question '{q_id}': unknown type '{q_type}' "
            f"(expected one of {sorted(QUESTION_TYPES)})"
        )
        return errors

    if q_type in ("slider", "line_scale"):
        lo, hi = q.get("min"), q.get("max")
        if lo is None or hi is None:
            errors.append(f"Question '{q_id}': {q_type} requires min and max")
        elif not (_is_number(lo) and _is_number(hi)):
            errors.append(f"Question '{q_id}': min/max must be numbers")
        elif lo >= hi:
            errors.append(f"Question '{q_id}': min must be < max")
        step = q.get("step")
        if step is not None and (not _is_number(step) or step <= 0):
            errors.append(f"Question '{q_id}': step must be a positive number")

    if q_type == "line_scale":
        errors.extend(_validate_line_scale(q_id, q))
    elif q_type == "category_scale":
        errors.extend(_validate_category_scale(q_id, q))
    elif q_type == "magnitude_estimation":
        errors.extend(_validate_magnitude_estimation(q_id, q))
    elif q_type == "multi_select":
        errors.extend(_validate_multi_select(q_id, q))
    elif q_type == "ranking":
        errors.extend(_validate_ranking(q_id, q))
    elif q_type == "dropdown":
        if not q.get("options"):
            errors.append(f"Dropdown question '{q_id}' missing options")

    return errors


def _validate_line_scale(q_id: str, q: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    if q.get("orientation") not in ORIENTATIONS:
        errors.append(
            f"Question '{q_id}': orientation must be one of {sorted(ORIENTATIONS)}"
        )
    if q.get("polarity") not in POLARITIES:
        errors.append(f"Question '{q_id}': polarity must be one of {sorted(POLARITIES)}")

    anchors = q.get("anchors")
    if not isinstance(anchors, list):
        errors.append(f"Question '{q_id}': anchors must be a list")
        return errors

    lo, hi = q.get("min"), q.get("max")
    range_ok = _is_number(lo) and _is_number(hi) and lo < hi
    prev = None
    for i, anchor in enumerate(anchors):
        if not isinstance(anchor, dict):
            errors.append(f"Question '{q_id}': anchor {i} must be an object")
            continue
        value, label = anchor.get("value"), anchor.get("label")
        if not _is_number(value):
            errors.append(f"Question '{q_id}': anchor {i} value must be a number")
            continue
        if not isinstance(label, str) or not label.strip():
            errors.append(f"Question '{q_id}': anchor {i} needs a non-empty label")
        if range_ok and not (lo <= value <= hi):
            errors.append(
                f"Question '{q_id}': anchor '{label}' value {value} outside [{lo}, {hi}]"
            )
        if prev is not None and value <= prev:
            errors.append(
                f"Question '{q_id}': anchors must be in strictly increasing value order"
            )
        prev = value
    return errors


def _validate_category_scale(q_id: str, q: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    options = q.get("options")
    if not isinstance(options, list) or len(options) < 2:
        errors.append(f"Question '{q_id}': category_scale needs at least 2 options")
        return errors
    values = []
    for i, opt in enumerate(options):
        if not isinstance(opt, dict) or not _is_number(opt.get("value")):
            errors.append(f"Question '{q_id}': option {i} must have a numeric 'value'")
            continue
        if not isinstance(opt.get("label"), str) or not opt["label"].strip():
            errors.append(f"Question '{q_id}': option {i} needs a non-empty label")
        values.append(opt["value"])
    if len(values) != len(set(values)):
        errors.append(f"Question '{q_id}': option values must be unique")
    if q.get("layout") not in CATEGORY_LAYOUTS:
        errors.append(f"Question '{q_id}': layout must be one of {sorted(CATEGORY_LAYOUTS)}")
    if q.get("style") not in CATEGORY_STYLES:
        errors.append(f"Question '{q_id}': style must be one of {sorted(CATEGORY_STYLES)}")
    ideal = q.get("ideal_value")
    if ideal is not None and ideal not in values:
        errors.append(f"Question '{q_id}': ideal_value {ideal} is not one of the option values")
    return errors


def _validate_magnitude_estimation(q_id: str, q: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    modulus = q.get("modulus")
    if modulus is not None and (not _is_number(modulus) or modulus <= 0):
        errors.append(f"Question '{q_id}': modulus must be a positive number")
    max_val = q.get("max")
    if max_val is not None and (not _is_number(max_val) or max_val <= 0):
        errors.append(f"Question '{q_id}': max must be a positive number")
    return errors


def _validate_choice_options(q_id: str, q: Dict[str, Any], min_count: int) -> List[str]:
    errors: List[str] = []
    options = q.get("options")
    if not isinstance(options, list) or len(options) < min_count:
        errors.append(f"Question '{q_id}': needs at least {min_count} options")
        return errors
    values = _option_values(q)
    if any(v is None or (isinstance(v, str) and not v.strip()) for v in values):
        errors.append(f"Question '{q_id}': every option needs a value")
    if len(values) != len(set(map(str, values))):
        errors.append(f"Question '{q_id}': option values must be unique")
    return errors


def _validate_multi_select(q_id: str, q: Dict[str, Any]) -> List[str]:
    errors = _validate_choice_options(q_id, q, 1)
    n = len(q.get("options") or [])
    lo = q.get("min_selected", 0)
    hi = q.get("max_selected")
    if not isinstance(lo, int) or isinstance(lo, bool) or lo < 0:
        errors.append(f"Question '{q_id}': min_selected must be a non-negative integer")
    elif hi is not None:
        if not isinstance(hi, int) or isinstance(hi, bool) or hi < max(lo, 1):
            errors.append(f"Question '{q_id}': max_selected must be an integer >= min_selected")
        elif hi > n:
            errors.append(f"Question '{q_id}': max_selected exceeds number of options")
    elif lo > n:
        errors.append(f"Question '{q_id}': min_selected exceeds number of options")
    return errors


def _validate_ranking(q_id: str, q: Dict[str, Any]) -> List[str]:
    return _validate_choice_options(q_id, q, 2)


# ============================================================================
# ANSWER VALIDATION
# ============================================================================


def validate_answer(question: Dict[str, Any], value: Any) -> Optional[str]:
    """
    Validate one answer against a resolved question.

    Returns an error string, or None if the answer is acceptable.
    ``None`` answers are not checked here (required-ness is handled by caller).
    """
    q_id = question.get("id", "?")
    q_type = question.get("type")

    if value is None:
        return None

    if q_type in ("slider", "line_scale"):
        if not _is_number(value):
            return f"Answer for '{q_id}' must be a number"
        lo, hi = question.get("min"), question.get("max")
        if _is_number(lo) and _is_number(hi) and not (lo <= value <= hi):
            return f"Answer for '{q_id}' out of range [{lo}, {hi}]"
        return None

    if q_type == "category_scale":
        if not _is_number(value):
            return f"Answer for '{q_id}' must be a number"
        if value not in _option_values(question):
            return f"Answer for '{q_id}' is not one of the scale options"
        return None

    if q_type == "pillbox":
        values = _option_values(question)
        if values:
            if str(value) not in {str(v) for v in values}:
                return f"Answer for '{q_id}' is not one of the options"
            return None
        if not _is_number(value):
            return f"Answer for '{q_id}' must be a number"
        lo, hi = question.get("min"), question.get("max")
        if _is_number(lo) and _is_number(hi) and not (lo <= value <= hi):
            return f"Answer for '{q_id}' out of range [{lo}, {hi}]"
        return None

    if q_type == "dropdown":
        if str(value) not in {str(v) for v in _option_values(question)}:
            return f"Answer for '{q_id}' is not one of the options"
        return None

    if q_type == "magnitude_estimation":
        if not _is_number(value):
            return f"Answer for '{q_id}' must be a number"
        if value < 0 or (value == 0 and not question.get("allow_zero", False)):
            return f"Answer for '{q_id}' must be a positive number"
        max_val = question.get("max")
        if _is_number(max_val) and value > max_val:
            return f"Answer for '{q_id}' exceeds maximum {max_val}"
        return None

    if q_type == "multi_select":
        if not isinstance(value, list):
            return f"Answer for '{q_id}' must be a list"
        allowed = {str(v) for v in _option_values(question)}
        picked = [str(v) for v in value]
        if any(v not in allowed for v in picked):
            return f"Answer for '{q_id}' contains an unknown option"
        if len(picked) != len(set(picked)):
            return f"Answer for '{q_id}' contains duplicates"
        lo = question.get("min_selected", 0) or 0
        hi = question.get("max_selected")
        if len(picked) < lo:
            return f"Select at least {lo} option(s) for '{q_id}'"
        if hi is not None and len(picked) > hi:
            return f"Select at most {hi} option(s) for '{q_id}'"
        return None

    if q_type == "ranking":
        if not isinstance(value, list):
            return f"Answer for '{q_id}' must be a list"
        allowed = sorted(str(v) for v in _option_values(question))
        if sorted(str(v) for v in value) != allowed:
            return f"Answer for '{q_id}' must rank every option exactly once"
        return None

    if q_type in ("text_input", "text_area"):
        if not isinstance(value, str):
            return f"Answer for '{q_id}' must be text"
        max_length = question.get("max_length")
        if isinstance(max_length, int) and len(value) > max_length:
            return f"Answer for '{q_id}' exceeds {max_length} characters"
        return None

    return None


def is_answered(value: Any) -> bool:
    """True if an answer counts as provided (for required-question checks)."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, list):
        return True  # an empty CATA selection is a valid answer; min_selected enforces counts
    return True
