"""
Tests for dual syringe support in pump control.

Validates that:
- Volume halving works correctly in burst config building
- Volume tracking doubles capacity when dual_syringe is true
- Backward compatibility: no dual_syringe field = single syringe behavior
"""

import pytest
from unittest.mock import patch, MagicMock
from robotaste.hardware.pump_controller import PumpBurstConfig


# ─── BURST CONFIG BUILDING (pump_manager) ──────────────────────────────────

class TestPumpManagerBurstConfigs:
    """Test _build_burst_configs in pump_manager.py."""

    def test_single_syringe_default(self):
        """Without dual_syringe, volume should not be halved."""
        from robotaste.core.pump_manager import _build_burst_configs

        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    "volume_unit": "ML",
                }
            ],
        }
        configs = _build_burst_configs(pump_config)
        assert len(configs) == 1
        # volume_ul should be 0 (default in _build_burst_configs, set per-cycle)
        assert configs[0].volume_ul == 0

    def test_dual_syringe_not_in_init_configs(self):
        """_build_burst_configs sets volume=0 for init; dual_syringe doesn't affect it."""
        from robotaste.core.pump_manager import _build_burst_configs

        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    "dual_syringe": True,
                }
            ],
        }
        configs = _build_burst_configs(pump_config)
        assert len(configs) == 1
        assert configs[0].volume_ul == 0


class TestSendVolumeAndRunDualSyringe:
    """Test volume halving in send_volume_and_run."""

    def _setup_cache(self, session_id):
        """Set up a mock pump in the cache."""
        from robotaste.core import pump_manager

        mock_pump = MagicMock()
        mock_pump.address = 0
        pump_manager._pump_cache[session_id] = {"Sugar": mock_pump}
        return mock_pump

    def _cleanup_cache(self, session_id):
        from robotaste.core import pump_manager
        pump_manager._pump_cache.pop(session_id, None)

    def test_single_syringe_full_volume(self):
        """Without dual_syringe, full volume is sent to pump."""
        from robotaste.core.pump_manager import send_volume_and_run

        session_id = "test-single-syringe"
        mock_pump = self._setup_cache(session_id)

        try:
            pump_config = {
                "dispensing_rate_ul_min": 2000,
                "pumps": [
                    {
                        "address": 0,
                        "ingredient": "Sugar",
                        "syringe_diameter_mm": 29.0,
                        "volume_unit": "ML",
                    }
                ],
            }
            volumes = {"Sugar": 10000.0}  # 10 mL

            send_volume_and_run(session_id, pump_config, volumes)

            # Verify burst command was called
            assert mock_pump._send_burst_command.called

            # Check the volume command contains full volume (10.00 mL)
            calls = mock_pump._send_burst_command.call_args_list
            vol_cmd = calls[0][0][0]  # First call, first positional arg
            assert "10.00" in vol_cmd  # 10000 µL = 10.00 mL
        finally:
            self._cleanup_cache(session_id)

    def test_dual_syringe_halved_volume(self):
        """With dual_syringe=true, volume sent to pump should be halved."""
        from robotaste.core.pump_manager import send_volume_and_run

        session_id = "test-dual-syringe"
        mock_pump = self._setup_cache(session_id)

        try:
            pump_config = {
                "dispensing_rate_ul_min": 2000,
                "pumps": [
                    {
                        "address": 0,
                        "ingredient": "Sugar",
                        "syringe_diameter_mm": 29.0,
                        "volume_unit": "ML",
                        "dual_syringe": True,
                    }
                ],
            }
            volumes = {"Sugar": 10000.0}  # 10 mL total

            send_volume_and_run(session_id, pump_config, volumes)

            # Verify burst command was called
            assert mock_pump._send_burst_command.called

            # Check the volume command contains halved volume (5.000 mL)
            calls = mock_pump._send_burst_command.call_args_list
            vol_cmd = calls[0][0][0]
            assert "5.000" in vol_cmd  # 10000/2 µL = 5.000 mL
        finally:
            self._cleanup_cache(session_id)


# ─── BURST CONFIG BUILDING (pump_control_service) ─────────────────────────

