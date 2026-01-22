"""
Protocol Schema Definition for RoboTaste Experiment Protocols

This module defines the JSON schema and data structures for experiment protocols.
Protocols are comprehensive blueprints that define all aspects of an experiment.

Author: RoboTaste Team
Version: 1.0
Created: 2026-01-01
"""

from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, asdict
from datetime import datetime
import json


# =============================================================================
# Type Definitions
# =============================================================================

SelectionMode = Literal["user_selected", "bo_selected", "predetermined"]
PhaseType = Literal["builtin", "custom", "loop"]
BuiltinPhase = Literal[
    "waiting",
    "registration",
    "instructions",
    "loading",
    "questionnaire",
    "selection",
    "completion",
]
CustomPhaseType = Literal[
    "custom_text", "custom_media", "custom_survey", "break", "calibration"
]


# =============================================================================
# Protocol Schema - Complete JSON Structure
# =============================================================================

PROTOCOL_JSON_SCHEMA = {
    "type": "object",
    "required": [
        "protocol_id",
        "name",
        "version",
        "ingredients",
        "sample_selection_schedule",
        "questionnaire_type",
    ],
    "properties": {
        # ===== Identity =====
        "protocol_id": {"type": "string", "description": "Unique identifier (UUID)"},
        "name": {
            "type": "string",
            "minLength": 1,
            "maxLength": 200,
            "description": "Protocol name",
        },
        "description": {
            "type": "string",
            "maxLength": 1000,
            "description": "Detailed description of the protocol",
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+$",
            "description": "Protocol version (semantic versioning: major.minor)",
        },
        "schema_version": {
            "type": "string",
            "description": "Schema version this protocol conforms to",
        },
        "created_by": {"type": "string", "description": "Creator/researcher name"},
        "created_at": {
            "type": "string",
            "format": "date-time",
            "description": "Creation timestamp",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Categorization tags",
        },
        # ===== Ingredients =====
        "ingredients": {
            "type": "array",
            "minItems": 1,
            "maxItems": 6,
            "items": {
                "type": "object",
                "required": ["name", "min_concentration", "max_concentration"],
                "properties": {
                    "name": {"type": "string"},
                    "min_concentration": {"type": "number", "minimum": 0},
                    "max_concentration": {"type": "number", "minimum": 0},
                    "unit": {"type": "string", "default": "mM"},
                    "molecular_weight": {"type": "number"},
                    "stock_concentration_mM": {"type": "number"},
                },
            },
        },
        # ===== Sample Selection Schedule (MIXED-MODE SUPPORT) =====
        "sample_selection_schedule": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["cycle_range", "mode"],
                "properties": {
                    "cycle_range": {
                        "type": "object",
                        "required": ["start", "end"],
                        "properties": {
                            "start": {"type": "integer", "minimum": 1},
                            "end": {"type": "integer", "minimum": 1},
                        },
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["user_selected", "bo_selected", "predetermined"],
                    },
                    "predetermined_samples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["cycle", "concentrations"],
                            "properties": {
                                "cycle": {"type": "integer"},
                                "concentrations": {
                                    "type": "object",
                                    "additionalProperties": {"type": "number"},
                                },
                            },
                        },
                    },
                    "config": {
                        "type": "object",
                        "properties": {
                            "interface_type": {
                                "type": "string",
                                "enum": ["grid", "sliders", "auto"],
                            },
                            "randomize_start": {"type": "boolean"},
                            "show_bo_suggestion": {"type": "boolean"},
                            "allow_override": {"type": "boolean"},
                            "auto_accept_suggestion": {"type": "boolean"},
                        },
                    },
                },
            },
        },
        # ===== Questionnaire =====
        "questionnaire_type": {
            "type": "string",
            "description": "Questionnaire type ID from QUESTIONNAIRE_CONFIGS",
        },
        # ===== Bayesian Optimization =====
        "bayesian_optimization": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "min_samples_for_bo": {"type": "integer", "minimum": 2},
                "acquisition_function": {"type": "string", "enum": ["ei", "ucb"]},
                "ei_xi": {"type": "number", "minimum": 0, "maximum": 1},
                "ucb_kappa": {"type": "number", "minimum": 0.1, "maximum": 10},
                "adaptive_acquisition": {"type": "boolean"},
                "exploration_budget": {"type": "number", "minimum": 0, "maximum": 1},
                "xi_exploration": {"type": "number"},
                "xi_exploitation": {"type": "number"},
                "kappa_exploration": {"type": "number"},
                "kappa_exploitation": {"type": "number"},
                "kernel_nu": {"type": "number", "enum": [0.5, 1.5, 2.5, float("inf")]},
                "alpha": {"type": "number", "minimum": 0, "maximum": 1},
                "n_restarts_optimizer": {"type": "integer", "minimum": 1},
            },
        },
        # ===== Phase Sequence (CUSTOM PHASES) =====
        "phase_sequence": {
            "type": "object",
            "properties": {
                "phases": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["phase_id", "phase_type"],
                        "properties": {
                            "phase_id": {"type": "string"},
                            "phase_type": {
                                "type": "string",
                                "enum": ["builtin", "custom", "loop"],
                            },
                            "required": {"type": "boolean"},
                            "duration_ms": {"type": ["integer", "null"]},
                            "auto_advance": {"type": "boolean"},
                            "content": {"type": "object"},
                            "loop_config": {"type": "object"},
                        },
                    },
                }
            },
        },
        # ===== Stopping Criteria =====
        "stopping_criteria": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["manual_only", "suggest_auto", "auto_with_minimum"],
                },
                "min_cycles": {"type": "integer", "minimum": 1},
                "max_cycles": {"type": "integer", "minimum": 1},
                "convergence_detection": {"type": "boolean"},
                "early_termination_allowed": {"type": "boolean"},
                "ei_threshold": {"type": "number"},
                "stability_threshold": {"type": "number"},
            },
        },
        # ===== Presentation Options =====
        "presentation": {
            "type": "object",
            "properties": {
                "randomize_start": {"type": "boolean"},
                "show_cycle_counter": {"type": "boolean"},
                "show_convergence_indicator": {"type": "boolean"},
                "display_bo_predictions": {"type": "boolean"},
            },
        },
        # ===== Loading Screen Configuration =====
        "loading_screen": {
            "type": "object",
            "description": "Configuration for loading/preparation screen displayed between cycles",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Instructions displayed during loading phase",
                    "default": "Rinse your mouth while the robot prepares the next sample.",
                },
                "duration_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 60,
                    "description": "Duration of loading screen in seconds (used when use_dynamic_duration is false)",
                    "default": 5,
                },
                "use_dynamic_duration": {
                    "type": "boolean",
                    "description": "If true, calculate duration from pump operation time instead of using duration_seconds",
                    "default": False,
                },
                "show_progress": {
                    "type": "boolean",
                    "description": "Display animated progress bar during loading",
                    "default": True,
                },
                "show_cycle_info": {
                    "type": "boolean",
                    "description": "Display current cycle number and total cycles",
                    "default": True,
                },
                "message_size": {
                    "type": "string",
                    "enum": ["normal", "large", "extra_large"],
                    "description": "Font size for loading message (normal=1.5rem, large=2.5rem, extra_large=3.5rem)",
                    "default": "large",
                },
            },
        },
        # ===== Data Collection Options =====
        "data_collection": {
            "type": "object",
            "properties": {
                "track_trajectory": {"type": "boolean"},
                "track_interaction_times": {"type": "boolean"},
                "collect_demographics": {"type": "boolean"},
                "custom_metadata": {"type": "object"},
            },
        },
        # ===== Pump Configuration =====
        "pump_config": {
            "type": "object",
            "description": "Configuration for automated syringe pump control",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "Enable automatic pump dispensing",
                    "default": False,
                },
                "serial_port": {
                    "type": "string",
                    "description": "Serial port for pump connection (e.g., /dev/ttyUSB0, COM3)",
                },
                "baud_rate": {
                    "type": "integer",
                    "enum": [300, 1200, 2400, 9600, 19200],
                    "description": "Serial communication baud rate",
                    "default": 19200,
                },
                "pumps": {
                    "type": "array",
                    "description": "List of pump configurations",
                    "items": {
                        "type": "object",
                        "required": ["address", "ingredient", "syringe_diameter_mm"],
                        "properties": {
                            "address": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 99,
                                "description": "Pump network address (0-99)",
                            },
                            "ingredient": {
                                "type": "string",
                                "description": "Ingredient name (must match protocol ingredient)",
                            },
                            "syringe_diameter_mm": {
                                "type": "number",
                                "minimum": 0.1,
                                "maximum": 50.0,
                                "description": "Syringe inner diameter in millimeters",
                            },
                            "volume_unit": {
                                "type": "string",
                                "enum": ["ML", "UL"],
                                "description": "Pump volume unit (mL or µL)",
                                "default": "ML",
                            },
                            "max_rate_ul_min": {
                                "type": "number",
                                "minimum": 0.1,
                                "description": "Maximum pumping rate in µL/min",
                                "default": 3000,
                            },
                            "stock_concentration_mM": {
                                "type": "number",
                                "minimum": 0,
                                "description": "Stock solution concentration in mM",
                            },
                        },
                    },
                },
                "total_volume_ml": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 1000,
                    "description": "Total sample volume in mL",
                    "default": 10.0,
                },
                "dispensing_rate_ul_min": {
                    "type": "number",
                    "minimum": 0.1,
                    "description": "Default dispensing rate in µL/min",
                    "default": 2000,
                },
                "simultaneous_dispensing": {
                    "type": "boolean",
                    "description": "Enable simultaneous dispensing for multiple pumps",
                    "default": True,
                },
                "use_burst_mode": {
                    "type": "boolean",
                    "description": "Use Network Command Burst for simultaneous dispensing (requires pump addresses 0-9). Significantly faster than individual commands.",
                    "default": False,
                },
            },
        },
    },
}


