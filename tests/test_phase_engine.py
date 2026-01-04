"""
Phase Engine Unit Tests

Tests for the PhaseEngine class, including:
- Phase sequence parsing
- Next phase determination
- Optional phase skipping
- Auto-advance detection
- Loop handling
- Circuit breaker
- Error handling

Author: Claude Sonnet 4.5
Date: January 2026
"""

import pytest
from robotaste.core.phase_engine import PhaseEngine, PhaseDefinition, DEFAULT_PHASES


class TestPhaseDefinition:
    """Test PhaseDefinition dataclass validation."""

    def test_valid_phase_definition(self):
        """Test creating a valid phase definition."""
        phase = PhaseDefinition(
            phase_id="waiting",
            phase_type="builtin",
            required=True
        )
        assert phase.phase_id == "waiting"
        assert phase.phase_type == "builtin"
        assert phase.required is True

    def test_auto_advance_requires_duration(self):
        """Test that auto_advance=True requires duration_ms."""
        with pytest.raises(ValueError, match="auto_advance=True requires duration_ms"):
            PhaseDefinition(
                phase_id="test_phase",
                phase_type="custom",
                auto_advance=True
            )

    def test_auto_advance_with_duration(self):
        """Test valid auto_advance configuration."""
        phase = PhaseDefinition(
            phase_id="test_phase",
            phase_type="custom",
            auto_advance=True,
            duration_ms=5000
        )
        assert phase.auto_advance is True
        assert phase.duration_ms == 5000

    def test_negative_duration_rejected(self):
        """Test that negative duration is rejected."""
        with pytest.raises(ValueError, match="duration_ms must be positive"):
            PhaseDefinition(
                phase_id="test_phase",
                phase_type="custom",
                duration_ms=-1000
            )


class TestPhaseEngineInitialization:
    """Test PhaseEngine initialization and parsing."""

    def test_parse_default_phases_when_empty_protocol(self):
        """Test that empty protocol uses DEFAULT_PHASES."""
        protocol = {"name": "Test Protocol"}
        engine = PhaseEngine(protocol, "test-session")

        assert len(engine.phase_sequence) == len(DEFAULT_PHASES)
        assert engine.phase_sequence[0].phase_id == "waiting"

    def test_parse_custom_phase_sequence(self):
        """Test parsing custom phase sequence."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin", "required": True},
                    {"phase_id": "custom_intro", "phase_type": "custom", "required": True},
                    {"phase_id": "completion", "phase_type": "builtin", "required": True}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        assert len(engine.phase_sequence) == 3
        assert engine.phase_sequence[0].phase_id == "waiting"
        assert engine.phase_sequence[1].phase_id == "custom_intro"
        assert engine.phase_sequence[1].phase_type == "custom"
        assert engine.phase_sequence[2].phase_id == "completion"

    def test_invalid_phase_sequence_falls_back(self):
        """Test that invalid phase sequence falls back to DEFAULT_PHASES."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "invalid", "auto_advance": True}  # Missing duration_ms
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Should fall back to DEFAULT_PHASES
        assert len(engine.phase_sequence) == len(DEFAULT_PHASES)

    def test_phase_sequence_as_list(self):
        """Test phase_sequence provided as direct list (not dict with 'phases' key)."""
        protocol = {
            "phase_sequence": [
                {"phase_id": "waiting", "phase_type": "builtin"},
                {"phase_id": "completion", "phase_type": "builtin"}
            ]
        }
        engine = PhaseEngine(protocol, "test-session")

        assert len(engine.phase_sequence) == 2