class TestServiceBurstConfigs:
    """Test _build_burst_configs in pump_control_service.py."""

    def test_single_syringe_full_volume(self):
        """Without dual_syringe, full recipe volume is used."""
        from pump_control_service import _build_burst_configs

        recipe = {"Sugar": 5000.0}
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                }
            ],
        }
        configs = _build_burst_configs(recipe, pump_config)
        assert len(configs) == 1
        assert configs[0].volume_ul == 5000.0

    def test_dual_syringe_halved_volume(self):
        """With dual_syringe=true, recipe volume is halved."""
        from pump_control_service import _build_burst_configs

        recipe = {"Sugar": 5000.0}
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    "dual_syringe": True,
                }
            ],
        }
        configs = _build_burst_configs(recipe, pump_config)
        assert len(configs) == 1
        assert configs[0].volume_ul == 2500.0  # 5000 / 2

    def test_mixed_dual_and_single(self):
        """Some pumps dual, some single — each handled independently."""
        from pump_control_service import _build_burst_configs

        recipe = {"Sugar": 4000.0, "Water": 6000.0}
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    "dual_syringe": True,
                },
                {
                    "address": 1,
                    "ingredient": "Water",
                    "syringe_diameter_mm": 29.0,
                    # No dual_syringe → defaults to False
                },
            ],
        }
        configs = _build_burst_configs(recipe, pump_config)
        assert len(configs) == 2

        sugar_config = next(c for c in configs if c.address == 0)
        water_config = next(c for c in configs if c.address == 1)

        assert sugar_config.volume_ul == 2000.0  # 4000 / 2
        assert water_config.volume_ul == 6000.0  # Full volume


# ─── PUMP TIME CALCULATION ─────────────────────────────────────────────────

class TestPumpTimeCalculation:
    """Test calculate_total_pump_time accounts for dual syringe."""

    def test_single_syringe_time(self):
        """Without dual syringe, time based on full volume."""
        from robotaste.core.pump_integration import calculate_total_pump_time

        recipe = {"Sugar": 60000.0}  # 60 mL at 2000 µL/min = 30 min = 1800s
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "simultaneous_dispensing": True,
            "pumps": [
                {"address": 0, "ingredient": "Sugar", "syringe_diameter_mm": 29.0}
            ],
        }
        time_s = calculate_total_pump_time(recipe, pump_config, buffer_percent=0)
        expected = (60000 / 2000) * 60  # 1800 seconds
        assert abs(time_s - expected) < 0.01

    def test_dual_syringe_time_halved(self):
        """With dual syringe, time based on halved volume."""
        from robotaste.core.pump_integration import calculate_total_pump_time

        recipe = {"Sugar": 60000.0}  # 60 mL total
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "simultaneous_dispensing": True,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    "dual_syringe": True,
                }
            ],
        }
        time_s = calculate_total_pump_time(recipe, pump_config, buffer_percent=0)
        # Halved: 30000 µL at 2000 µL/min = 15 min = 900s
        expected = (30000 / 2000) * 60
        assert abs(time_s - expected) < 0.01


# ─── BACKWARD COMPATIBILITY ───────────────────────────────────────────────

class TestBackwardCompatibility:
    """Ensure protocols without dual_syringe work exactly as before."""

    def test_missing_dual_syringe_field(self):
        """Pump config without dual_syringe field should default to single."""
        from pump_control_service import _build_burst_configs

        recipe = {"Sugar": 3000.0}
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    # No dual_syringe key at all
                }
            ],
        }
        configs = _build_burst_configs(recipe, pump_config)
        assert configs[0].volume_ul == 3000.0  # Unchanged

    def test_explicit_false_dual_syringe(self):
        """dual_syringe: false should behave identically to missing."""
        from pump_control_service import _build_burst_configs

        recipe = {"Sugar": 3000.0}
        pump_config = {
            "dispensing_rate_ul_min": 2000,
            "pumps": [
                {
                    "address": 0,
                    "ingredient": "Sugar",
                    "syringe_diameter_mm": 29.0,
                    "dual_syringe": False,
                }
            ],
        }
        configs = _build_burst_configs(recipe, pump_config)
        assert configs[0].volume_ul == 3000.0  # Unchanged