# =============================================================================
# Example Protocol - Full Specification
# =============================================================================

EXAMPLE_PROTOCOL_MIXED_MODE = {
    # Identity
    "protocol_id": "proto_example_001",
    "name": "Mixed-Mode Sugar-Salt Optimization",
    "description": "Calibration with pre-determined samples, exploration with user selection, then BO optimization",
    "version": "1.0",
    "schema_version": "1.0",
    "created_by": "Research Team",
    "created_at": "2026-01-01T00:00:00Z",
    "tags": ["binary", "hedonic", "mixed-mode", "research"],
    # Ingredients
    "ingredients": [
        {
            "name": "Sugar",
            "min_concentration": 0.73,
            "max_concentration": 73.0,
            "unit": "mM",
            "molecular_weight": 342.3,
            "stock_concentration_mM": 1000.0,
        },
        {
            "name": "Salt",
            "min_concentration": 0.10,
            "max_concentration": 10.0,
            "unit": "mM",
            "molecular_weight": 58.44,
            "stock_concentration_mM": 1000.0,
        },
    ],
    # Sample Selection Schedule (MIXED-MODE)
    "sample_selection_schedule": [
        {
            "cycle_range": {"start": 1, "end": 2},
            "mode": "predetermined",
            "predetermined_samples": [
                {"cycle": 1, "concentrations": {"Sugar": 10.0, "Salt": 2.0}},
                {"cycle": 2, "concentrations": {"Sugar": 40.0, "Salt": 6.0}},
            ],
        },
        {
            "cycle_range": {"start": 3, "end": 5},
            "mode": "user_selected",
            "config": {"interface_type": "grid", "randomize_start": True},
        },
        {
            "cycle_range": {"start": 6, "end": 15},
            "mode": "bo_selected",
            "config": {
                "show_bo_suggestion": True,
                "allow_override": True,
                "auto_accept_suggestion": False,
            },
        },
    ],
    # Questionnaire
    "questionnaire_type": "hedonic_continuous",
    # Bayesian Optimization (applies when mode = "bo_selected")
    "bayesian_optimization": {
        "enabled": True,
        "min_samples_for_bo": 3,
        "acquisition_function": "ei",
        "ei_xi": 0.01,
        "ucb_kappa": 2.0,
        "adaptive_acquisition": True,
        "exploration_budget": 0.25,
        "xi_exploration": 0.1,
        "xi_exploitation": 0.01,
        "kappa_exploration": 3.0,
        "kappa_exploitation": 1.0,
        "kernel_nu": 2.5,
        "alpha": 1e-3,
        "n_restarts_optimizer": 10,
    },
    # Phase Sequence (optional - if not specified, use default)
    "phase_sequence": {
        "phases": [
            {"phase_id": "waiting", "phase_type": "builtin", "required": True},
            {"phase_id": "registration", "phase_type": "builtin", "required": False},
            {"phase_id": "instructions", "phase_type": "builtin", "required": True},
            {"phase_id": "experiment_loop", "phase_type": "loop", "required": True},
        ]
    },
    # Stopping Criteria
    "stopping_criteria": {
        "mode": "suggest_auto",
        "min_cycles": 15,
        "max_cycles": 30,
        "convergence_detection": True,
        "early_termination_allowed": True,
        "ei_threshold": 0.001,
        "stability_threshold": 0.05,
    },
    # Presentation
    "presentation": {
        "randomize_start": True,
        "show_cycle_counter": True,
        "show_convergence_indicator": True,
        "display_bo_predictions": True,
    },
    # Loading Screen Configuration
    "loading_screen": {
        "message": "Please rinse your mouth with water while the robot prepares the next sample.",
        "duration_seconds": 5,
        "show_progress": True,
        "show_cycle_info": True,
        "message_size": "large",
    },
    # Data Collection
    "data_collection": {
        "track_trajectory": True,
        "track_interaction_times": True,
        "collect_demographics": True,
        "custom_metadata": {},
    },
}