class TestPhaseNavigation:
    """Test phase navigation and next phase determination."""

    def test_get_next_phase_sequential(self):
        """Test sequential phase progression."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"},
                    {"phase_id": "registration", "phase_type": "builtin"},
                    {"phase_id": "instructions", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        next_phase = engine.get_next_phase("waiting")
        assert next_phase == "registration"

        next_phase = engine.get_next_phase("registration")
        assert next_phase == "instructions"

    def test_skip_optional_phases(self):
        """Test skipping optional (non-required) phases."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin", "required": True},
                    {"phase_id": "registration", "phase_type": "builtin", "required": False},
                    {"phase_id": "instructions", "phase_type": "builtin", "required": True}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Without skipping, should go to registration
        next_phase = engine.get_next_phase("waiting", skip_optional=False)
        assert next_phase == "registration"

        # With skipping, should skip registration and go to instructions
        next_phase = engine.get_next_phase("waiting", skip_optional=True)
        assert next_phase == "instructions"

    def test_end_of_sequence_goes_to_completion(self):
        """Test that end of sequence defaults to completion."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"},
                    {"phase_id": "instructions", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        next_phase = engine.get_next_phase("instructions")
        assert next_phase == "completion"


class TestExperimentLoop:
    """Test experiment loop handling."""

    def test_entering_experiment_loop(self):
        """Test entering experiment loop from previous phase."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"},
                    {"phase_id": "instructions", "phase_type": "builtin"},
                    {"phase_id": "experiment_loop", "phase_type": "loop"},
                    {"phase_id": "completion", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Transitioning from instructions should enter loop
        next_phase = engine.get_next_phase("instructions")
        assert next_phase == "selection"  # Loop starts with selection (prepare sample first)

    def test_loop_phase_progression(self):
        """Test progression through loop phases."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "experiment_loop", "phase_type": "loop"}
                ]
            },
            "stopping_criteria": {
                "max_cycles": 3
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # loading → questionnaire
        next_phase = engine.get_next_phase("loading", current_cycle=1)
        assert next_phase == "questionnaire"

        # questionnaire → selection
        next_phase = engine.get_next_phase("questionnaire", current_cycle=1)
        assert next_phase == "selection"

        # selection → loading (continue loop, cycle < max_cycles)
        next_phase = engine.get_next_phase("selection", current_cycle=1)
        assert next_phase == "loading"

    def test_loop_exit_on_max_cycles(self):
        """Test exiting loop when max_cycles reached."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"},
                    {"phase_id": "experiment_loop", "phase_type": "loop"},
                    {"phase_id": "completion", "phase_type": "builtin"}
                ]
            },
            "stopping_criteria": {
                "max_cycles": 3
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # NOTE: Stopping logic is now handled in subject.py after QUESTIONNAIRE phase
        # PhaseEngine just handles phase transitions within the loop
        # At cycle 3, selection should go to loading (stopping check happens in subject.py)
        next_phase = engine.get_next_phase("selection", current_cycle=3)
        assert next_phase == "loading"

    def test_robot_preparing_in_loop(self):
        """Test that robot_preparing is recognized as loop phase."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "experiment_loop", "phase_type": "loop"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # robot_preparing → questionnaire
        next_phase = engine.get_next_phase("robot_preparing", current_cycle=1)
        assert next_phase == "questionnaire"


class TestAutoAdvance:
    """Test auto-advance functionality."""

    def test_should_auto_advance_enabled(self):
        """Test detecting auto-advance enabled phases."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "custom_break", "phase_type": "custom", "auto_advance": True, "duration_ms": 5000}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        should_advance, duration = engine.should_auto_advance("custom_break")
        assert should_advance is True
        assert duration == 5000

    def test_should_auto_advance_disabled(self):
        """Test detecting auto-advance disabled phases."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        should_advance, duration = engine.should_auto_advance("waiting")
        assert should_advance is False
        assert duration == 0

    def test_should_auto_advance_unknown_phase(self):
        """Test auto-advance check for unknown phase."""
        protocol = {"phase_sequence": {"phases": []}}
        engine = PhaseEngine(protocol, "test-session")

        should_advance, duration = engine.should_auto_advance("unknown_phase")
        assert should_advance is False
        assert duration == 0


class TestPhaseMetadata:
    """Test phase metadata and content retrieval."""

    def test_can_skip_required_phase(self):
        """Test that required phases cannot be skipped."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "instructions", "phase_type": "builtin", "required": True}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        assert engine.can_skip_phase("instructions") is False

    def test_can_skip_optional_phase(self):
        """Test that optional phases can be skipped."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "registration", "phase_type": "builtin", "required": False}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        assert engine.can_skip_phase("registration") is True

    def test_get_phase_content_for_custom_phase(self):
        """Test retrieving custom content for custom phases."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {
                        "phase_id": "custom_intro",
                        "phase_type": "custom",
                        "content": {
                            "type": "text",
                            "title": "Welcome!",
                            "body": "Welcome to the experiment"
                        }
                    }
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        content = engine.get_phase_content("custom_intro")
        assert content is not None
        assert content["type"] == "text"
        assert content["title"] == "Welcome!"

    def test_get_phase_content_for_builtin_phase(self):
        """Test that builtin phases have no custom content."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        content = engine.get_phase_content("waiting")
        assert content is None


class TestCircuitBreaker:
    """Test circuit breaker to prevent infinite loops."""

    def test_circuit_breaker_triggers(self):
        """Test that circuit breaker triggers after max transitions."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Trigger 101 transitions to exceed MAX_TRANSITIONS (100)
        for i in range(101):
            next_phase = engine.get_next_phase("waiting")

        # Should force completion
        assert next_phase == "completion"

    def test_transition_count_increments(self):
        """Test that transition count increments correctly."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"},
                    {"phase_id": "completion", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        assert engine.transition_count == 0

        engine.get_next_phase("waiting")
        assert engine.transition_count == 1

        engine.get_next_phase("waiting")
        assert engine.transition_count == 2


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unknown_current_phase(self):
        """Test handling unknown current phase."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Should handle gracefully
        next_phase = engine.get_next_phase("unknown_phase")
        # Should return first phase or stay in current
        assert next_phase in ["waiting", "unknown_phase"]

    def test_empty_phase_sequence(self):
        """Test handling empty phase sequence."""
        protocol = {
            "phase_sequence": {
                "phases": []
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Should fall back to DEFAULT_PHASES
        assert len(engine.phase_sequence) == len(DEFAULT_PHASES)

    def test_missing_stopping_criteria(self):
        """Test loop handling without stopping criteria."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "experiment_loop", "phase_type": "loop"}
                ]
            }
            # No stopping_criteria
        }
        engine = PhaseEngine(protocol, "test-session")

        # Should not crash, loop continues until manual stop
        next_phase = engine.get_next_phase("selection", current_cycle=100)
        # Without max_cycles, should continue looping
        assert next_phase == "loading"


class TestComplexScenarios:
    """Test complex realistic scenarios."""

    def test_full_experiment_flow_with_custom_phases(self):
        """Test full experiment flow with custom phases."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin"},
                    {"phase_id": "registration", "phase_type": "builtin", "required": False},
                    {"phase_id": "custom_tutorial", "phase_type": "custom", "content": {"type": "text"}},
                    {"phase_id": "instructions", "phase_type": "builtin"},
                    {"phase_id": "experiment_loop", "phase_type": "loop"},
                    {"phase_id": "custom_survey", "phase_type": "custom", "content": {"type": "survey"}},
                    {"phase_id": "completion", "phase_type": "builtin"}
                ]
            },
            "stopping_criteria": {
                "max_cycles": 2
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Trace flow
        assert engine.get_next_phase("waiting") == "registration"
        assert engine.get_next_phase("registration") == "custom_tutorial"
        assert engine.get_next_phase("custom_tutorial") == "instructions"
        assert engine.get_next_phase("instructions") == "selection"  # Enter loop with selection

        # Loop cycle 1: selection -> loading -> questionnaire -> selection
        assert engine.get_next_phase("selection", current_cycle=1) == "loading"
        assert engine.get_next_phase("loading", current_cycle=1) == "questionnaire"
        assert engine.get_next_phase("questionnaire", current_cycle=1) == "selection"

        # Loop cycle 2: selection -> loading -> questionnaire -> selection
        # NOTE: Stopping logic is now in subject.py, not phase_engine
        # PhaseEngine would continue looping, subject.py handles the exit
        assert engine.get_next_phase("selection", current_cycle=2) == "loading"
        assert engine.get_next_phase("loading", current_cycle=2) == "questionnaire"
        assert engine.get_next_phase("questionnaire", current_cycle=2) == "selection"

        # If we manually exit the loop (as subject.py would), next phase is custom_survey
        # This simulates what happens when subject.py detects max_cycles reached

    def test_skip_all_optional_phases(self):
        """Test skipping multiple optional phases in sequence."""
        protocol = {
            "phase_sequence": {
                "phases": [
                    {"phase_id": "waiting", "phase_type": "builtin", "required": True},
                    {"phase_id": "registration", "phase_type": "builtin", "required": False},
                    {"phase_id": "tutorial", "phase_type": "custom", "required": False},
                    {"phase_id": "instructions", "phase_type": "builtin", "required": True}
                ]
            }
        }
        engine = PhaseEngine(protocol, "test-session")

        # Skip all optional phases
        next_phase = engine.get_next_phase("waiting", skip_optional=True)
        assert next_phase == "instructions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
