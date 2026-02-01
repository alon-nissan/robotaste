"""
Protocol Management for RoboTaste

This module provides core functions for creating, validating, and managing
experiment protocols. Protocols are comprehensive configuration blueprints
that define all aspects of an experiment.

Author: RoboTaste Team
Version: 1.0
Created: 2026-01-01
"""

import json
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import uuid

from robotaste.config.protocol_schema import (
    PROTOCOL_JSON_SCHEMA,
    VALIDATION_RULES,
    EXAMPLE_PROTOCOL_MIXED_MODE,
    get_empty_protocol_template,
    get_selection_mode_for_cycle,
    get_predetermined_sample,
    protocol_to_json,
    protocol_from_json,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Creation & Manipulation
# =============================================================================


def create_protocol(
    name: str,
    description: str = "",
    created_by: str = "",
    tags: List[str] = None,  # type: ignore
    **kwargs,
) -> Dict[str, Any]:
    """
    Create a new protocol with basic metadata.

    Args:
        name: Protocol name
        description: Protocol description
        created_by: Creator name
        tags: List of tags for categorization
        **kwargs: Additional protocol fields

    Returns:
        Protocol dictionary with generated ID and timestamp
    """
    protocol = get_empty_protocol_template()

    # Set identity fields
    protocol["protocol_id"] = f"proto_{uuid.uuid4().hex[:12]}"
    protocol["name"] = name
    protocol["description"] = description
    protocol["created_by"] = created_by
    protocol["tags"] = tags or []
    protocol["created_at"] = datetime.utcnow().isoformat() + "Z"
    protocol["schema_version"] = "1.0"
    protocol["version"] = "1.0"

    # Merge any additional fields
    protocol.update(kwargs)

    logger.info(f"Created protocol: {name} (ID: {protocol['protocol_id']})")

    return protocol


def clone_protocol(source_protocol: Dict[str, Any], new_name: str) -> Dict[str, Any]:
    """
    Create a copy of an existing protocol with a new name and ID.

    Args:
        source_protocol: Protocol to clone
        new_name: Name for the cloned protocol

    Returns:
        Cloned protocol with new ID and timestamp
    """
    cloned = source_protocol.copy()

    # Generate new identity
    cloned["protocol_id"] = f"proto_{uuid.uuid4().hex[:12]}"
    cloned["name"] = new_name
    cloned["created_at"] = datetime.utcnow().isoformat() + "Z"
    cloned["version"] = "1.0"  # Reset version for clone

    logger.info(f"Cloned protocol '{source_protocol['name']}' to '{new_name}'")

    return cloned


def compute_protocol_hash(protocol: Dict[str, Any]) -> str:
    """
    Compute SHA256 hash of protocol JSON for version control.

    Args:
        protocol: Protocol dictionary

    Returns:
        Hexadecimal hash string
    """
    # Create a copy without hash field itself
    protocol_copy = {k: v for k, v in protocol.items() if k != "protocol_hash"}

    # Convert to canonical JSON (sorted keys)
    json_str = json.dumps(protocol_copy, sort_keys=True)

    # Compute hash
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


# =============================================================================
# Protocol Validation
# =============================================================================


class ProtocolValidationError(Exception):
    """Raised when protocol validation fails."""

    pass


def validate_protocol(protocol: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate a protocol against all validation rules.

    Performs three levels of validation:
    1. Schema validation - JSON structure
    2. Semantic validation - Logical consistency
    3. Compatibility validation - Version compatibility

    Args:
        protocol: Protocol dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Level 1: Schema Validation
    schema_errors = _validate_schema(protocol)
    errors.extend(schema_errors)

    # Level 2: Semantic Validation
    semantic_errors = _validate_semantics(protocol)
    errors.extend(semantic_errors)

    # Level 3: Compatibility Validation (warnings only)
    compatibility_warnings = _validate_compatibility(protocol)
    # Don't add warnings to errors, just log them
    for warning in compatibility_warnings:
        logger.warning(f"Protocol compatibility: {warning}")

    is_valid = len(errors) == 0

    if is_valid:
        logger.info(f"Protocol '{protocol.get('name')}' passed validation")
    else:
        logger.error(f"Protocol validation failed with {len(errors)} errors")

    return is_valid, errors


def _validate_schema(protocol: Dict[str, Any]) -> List[str]:
    """Validate protocol against JSON schema structure."""
    errors = []

    # Check required fields (protocol_id is optional during creation)
    required_fields = [
        "name",
        "version",
        "ingredients",
        "sample_selection_schedule",
    ]
    for field in required_fields:
        if field not in protocol:
            errors.append(f"Missing required field: {field}")

    # Validate name length
    if "name" in protocol:
        name_len = len(protocol["name"])
        if name_len == 0:
            errors.append("Protocol name cannot be empty")
        elif name_len > VALIDATION_RULES["max_name_length"]:
            errors.append(
                f"Protocol name too long (max {VALIDATION_RULES['max_name_length']} chars)"
            )

    # Validate description length
    if (
        "description" in protocol
        and len(protocol["description"]) > VALIDATION_RULES["max_description_length"]
    ):
        errors.append(
            f"Description too long (max {VALIDATION_RULES['max_description_length']} chars)"
        )

    # Validate ingredients count
    if "ingredients" in protocol:
        num_ingredients = len(protocol["ingredients"])
        if num_ingredients < VALIDATION_RULES["min_ingredients"]:
            errors.append(
                f"Must have at least {VALIDATION_RULES['min_ingredients']} ingredient"
            )
        elif num_ingredients > VALIDATION_RULES["max_ingredients"]:
            errors.append(
                f"Too many ingredients (max {VALIDATION_RULES['max_ingredients']})"
            )

    return errors


def _validate_semantics(protocol: Dict[str, Any]) -> List[str]:
    """Validate logical consistency of protocol configuration."""
    errors = []

    # Validate sample selection schedule
    schedule_errors = _validate_sample_selection_schedule(protocol)
    errors.extend(schedule_errors)

    # Validate ingredients
    ingredient_errors = _validate_ingredients(protocol)
    errors.extend(ingredient_errors)

    # Validate questionnaire (inline or legacy)
    questionnaire_errors = _validate_questionnaire_config(protocol)
    errors.extend(questionnaire_errors)

    # Validate BO configuration
    bo_errors = _validate_bo_config(protocol)
    errors.extend(bo_errors)

    # Validate stopping criteria
    criteria_errors = _validate_stopping_criteria(protocol)
    errors.extend(criteria_errors)

    # Validate phase sequence (NEW for Week 5)
    phase_errors = _validate_phase_sequence(protocol)
    errors.extend(phase_errors)

    # Validate pump configuration
    pump_errors = _validate_pump_config(protocol)
    errors.extend(pump_errors)

    return errors


def _validate_sample_selection_schedule(protocol: Dict[str, Any]) -> List[str]:
    """Validate sample selection schedule is logically consistent."""
    errors = []

    schedule = protocol.get("sample_selection_schedule", [])

    if not schedule:
        errors.append("Sample selection schedule cannot be empty")
        return errors

    # Track cycle coverage to detect gaps/overlaps
    covered_cycles = set()

    for i, entry in enumerate(schedule):
        # Validate required fields
        if "cycle_range" not in entry:
            errors.append(f"Schedule entry {i+1}: missing cycle_range")
            continue

        if "mode" not in entry:
            errors.append(f"Schedule entry {i+1}: missing mode")
            continue

        cycle_range = entry["cycle_range"]
        mode = entry["mode"]

        # Validate cycle range
        if "start" not in cycle_range or "end" not in cycle_range:
            errors.append(
                f"Schedule entry {i+1}: cycle_range must have 'start' and 'end'"
            )
            continue

        start = cycle_range["start"]
        end = cycle_range["end"]

        if start < 1:
            errors.append(f"Schedule entry {i+1}: cycle start must be >= 1")

        if end < start:
            errors.append(f"Schedule entry {i+1}: cycle end ({end}) < start ({start})")

        # Check for overlaps
        for cycle in range(start, end + 1):
            if cycle in covered_cycles:
                errors.append(
                    f"Schedule entry {i+1}: cycle {cycle} already covered by another entry"
                )
            covered_cycles.add(cycle)

        # Validate mode
        if mode not in VALIDATION_RULES["valid_modes"]:
            errors.append(f"Schedule entry {i+1}: invalid mode '{mode}'")

        # Validate mode-specific requirements
        if mode in ["predetermined", "predetermined_absolute"]:
            if "predetermined_samples" not in entry:
                errors.append(
                    f"Schedule entry {i+1}: predetermined_absolute mode requires 'predetermined_samples'"
                )
            else:
                samples = entry["predetermined_samples"]
                expected_cycles = set(range(start, end + 1))
                provided_cycles = {s["cycle"] for s in samples if "cycle" in s}

                missing = expected_cycles - provided_cycles
                if missing:
                    errors.append(
                        f"Schedule entry {i+1}: missing predetermined samples for cycles {sorted(missing)}"
                    )

                # Validate concentration data
                for sample in samples:
                    if "concentrations" not in sample:
                        errors.append(
                            f"Schedule entry {i+1}, cycle {sample.get('cycle')}: missing concentrations"
                        )

        elif mode == "predetermined_randomized":
            if "sample_bank" not in entry:
                errors.append(
                    f"Schedule entry {i+1}: predetermined_randomized mode requires 'sample_bank'"
                )
            else:
                bank = entry["sample_bank"]

                # Validate required fields
                if "samples" not in bank:
                    errors.append(
                        f"Schedule entry {i+1}: sample_bank requires 'samples' array"
                    )
                elif not bank["samples"]:
                    errors.append(
                        f"Schedule entry {i+1}: sample_bank 'samples' cannot be empty"
                    )
                else:
                    # Check for duplicate sample IDs
                    sample_ids = [s.get("id") for s in bank["samples"] if "id" in s]
                    if len(sample_ids) != len(set(sample_ids)):
                        errors.append(
                            f"Schedule entry {i+1}: duplicate sample IDs in sample_bank"
                        )

                    # Validate each sample has concentrations
                    for sample in bank["samples"]:
                        if "id" not in sample:
                            errors.append(
                                f"Schedule entry {i+1}: sample_bank sample missing 'id'"
                            )
                        if "concentrations" not in sample:
                            errors.append(
                                f"Schedule entry {i+1}: sample_bank sample '{sample.get('id', '?')}' missing concentrations"
                            )

                # Validate design_type
                if "design_type" not in bank:
                    errors.append(
                        f"Schedule entry {i+1}: sample_bank requires 'design_type'"
                    )
                elif bank["design_type"] not in ["randomized", "latin_square"]:
                    errors.append(
                        f"Schedule entry {i+1}: invalid design_type '{bank['design_type']}' (must be 'randomized' or 'latin_square')"
                    )

                # Warn if bank size doesn't match cycle count
                if "samples" in bank and bank["samples"]:
                    bank_size = len(bank["samples"])
                    cycle_count = end - start + 1
                    if bank_size != cycle_count:
                        warnings.append(
                            f"Schedule entry {i+1}: sample_bank size ({bank_size}) doesn't match cycle count ({cycle_count})"
                        )

    # Check for gaps in cycle coverage (warn only)
    if covered_cycles:
        max_cycle = max(covered_cycles)
        all_cycles = set(range(1, max_cycle + 1))
        gaps = all_cycles - covered_cycles
        if gaps:
            logger.warning(
                f"Cycle coverage has gaps: {sorted(gaps)} (will default to user_selected)"
            )

    return errors


def _validate_ingredients(protocol: Dict[str, Any]) -> List[str]:
    """Validate ingredient configurations."""
    errors = []

    ingredients = protocol.get("ingredients", [])

    for i, ingredient in enumerate(ingredients):
        if "name" not in ingredient:
            errors.append(f"Ingredient {i+1}: missing name")

        if (
            "min_concentration" not in ingredient
            or "max_concentration" not in ingredient
        ):
            errors.append(f"Ingredient {i+1}: missing concentration range")
            continue

        min_conc = ingredient["min_concentration"]
        max_conc = ingredient["max_concentration"]

        if min_conc < 0:
            errors.append(f"Ingredient {i+1}: min_concentration cannot be negative")

        if max_conc <= min_conc:
            errors.append(
                f"Ingredient {i+1}: max_concentration must be > min_concentration"
            )

    return errors


def _validate_questionnaire_config(protocol: Dict[str, Any]) -> List[str]:
    """Validate questionnaire configuration structure."""
    errors = []

    # Check if either questionnaire or questionnaire_type is present
    has_questionnaire = "questionnaire" in protocol
    has_questionnaire_type = "questionnaire_type" in protocol

    if not has_questionnaire and not has_questionnaire_type:
        errors.append("Protocol must have either 'questionnaire' object or 'questionnaire_type' string")
        return errors

    # Validate inline questionnaire if present
    if has_questionnaire:
        questionnaire = protocol["questionnaire"]

        if not isinstance(questionnaire, dict):
            errors.append("Questionnaire must be an object")
            return errors

        # Validate questions array
        if "questions" not in questionnaire or not questionnaire["questions"]:
            errors.append("Questionnaire must have at least one question")
            return errors

        question_ids = set()
        for idx, question in enumerate(questionnaire["questions"]):
            q_id = question.get("id")
            if not q_id:
                errors.append(f"Question {idx} missing 'id' field")
                continue

            if q_id in question_ids:
                errors.append(f"Duplicate question id: {q_id}")
            question_ids.add(q_id)

            # Type-specific validation
            q_type = question.get("type")
            if not q_type:
                errors.append(f"Question '{q_id}' missing 'type' field")
                continue

            if q_type == "slider":
                if "min" not in question or "max" not in question:
                    errors.append(f"Slider question '{q_id}' missing min/max")
                elif question["min"] >= question["max"]:
                    errors.append(f"Slider question '{q_id}': min must be < max")

            elif q_type == "dropdown":
                if "options" not in question or not question["options"]:
                    errors.append(f"Dropdown question '{q_id}' missing options")

        # Validate bayesian_target
        if "bayesian_target" not in questionnaire:
            errors.append("Questionnaire missing 'bayesian_target' configuration")
        else:
            target = questionnaire["bayesian_target"]
            target_var = target.get("variable")

            if not target_var:
                errors.append("bayesian_target missing 'variable' field")
            elif target_var != "composite" and target_var not in question_ids:
                errors.append(f"bayesian_target references unknown question: {target_var}")

            if "higher_is_better" not in target:
                errors.append("bayesian_target missing 'higher_is_better' field")

    # Validate legacy questionnaire_type if present (and no inline questionnaire)
    elif has_questionnaire_type:
        q_type = protocol["questionnaire_type"]
        if q_type not in VALIDATION_RULES["valid_questionnaire_types"]:
            errors.append(f"Invalid questionnaire type: {q_type}")

    return errors


def _validate_bo_config(protocol: Dict[str, Any]) -> List[str]:
    """Validate Bayesian Optimization configuration."""
    errors = []

    # Check if any schedule entry uses BO
    schedule = protocol.get("sample_selection_schedule", [])
    uses_bo = any(entry.get("mode") == "bo_selected" for entry in schedule)

    if not uses_bo:
        return errors  # BO config not required if not using BO mode

    bo_config = protocol.get("bayesian_optimization", {})

    if not bo_config:
        errors.append(
            "Bayesian optimization config required when using bo_selected mode"
        )
        return errors

    # Validate acquisition function
    acq_func = bo_config.get("acquisition_function", "ei")
    if acq_func not in VALIDATION_RULES["valid_acquisition_functions"]:
        errors.append(f"Invalid acquisition function: {acq_func}")

    # Validate kernel nu
    kernel_nu = bo_config.get("kernel_nu", 2.5)
    if kernel_nu not in VALIDATION_RULES["valid_kernel_nu"]:
        errors.append(f"Invalid kernel_nu: {kernel_nu} (must be 0.5, 1.5, 2.5, or inf)")

    # Validate min_samples_for_bo
    min_samples = bo_config.get("min_samples_for_bo", 3)
    if min_samples < 2:
        errors.append("min_samples_for_bo must be >= 2")

    # Validate alpha (noise parameter)
    alpha = bo_config.get("alpha", 1e-3)
    if alpha <= 0 or alpha > 1:
        errors.append(f"alpha must be in range (0, 1], got {alpha}")

    return errors


def _validate_stopping_criteria(protocol: Dict[str, Any]) -> List[str]:
    """Validate stopping criteria configuration."""
    errors = []

    criteria = protocol.get("stopping_criteria", {})

    if not criteria:
        return errors  # Stopping criteria is optional

    # Validate min/max cycles
    min_cycles = criteria.get("min_cycles")
    max_cycles = criteria.get("max_cycles")

    if min_cycles is not None and min_cycles < VALIDATION_RULES["min_cycles"]:
        errors.append(f"min_cycles must be >= {VALIDATION_RULES['min_cycles']}")

    if max_cycles is not None and max_cycles > VALIDATION_RULES["max_cycles"]:
        errors.append(f"max_cycles must be <= {VALIDATION_RULES['max_cycles']}")

    if min_cycles is not None and max_cycles is not None and min_cycles > max_cycles:
        errors.append(
            f"min_cycles ({min_cycles}) cannot be > max_cycles ({max_cycles})"
        )

    return errors


def _validate_phase_sequence(protocol: Dict[str, Any]) -> List[str]:
    """
    Validate phase sequence configuration.

    Checks:
    - All phase_ids are valid
    - Required fields are present
    - Auto-advance has duration_ms
    - Duration values are positive
    - Phase types are valid
    - Completion phase is present

    Args:
        protocol: Protocol dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Extract phase_sequence (optional field)
    phase_sequence_config = protocol.get("phase_sequence")

    if not phase_sequence_config:
        return []  # No custom sequence = valid (uses default)

    # Handle both dict with 'phases' key and direct list
    if isinstance(phase_sequence_config, dict):
        phases_list = phase_sequence_config.get("phases", [])
    elif isinstance(phase_sequence_config, list):
        phases_list = phase_sequence_config
    else:
        errors.append("phase_sequence must be a dict or list")
        return errors

    if not phases_list:
        return []  # Empty sequence = valid (uses default)

    # Valid phase IDs for builtin phases
    valid_builtin_ids = {
        "waiting",
        "consent",
        "registration",
        "instructions",
        "robot_preparing",
        "loading",
        "questionnaire",
        "selection",
        "completion",
        "complete",  # Alternative name
        "experiment_loop",
    }

    # Valid phase types
    valid_phase_types = {"builtin", "custom", "loop"}

    # Track phase_ids for uniqueness check
    phase_ids = []

    # Validate each phase
    for idx, phase in enumerate(phases_list):
        if not isinstance(phase, dict):
            errors.append(f"Phase {idx}: must be a dictionary")
            continue

        phase_id = phase.get("phase_id")
        phase_type = phase.get("phase_type")

        # Required fields
        if not phase_id:
            errors.append(f"Phase {idx}: Missing phase_id")
        else:
            phase_ids.append(phase_id)

        if not phase_type:
            errors.append(f"Phase {idx}: Missing phase_type")

        # Valid phase_type
        if phase_type and phase_type not in valid_phase_types:
            errors.append(
                f"Phase {phase_id or idx}: Invalid phase_type '{phase_type}' "
                f"(must be one of: {', '.join(valid_phase_types)})"
            )

        # Builtin phase validation
        if phase_type == "builtin" and phase_id:
            if phase_id not in valid_builtin_ids:
                errors.append(
                    f"Phase {idx}: Invalid builtin phase_id '{phase_id}' "
                    f"(must be one of: {', '.join(sorted(valid_builtin_ids))})"
                )

        # Auto-advance validation
        if phase.get("auto_advance"):
            duration_ms = phase.get("duration_ms")
            if not duration_ms:
                errors.append(
                    f"Phase {phase_id or idx}: auto_advance=True requires duration_ms"
                )
            elif duration_ms <= 0:
                errors.append(
                    f"Phase {phase_id or idx}: duration_ms must be positive, got {duration_ms}"
                )

        # Duration validation (even without auto_advance)
        duration_ms = phase.get("duration_ms")
        if duration_ms is not None and duration_ms <= 0:
            errors.append(
                f"Phase {phase_id or idx}: duration_ms must be positive, got {duration_ms}"
            )

        # Loop phase validation
        if phase_type == "loop" and not phase.get("loop_config"):
            logger.warning(
                f"Phase {phase_id or idx}: loop type typically has loop_config"
            )

    # Check for duplicate phase_ids
    duplicates = [pid for pid in set(phase_ids) if phase_ids.count(pid) > 1]
    if duplicates:
        errors.append(f"Duplicate phase_ids found: {', '.join(duplicates)}")

    # Required completion phase
    completion_aliases = {"completion", "complete"}
    has_completion = any(pid in completion_aliases for pid in phase_ids)
    if not has_completion:
        errors.append(
            "Phase sequence must include a 'completion' or 'complete' phase"
        )

    return errors


def _validate_pump_rate_for_syringe(pumps: List[Dict[str, Any]], dispensing_rate_ul_min: float) -> List[str]:
    """
    Validate dispensing rate is within limits for each pump's syringe diameter.
    
    Uses NE-4000 rate limits from user manual Table 11.7.
    
    Args:
        pumps: List of pump configuration dictionaries
        dispensing_rate_ul_min: Requested rate in µL/min
        
    Returns:
        List of error messages (empty if all valid)
    """
    errors = []
    
    # Convert rate to mL/min for comparison
    rate_ml_min = dispensing_rate_ul_min / 1000.0
    
    # NE-4000 rate limits by syringe diameter (from manual Table 11.7, B-D syringes)
    # Format: (diameter_mm, max_rate_ml_min)
    BD_SYRINGE_RATE_TABLE = [
        (4.699, 3.135),    # 1mL BD syringe
        (8.585, 10.46),    # 3mL BD
        (11.99, 20.41),    # 5mL BD
        (14.43, 29.56),    # 10mL BD
        (19.05, 51.53),    # 20mL BD
        (21.59, 66.19),    # 30mL BD
        (26.59, 100.3),    # 60mL BD
    ]
    
    def get_max_rate_for_diameter(diameter_mm: float) -> float:
        """Get max rate (mL/min) for a syringe diameter."""
        for i, (d, rate) in enumerate(BD_SYRINGE_RATE_TABLE):
            if diameter_mm <= d:
                if i == 0:
                    return rate
                # Linear interpolation
                prev_d, prev_rate = BD_SYRINGE_RATE_TABLE[i - 1]
                ratio = (diameter_mm - prev_d) / (d - prev_d)
                return prev_rate + ratio * (rate - prev_rate)
        # Above largest diameter
        return min(95.0, BD_SYRINGE_RATE_TABLE[-1][1])
    
    for i, pump in enumerate(pumps):
        pump_num = i + 1
        diameter = pump.get("syringe_diameter_mm")
        ingredient = pump.get("ingredient", f"Pump {pump_num}")
        
        if diameter is None:
            continue  # Already validated elsewhere
            
        max_rate = get_max_rate_for_diameter(diameter)
        
        if rate_ml_min > max_rate:
            errors.append(
                f"Pump {pump_num} ({ingredient}): Dispensing rate {rate_ml_min:.1f} mL/min "
                f"exceeds maximum {max_rate:.1f} mL/min for {diameter:.2f}mm diameter syringe. "
                f"Reduce dispensing_rate_ul_min to {int(max_rate * 1000)} or less."
            )
    
    return errors


def _validate_pump_config(protocol: Dict[str, Any]) -> List[str]:
    """
    Validate pump configuration.

    Checks:
    - Serial port is specified if pumps enabled
    - Baud rate is valid
    - Pump addresses are unique and in valid range
    - Each pump ingredient matches protocol ingredients
    - Syringe diameters are within valid range
    - All protocol ingredients have pump mappings (if enabled)

    Args:
        protocol: Protocol dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors = []

    # Get pump configuration (optional field)
    pump_config = protocol.get("pump_config", {})

    if not pump_config or not pump_config.get("enabled", False):
        return []  # Pump control disabled = valid

    # Validate serial port
    serial_port = pump_config.get("serial_port", "").strip()
    if not serial_port:
        errors.append("Pump config: serial_port must be specified when pumps are enabled")

    # Validate baud rate
    baud_rate = pump_config.get("baud_rate", 19200)
    valid_baud_rates = [300, 1200, 2400, 9600, 19200]
    if baud_rate not in valid_baud_rates:
        errors.append(f"Pump config: invalid baud_rate {baud_rate}, must be one of {valid_baud_rates}")

    # Validate pumps list
    pumps = pump_config.get("pumps", [])
    if not pumps:
        errors.append("Pump config: at least one pump must be configured when pumps are enabled")
        return errors

    # Get protocol ingredients for validation
    protocol_ingredients = [ing.get("name") for ing in protocol.get("ingredients", [])]

    # Track pump addresses for uniqueness check
    pump_addresses = []
    pump_ingredients = []

    for i, pump in enumerate(pumps):
        pump_num = i + 1

        # Validate required fields
        if "address" not in pump:
            errors.append(f"Pump {pump_num}: missing 'address' field")
            continue

        if "ingredient" not in pump:
            errors.append(f"Pump {pump_num}: missing 'ingredient' field")
            continue

        if "syringe_diameter_mm" not in pump:
            errors.append(f"Pump {pump_num}: missing 'syringe_diameter_mm' field")
            continue

        # Validate address
        address = pump["address"]
        if not isinstance(address, int) or not (0 <= address <= 99):
            errors.append(f"Pump {pump_num}: address must be an integer between 0 and 99, got {address}")
        else:
            if address in pump_addresses:
                errors.append(f"Pump {pump_num}: duplicate address {address}")
            else:
                pump_addresses.append(address)

        # Validate ingredient
        ingredient = pump["ingredient"]
        if ingredient not in protocol_ingredients:
            errors.append(f"Pump {pump_num}: ingredient '{ingredient}' not found in protocol ingredients")
        else:
            if ingredient in pump_ingredients:
                errors.append(f"Pump {pump_num}: duplicate mapping for ingredient '{ingredient}'")
            else:
                pump_ingredients.append(ingredient)

        # Validate syringe diameter
        diameter = pump.get("syringe_diameter_mm")
        if not isinstance(diameter, (int, float)) or not (0.1 <= diameter <= 50.0):
            errors.append(f"Pump {pump_num}: syringe_diameter_mm must be between 0.1 and 50.0 mm, got {diameter}")

        # Validate max rate (optional)
        max_rate = pump.get("max_rate_ul_min")
        if max_rate is not None and (not isinstance(max_rate, (int, float)) or max_rate <= 0):
            errors.append(f"Pump {pump_num}: max_rate_ul_min must be positive, got {max_rate}")

        # Validate volume unit (optional)
        volume_unit = pump.get("volume_unit", "ML")
        if volume_unit not in ["ML", "UL"]:
            errors.append(
                f"Pump {pump_num}: volume_unit must be 'ML' or 'UL', got {volume_unit}"
            )

        # Validate stock concentration (optional)
        stock_conc = pump.get("stock_concentration_mM")
        if stock_conc is not None and (not isinstance(stock_conc, (int, float)) or stock_conc < 0):
            errors.append(f"Pump {pump_num}: stock_concentration_mM must be non-negative, got {stock_conc}")

    # Check if all ingredients have pump mappings
    unmapped_ingredients = set(protocol_ingredients) - set(pump_ingredients)
    if unmapped_ingredients:
        errors.append(f"Pump config: the following ingredients have no pump mapping: {', '.join(sorted(unmapped_ingredients))}")

    # Validate total volume
    total_volume = pump_config.get("total_volume_ml")
    if total_volume is not None:
        if not isinstance(total_volume, (int, float)) or not (0.1 <= total_volume <= 1000):
            errors.append(f"Pump config: total_volume_ml must be between 0.1 and 1000 mL, got {total_volume}")

    # Validate dispensing rate
    dispensing_rate = pump_config.get("dispensing_rate_ul_min")
    if dispensing_rate is not None:
        if not isinstance(dispensing_rate, (int, float)) or dispensing_rate <= 0:
            errors.append(f"Pump config: dispensing_rate_ul_min must be positive, got {dispensing_rate}")
        else:
            # Validate rate against syringe diameter limits
            rate_errors = _validate_pump_rate_for_syringe(pumps, dispensing_rate)
            errors.extend(rate_errors)

    # Validate burst mode compatibility
    use_burst = pump_config.get("use_burst_mode", False)
    if use_burst:
        for i, pump_cfg in enumerate(pumps):
            address = pump_cfg.get("address")
            if address is None:
                errors.append(f"Pump {i+1}: Missing address (required for burst mode)")
            elif address > 9:
                errors.append(
                    f"Pump {i+1}: Address {address} exceeds burst mode limit (0-9). "
                    f"Either change address or disable burst mode."
                )

        # Warn if burst mode enabled but not using simultaneous dispensing
        if not pump_config.get("simultaneous_dispensing", False):
            # This is just a warning, not an error
            logger.warning(
                "Burst mode is enabled but simultaneous_dispensing is False. "
                "Burst mode only works with simultaneous dispensing."
            )

    return errors


def _validate_compatibility(protocol: Dict[str, Any]) -> List[str]:
    """Check protocol version compatibility (warnings only)."""
    warnings = []

    protocol_schema_version = protocol.get("schema_version", "1.0")
    current_schema_version = "1.0"

    if protocol_schema_version != current_schema_version:
        warnings.append(
            f"Protocol uses schema version {protocol_schema_version}, current is {current_schema_version}"
        )

    return warnings


# =============================================================================
# Protocol Import/Export
# =============================================================================


def export_protocol_to_file(protocol: Dict[str, Any], file_path: str) -> bool:
    """
    Export protocol to JSON file.

    Args:
        protocol: Protocol dictionary
        file_path: Path to save JSON file

    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate before export
        is_valid, errors = validate_protocol(protocol)
        if not is_valid:
            logger.error(f"Cannot export invalid protocol: {errors}")
            return False

        # Write to file
        with open(file_path, "w") as f:
            json.dump(protocol, f, indent=2, sort_keys=False)

        logger.info(f"Exported protocol '{protocol['name']}' to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Failed to export protocol: {e}")
        return False


def import_protocol_from_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Import protocol from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        Protocol dictionary if valid, None otherwise
    """
    try:
        # Read file
        with open(file_path, "r") as f:
            protocol = json.load(f)

        # Validate
        is_valid, errors = validate_protocol(protocol)
        if not is_valid:
            logger.error(f"Invalid protocol file: {errors}")
            return None

        # Generate new ID and timestamp for imported protocol
        protocol["protocol_id"] = f"proto_{uuid.uuid4().hex[:12]}"
        protocol["created_at"] = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Imported protocol '{protocol['name']}' from {file_path}")
        return protocol

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in protocol file: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to import protocol: {e}")
        return None


def export_protocol_to_json_string(protocol: Dict[str, Any]) -> Optional[str]:
    """
    Export protocol to JSON string for database storage.

    Args:
        protocol: Protocol dictionary

    Returns:
        JSON string if valid, None otherwise
    """
    try:
        # Validate before export
        is_valid, errors = validate_protocol(protocol)
        if not is_valid:
            logger.error(f"Cannot export invalid protocol: {errors}")
            return None

        # Compute hash
        protocol["protocol_hash"] = compute_protocol_hash(protocol)

        return protocol_to_json(protocol)

    except Exception as e:
        logger.error(f"Failed to convert protocol to JSON: {e}")
        return None


def import_protocol_from_json_string(json_str: str) -> Optional[Dict[str, Any]]:
    """
    Import protocol from JSON string.

    Args:
        json_str: JSON string

    Returns:
        Protocol dictionary if valid, None otherwise
    """
    try:
        protocol = protocol_from_json(json_str)

        # Validate
        is_valid, errors = validate_protocol(protocol)
        if not is_valid:
            logger.error(f"Invalid protocol JSON: {errors}")
            return None

        return protocol

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to parse protocol JSON: {e}")
        return None


# =============================================================================
# Protocol Queries & Utilities
# =============================================================================


def get_protocol_summary(protocol: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of a protocol.

    Args:
        protocol: Protocol dictionary

    Returns:
        Multi-line summary string
    """
    lines = []

    lines.append(f"Protocol: {protocol.get('name', 'Unnamed')}")
    lines.append(f"Version: {protocol.get('version', 'Unknown')}")

    if protocol.get("description"):
        lines.append(f"Description: {protocol['description']}")

    # Ingredients
    ingredients = protocol.get("ingredients", [])
    lines.append(f"\nIngredients ({len(ingredients)}):")
    for ing in ingredients:
        name = ing.get("name", "Unknown")
        min_c = ing.get("min_concentration", 0)
        max_c = ing.get("max_concentration", 0)
        unit = ing.get("unit", "mM")
        lines.append(f"  - {name}: {min_c}-{max_c} {unit}")

    # Sample selection schedule
    schedule = protocol.get("sample_selection_schedule", [])
    lines.append(f"\nSample Selection Schedule ({len(schedule)} phases):")
    for entry in schedule:
        cycle_range = entry.get("cycle_range", {})
        start = cycle_range.get("start", "?")
        end = cycle_range.get("end", "?")
        mode = entry.get("mode", "unknown")
        lines.append(f"  - Cycles {start}-{end}: {mode}")

    # Questionnaire
    q_type = protocol.get("questionnaire_type", "Unknown")
    lines.append(f"\nQuestionnaire: {q_type}")

    # Stopping criteria
    criteria = protocol.get("stopping_criteria", {})
    if criteria:
        min_c = criteria.get("min_cycles", "?")
        max_c = criteria.get("max_cycles", "?")
        lines.append(f"\nStopping: {min_c}-{max_c} cycles")

    return "\n".join(lines)


# =============================================================================
# Protocol Versioning
# =============================================================================


def increment_protocol_version(protocol: Dict[str, Any], major_increment: bool = False) -> Dict[str, Any]:
    """
    Create a new version of a protocol with incremented version number.

    Args:
        protocol: Existing protocol dictionary
        major_increment: If True, increment major version (1.9 → 2.0).
                        If False, increment minor version (1.0 → 1.1)

    Returns:
        New protocol with incremented version, new ID, and new hash

    Example:
        >>> old_protocol = {"protocol_id": "abc", "name": "Test", "version": "1.0", ...}
        >>> new_protocol = increment_protocol_version(old_protocol)
        >>> new_protocol['version']
        '1.1'
        >>> new_protocol['protocol_id'] != old_protocol['protocol_id']
        True
    """
    import copy
    import uuid
    from datetime import datetime

    new_protocol = copy.deepcopy(protocol)

    # Parse current version
    try:
        version_parts = protocol.get('version', '1.0').split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
    except (ValueError, IndexError):
        logger.warning(f"Invalid version format: {protocol.get('version')}, defaulting to 1.0")
        major, minor = 1, 0

    # Increment version
    if major_increment:
        new_version = f"{major + 1}.0"
    else:
        new_version = f"{major}.{minor + 1}"

    new_protocol['version'] = new_version

    # Generate new ID and hash
    new_protocol['protocol_id'] = str(uuid.uuid4())
    new_protocol['protocol_hash'] = compute_protocol_hash(new_protocol)

    # Update metadata
    now = datetime.utcnow().isoformat()
    new_protocol['created_at'] = now
    new_protocol['updated_at'] = now

    # Add provenance metadata
    new_protocol['derived_from'] = protocol.get('protocol_id')

    logger.info(f"Incremented protocol version: {protocol.get('version')} → {new_version}")
    return new_protocol


def compare_protocols(protocol_v1: Dict[str, Any], protocol_v2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two protocol versions and return differences.

    Args:
        protocol_v1: First protocol (baseline)
        protocol_v2: Second protocol (comparison)

    Returns:
        Dictionary with:
        {
            "ingredients_changed": bool,
            "schedule_changed": bool,
            "questionnaire_changed": bool,
            "bo_config_changed": bool,
            "stopping_criteria_changed": bool,
            "differences": List[str]  # Human-readable descriptions
        }

    Example:
        >>> v1 = {"name": "Test", "version": "1.0", "ingredients": [{"name": "Sugar"}]}
        >>> v2 = {"name": "Test", "version": "1.1", "ingredients": [{"name": "Salt"}]}
        >>> diff = compare_protocols(v1, v2)
        >>> diff['ingredients_changed']
        True
        >>> "Ingredients modified" in diff['differences']
        True
    """
    differences = []

    # Compare ingredients
    ingredients_changed = protocol_v1.get('ingredients') != protocol_v2.get('ingredients')
    if ingredients_changed:
        differences.append("Ingredients modified")

    # Compare sample selection schedule
    schedule_changed = protocol_v1.get('sample_selection_schedule') != protocol_v2.get('sample_selection_schedule')
    if schedule_changed:
        differences.append("Sample selection schedule modified")

    # Compare questionnaire type
    questionnaire_changed = protocol_v1.get('questionnaire_type') != protocol_v2.get('questionnaire_type')
    if questionnaire_changed:
        differences.append("Questionnaire type changed")

    # Compare BO configuration
    bo_config_changed = protocol_v1.get('bayesian_optimization') != protocol_v2.get('bayesian_optimization')
    if bo_config_changed:
        differences.append("Bayesian Optimization configuration modified")

    # Compare stopping criteria
    stopping_criteria_changed = protocol_v1.get('stopping_criteria') != protocol_v2.get('stopping_criteria')
    if stopping_criteria_changed:
        differences.append("Stopping criteria modified")

    # Compare metadata
    if protocol_v1.get('name') != protocol_v2.get('name'):
        differences.append(f"Name changed: '{protocol_v1.get('name')}' → '{protocol_v2.get('name')}'")

    if protocol_v1.get('description') != protocol_v2.get('description'):
        differences.append("Description modified")

    if protocol_v1.get('tags') != protocol_v2.get('tags'):
        differences.append("Tags modified")

    return {
        "ingredients_changed": ingredients_changed,
        "schedule_changed": schedule_changed,
        "questionnaire_changed": questionnaire_changed,
        "bo_config_changed": bo_config_changed,
        "stopping_criteria_changed": stopping_criteria_changed,
        "differences": differences,
        "total_changes": len(differences)
    }


def export_protocol_to_clipboard(protocol: Dict[str, Any]) -> str:
    """
    Generate shareable JSON string for clipboard export.

    Removes internal metadata fields (protocol_id, created_at, etc.) to create
    a clean protocol that can be imported elsewhere.

    Args:
        protocol: Protocol dictionary

    Returns:
        Clean JSON string suitable for clipboard export

    Example:
        >>> protocol = {"protocol_id": "abc", "name": "Test", "created_at": "2026-01-01", ...}
        >>> json_str = export_protocol_to_clipboard(protocol)
        >>> "protocol_id" in json_str
        False
        >>> "name" in json_str
        True
    """
    import copy

    clean_protocol = copy.deepcopy(protocol)

    # Remove internal metadata that shouldn't be exported
    internal_fields = [
        'protocol_id',
        'created_at',
        'updated_at',
        'protocol_hash',
        'is_archived',
        'deleted_at',
        'created_by',
        'derived_from'
    ]

    for field in internal_fields:
        clean_protocol.pop(field, None)

    # Export to formatted JSON
    return json.dumps(clean_protocol, indent=2, ensure_ascii=False)


# Export key functions for easier imports
__all__ = [
    "create_protocol",
    "clone_protocol",
    "validate_protocol",
    "export_protocol_to_file",
    "import_protocol_from_file",
    "export_protocol_to_json_string",
    "import_protocol_from_json_string",
    "compute_protocol_hash",
    "get_protocol_summary",
    "get_selection_mode_for_cycle",
    "get_predetermined_sample",
    "increment_protocol_version",
    "compare_protocols",
    "export_protocol_to_clipboard",
    "ProtocolValidationError",
]