# =============================================================================
# Helper Functions
# =============================================================================


def get_empty_protocol_template() -> Dict[str, Any]:
    """
    Get an empty protocol template with minimal required fields.

    Returns:
        Dict with minimal protocol structure
    """
    return {
        "protocol_id": "",  # Will be generated
        "name": "",
        "description": "",
        "version": "1.0",
        "schema_version": "1.0",
        "created_by": "",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "tags": [],
        "ingredients": [],
        "sample_selection_schedule": [],
        "questionnaire_type": "hedonic_continuous",
        "bayesian_optimization": {
            "enabled": True,
            "min_samples_for_bo": 3,
            "acquisition_function": "ei",
            "adaptive_acquisition": True,
        },
        "stopping_criteria": {
            "mode": "suggest_auto",
            "min_cycles": 10,
            "max_cycles": 30,
            "convergence_detection": True,
        },
        "presentation": {
            "randomize_start": True,
            "show_cycle_counter": True,
            "show_convergence_indicator": True,
        },
        "data_collection": {
            "track_trajectory": True,
            "track_interaction_times": True,
            "collect_demographics": True,
        },
        "pump_config": {
            "enabled": False,
            "serial_port": "",
            "baud_rate": 19200,
            "pumps": [],
            "total_volume_ml": 10.0,
            "dispensing_rate_ul_min": 2000,
            "simultaneous_dispensing": True,
            "use_burst_mode": False,
        },
    }


