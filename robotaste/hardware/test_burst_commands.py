"""
Unit tests for Network Command Burst functionality.

Tests the BurstCommandBuilder class and burst command generation.
"""

import pytest
from robotaste.hardware.pump_controller import BurstCommandBuilder, PumpBurstConfig


def test_burst_command_builder_two_pumps():
    """Test burst command generation matches manual example."""
    configs = [
        PumpBurstConfig(
            address=0,
            rate_ul_min=60000,
            volume_ul=3000,
            diameter_mm=29.0,
            direction="INF",
        ),
        PumpBurstConfig(
            address=1,
            rate_ul_min=30000,
            volume_ul=1000,
            diameter_mm=29.0,
            direction="INF",
        ),
    ]

    commands = BurstCommandBuilder.build_burst_commands(configs)

    # Verify structure (exact format may vary based on auto-conversion)
    assert "0 RAT" in commands.config_command
    assert "1 RAT" in commands.config_command
    assert "0 VOL" in commands.config_command
    assert "1 VOL" in commands.config_command
    assert "0 DIR INF" in commands.config_command
    assert "1 DIR INF" in commands.config_command

    assert "0 RAT *" in commands.validation_command
    assert "1 RAT *" in commands.validation_command
    assert "0 VOL *" in commands.validation_command
    assert "1 VOL *" in commands.validation_command

    assert "0 RUN *" in commands.run_command
    assert "1 RUN *" in commands.run_command


def test_burst_command_builder_single_pump():
    """Test burst command generation with single pump."""
    configs = [
        PumpBurstConfig(
            address=5,
            rate_ul_min=1000,
            volume_ul=500,
            diameter_mm=29.0,
            direction="WDR",
        ),
    ]

    commands = BurstCommandBuilder.build_burst_commands(configs)

    # Verify structure
    assert "5 RAT" in commands.config_command
    assert "5 VOL" in commands.config_command
    assert "5 DIR WDR" in commands.config_command

    assert "5 RAT *" in commands.validation_command
    assert "5 VOL *" in commands.validation_command

    assert "5 RUN *" in commands.run_command


def test_burst_command_builder_three_pumps():
    """Test burst command generation with three pumps."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=100, diameter_mm=29.0),
        PumpBurstConfig(address=1, rate_ul_min=2000, volume_ul=200, diameter_mm=29.0),
        PumpBurstConfig(address=2, rate_ul_min=3000, volume_ul=300, diameter_mm=29.0),
    ]

    commands = BurstCommandBuilder.build_burst_commands(configs)

    # Verify all three pumps are in commands
    for addr in [0, 1, 2]:
        assert f"{addr} RAT" in commands.config_command
        assert f"{addr} VOL" in commands.config_command
        assert f"{addr} DIR INF" in commands.config_command
        assert f"{addr} RAT *" in commands.validation_command
        assert f"{addr} VOL *" in commands.validation_command
        assert f"{addr} RUN *" in commands.run_command


def test_burst_validation_address_out_of_range():
    """Test that addresses > 9 are rejected."""
    configs = [
        PumpBurstConfig(address=10, rate_ul_min=1000, volume_ul=100, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="address.*out of range"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_validation_address_negative():
    """Test that negative addresses are rejected."""
    configs = [
        PumpBurstConfig(address=-1, rate_ul_min=1000, volume_ul=100, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="address.*out of range"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_validation_duplicate_addresses():
    """Test that duplicate addresses are rejected."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=100, diameter_mm=29.0),
        PumpBurstConfig(address=0, rate_ul_min=2000, volume_ul=200, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="Duplicate"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_validation_zero_rate():
    """Test that zero rate is rejected."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=0, volume_ul=100, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="Rate must be positive"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_validation_negative_rate():
    """Test that negative rate is rejected."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=-1000, volume_ul=100, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="Rate must be positive"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_validation_zero_volume():
    """Test that zero volume is rejected."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=0, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="Volume must be positive"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_validation_negative_volume():
    """Test that negative volume is rejected."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=-100, diameter_mm=29.0),
    ]

    with pytest.raises(ValueError, match="Volume must be positive"):
        BurstCommandBuilder.build_burst_commands(configs)


def test_burst_command_format_with_asterisks():
    """Test that all commands end with proper asterisk separators."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=100, diameter_mm=29.0),
        PumpBurstConfig(address=1, rate_ul_min=2000, volume_ul=200, diameter_mm=29.0),
    ]

    commands = BurstCommandBuilder.build_burst_commands(configs)

    # All commands should end with " *"
    assert commands.config_command.endswith(" *")
    assert commands.validation_command.endswith(" *")
    assert commands.run_command.endswith(" *")

    # Commands should contain " * " as separators
    assert " * " in commands.config_command
    assert " * " in commands.validation_command
    assert " * " in commands.run_command


def test_burst_command_volume_conversion():
    """Test that volumes are properly converted from µL to mL."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=3000, diameter_mm=29.0),
    ]

    commands = BurstCommandBuilder.build_burst_commands(configs)

    # Volume should be converted to mL with proper formatting
    assert "0 VOL 3.000" in commands.config_command or "0 VOL 3.0" in commands.config_command


def test_validate_burst_config_valid():
    """Test that valid configurations pass validation."""
    configs = [
        PumpBurstConfig(address=0, rate_ul_min=1000, volume_ul=100, diameter_mm=29.0),
        PumpBurstConfig(address=5, rate_ul_min=2000, volume_ul=200, diameter_mm=29.0),
        PumpBurstConfig(address=9, rate_ul_min=3000, volume_ul=300, diameter_mm=29.0),
    ]

    errors = BurstCommandBuilder.validate_burst_config(configs)
    assert len(errors) == 0


def test_validate_burst_config_multiple_errors():
    """Test that multiple validation errors are all reported."""
    configs = [
        PumpBurstConfig(address=10, rate_ul_min=-1000, volume_ul=-100, diameter_mm=29.0),
        PumpBurstConfig(address=10, rate_ul_min=2000, volume_ul=200, diameter_mm=29.0),
    ]

    errors = BurstCommandBuilder.validate_burst_config(configs)

    # Should have multiple errors
    assert len(errors) >= 3  # At least: address out of range (x2), negative rate, negative volume, duplicate

    # Check specific errors are present
    error_text = " ".join(errors)
    assert "out of range" in error_text
    assert "Duplicate" in error_text
    assert "Rate must be positive" in error_text
    assert "Volume must be positive" in error_text
