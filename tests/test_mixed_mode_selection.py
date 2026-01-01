"""
Unit tests for mixed-mode sample selection (Week 3-4 implementation).

Tests the three selection modes:
- user_selected
- bo_selected
- predetermined
"""

import pytest
import json
from robotaste.config.protocol_schema import (
    get_selection_mode_for_cycle,
    get_predetermined_sample,
    EXAMPLE_PROTOCOL_MIXED_MODE
)


def test_selection_mode_determination():
    """Test that selection mode is correctly determined from protocol."""
    protocol = EXAMPLE_PROTOCOL_MIXED_MODE

    # Cycle 1-2: predetermined
    assert get_selection_mode_for_cycle(protocol, 1) == "predetermined"
    assert get_selection_mode_for_cycle(protocol, 2) == "predetermined"

    # Cycle 3-5: user_selected
    assert get_selection_mode_for_cycle(protocol, 3) == "user_selected"
    assert get_selection_mode_for_cycle(protocol, 4) == "user_selected"
    assert get_selection_mode_for_cycle(protocol, 5) == "user_selected"

    # Cycle 6-15: bo_selected
    assert get_selection_mode_for_cycle(protocol, 6) == "bo_selected"
    assert get_selection_mode_for_cycle(protocol, 10) == "bo_selected"
    assert get_selection_mode_for_cycle(protocol, 15) == "bo_selected"

    # Cycle beyond schedule: fallback to user_selected
    assert get_selection_mode_for_cycle(protocol, 16) == "user_selected"
    assert get_selection_mode_for_cycle(protocol, 100) == "user_selected"


def test_predetermined_sample_retrieval():
    """Test that predetermined samples are correctly retrieved."""
    protocol = EXAMPLE_PROTOCOL_MIXED_MODE

    # Cycle 1: should have predetermined sample
    sample1 = get_predetermined_sample(protocol, 1)
    assert sample1 is not None
    assert "Sugar" in sample1
    assert "Salt" in sample1
    assert sample1["Sugar"] == 10.0
    assert sample1["Salt"] == 2.0

    # Cycle 2: should have predetermined sample
    sample2 = get_predetermined_sample(protocol, 2)
    assert sample2 is not None
    assert sample2["Sugar"] == 40.0
    assert sample2["Salt"] == 6.0

    # Cycle 3: user_selected mode, no predetermined sample
    sample3 = get_predetermined_sample(protocol, 3)
    assert sample3 is None

    # Cycle 6: bo_selected mode, no predetermined sample
    sample6 = get_predetermined_sample(protocol, 6)
    assert sample6 is None


def test_protocol_validation():
    """Test that protocol validation catches errors in sample selection schedule."""
    from robotaste.config.protocols import validate_protocol

    # Valid protocol
    is_valid, errors = validate_protocol(EXAMPLE_PROTOCOL_MIXED_MODE)
    assert is_valid, f"Example protocol should be valid, but got errors: {errors}"
    assert len(errors) == 0

    # Test invalid protocol: missing predetermined samples
    invalid_protocol = {
        **EXAMPLE_PROTOCOL_MIXED_MODE,
        "sample_selection_schedule": [
            {
                "cycle_range": {"start": 1, "end": 3},
                "mode": "predetermined",
                # Missing predetermined_samples!
            }
        ]
    }

    is_valid, errors = validate_protocol(invalid_protocol)
    assert not is_valid
    assert any("predetermined" in err.lower() for err in errors)


def test_selection_mode_fallback():
    """Test fallback behavior when protocol has no schedule."""
    empty_protocol = {
        "protocol_id": "test_001",
        "name": "Empty Protocol",
        "version": "1.0",
        "ingredients": [{"name": "Sugar", "min_concentration": 0, "max_concentration": 100}],
        "sample_selection_schedule": [],
        "questionnaire_type": "hedonic_continuous"
    }

    # Should default to user_selected
    assert get_selection_mode_for_cycle(empty_protocol, 1) == "user_selected"
    assert get_selection_mode_for_cycle(empty_protocol, 10) == "user_selected"


def test_cycle_range_overlap_validation():
    """Test that overlapping cycle ranges are caught by validation."""
    from robotaste.config.protocols import validate_protocol

    overlapping_protocol = {
        **EXAMPLE_PROTOCOL_MIXED_MODE,
        "sample_selection_schedule": [
            {
                "cycle_range": {"start": 1, "end": 5},
                "mode": "user_selected"
            },
            {
                "cycle_range": {"start": 3, "end": 8},  # Overlaps with previous!
                "mode": "bo_selected"
            }
        ]
    }

    is_valid, errors = validate_protocol(overlapping_protocol)
    assert not is_valid
    assert any("overlap" in err.lower() or "already covered" in err.lower() for err in errors)


def test_invalid_mode_validation():
    """Test that invalid selection modes are rejected."""
    from robotaste.config.protocols import validate_protocol

    invalid_mode_protocol = {
        **EXAMPLE_PROTOCOL_MIXED_MODE,
        "sample_selection_schedule": [
            {
                "cycle_range": {"start": 1, "end": 5},
                "mode": "invalid_mode"  # Not in ["user_selected", "bo_selected", "predetermined"]
            }
        ]
    }

    is_valid, errors = validate_protocol(invalid_mode_protocol)
    assert not is_valid
    assert any("invalid mode" in err.lower() for err in errors)


def test_bo_config_validation_when_using_bo_mode():
    """Test that BO config is validated when using bo_selected mode."""
    from robotaste.config.protocols import validate_protocol

    # Protocol with bo_selected mode but no BO config
    no_bo_config_protocol = {
        **EXAMPLE_PROTOCOL_MIXED_MODE,
        "sample_selection_schedule": [
            {
                "cycle_range": {"start": 1, "end": 10},
                "mode": "bo_selected"
            }
        ],
        "bayesian_optimization": {}  # Empty BO config
    }

    is_valid, errors = validate_protocol(no_bo_config_protocol)
    assert not is_valid
    assert any("bayesian optimization" in err.lower() for err in errors)


if __name__ == "__main__":
    # Run tests manually
    print("Running mixed-mode selection tests...")

    test_selection_mode_determination()
    print("✓ Selection mode determination test passed")

    test_predetermined_sample_retrieval()
    print("✓ Predetermined sample retrieval test passed")

    test_protocol_validation()
    print("✓ Protocol validation test passed")

    test_selection_mode_fallback()
    print("✓ Selection mode fallback test passed")

    test_cycle_range_overlap_validation()
    print("✓ Cycle range overlap validation test passed")

    test_invalid_mode_validation()
    print("✓ Invalid mode validation test passed")

    test_bo_config_validation_when_using_bo_mode()
    print("✓ BO config validation test passed")

    print("\nAll tests passed! ✓")