def get_selection_mode_for_cycle(
    protocol: Dict[str, Any], cycle_number: int
) -> SelectionMode:
    """
    Determine the selection mode for a specific cycle based on the protocol schedule.

    Args:
        protocol: Protocol dictionary
        cycle_number: Current cycle number (1-indexed)

    Returns:
        Selection mode: "user_selected", "bo_selected", or "predetermined"
    """
    schedule = protocol.get("sample_selection_schedule", [])

    for entry in schedule:
        cycle_range = entry.get("cycle_range", {})
        start = cycle_range.get("start", 0)
        end = cycle_range.get("end", 0)

        if start <= cycle_number <= end:
            return entry.get("mode", "user_selected")

    # Fallback to user_selected if no matching range
    return "user_selected"


def get_predetermined_sample(
    protocol: Dict[str, Any], cycle_number: int
) -> Optional[Dict[str, float]]:
    """
    Get the predetermined sample concentrations for a specific cycle.

    Args:
        protocol: Protocol dictionary
        cycle_number: Current cycle number (1-indexed)

    Returns:
        Dict of {ingredient_name: concentration} or None if not predetermined
    """
    schedule = protocol.get("sample_selection_schedule", [])

    for entry in schedule:
        if entry.get("mode") != "predetermined":
            continue

        cycle_range = entry.get("cycle_range", {})
        start = cycle_range.get("start", 0)
        end = cycle_range.get("end", 0)

        if start <= cycle_number <= end:
            # Find the specific sample for this cycle
            samples = entry.get("predetermined_samples", [])
            for sample in samples:
                if sample.get("cycle") == cycle_number:
                    return sample.get("concentrations")

    return None


def protocol_to_json(protocol: Dict[str, Any]) -> str:
    """
    Convert protocol dictionary to JSON string.

    Args:
        protocol: Protocol dictionary

    Returns:
        JSON string
    """
    return json.dumps(protocol, indent=2, sort_keys=False)


def protocol_from_json(json_str: str) -> Dict[str, Any]:
    """
    Parse protocol from JSON string.

    Args:
        json_str: JSON string

    Returns:
        Protocol dictionary

    Raises:
        json.JSONDecodeError: If JSON is invalid
    """
    return json.loads(json_str)


# =============================================================================
# Validation Rules (Used by protocols.py)
# =============================================================================

VALIDATION_RULES = {
    "max_ingredients": 6,
    "min_ingredients": 1,
    "max_name_length": 200,
    "max_description_length": 1000,
    "min_cycles": 1,
    "max_cycles": 100,
    "valid_modes": ["user_selected", "bo_selected", "predetermined"],
    "valid_questionnaire_types": [
        "hedonic_continuous",
        "hedonic_discrete",
        "unified_feedback",
        "multi_attribute",
        "composite_preference",
        "intensity_continuous",
    ],
    "valid_acquisition_functions": ["ei", "ucb"],
    "valid_kernel_nu": [0.5, 1.5, 2.5, float("inf")],
}
