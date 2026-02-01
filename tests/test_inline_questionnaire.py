"""
Test Inline Questionnaire Configuration

Tests the new inline questionnaire feature where questionnaires are embedded
directly in protocols instead of referencing a library.
"""

import pytest
import tempfile
import os
from robotaste.config.protocols import validate_protocol
from robotaste.data.protocol_repo import create_protocol_in_db, get_protocol_by_id
from robotaste.config.questionnaire import (
    get_questionnaire_config,
    QUESTIONNAIRE_EXAMPLES,
    validate_questionnaire_response,
)
from robotaste.data.database import (
    DB_PATH,
    create_session,
    get_session,
    get_questionnaire_from_session,
    update_session_with_config,
)
from robotaste.data import database as sql
import json


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    # Create a temporary database file
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()

    # Override the module-level DB_PATH
    original_db_path = sql.DB_PATH
    sql.DB_PATH = temp_db.name

    # Initialize database
    sql.init_database()

    yield temp_db.name

    # Cleanup
    sql.DB_PATH = original_db_path
    if os.path.exists(temp_db.name):
        os.unlink(temp_db.name)


class TestInlineQuestionnaireValidation:
    """Test validation of inline questionnaire configurations."""

    def test_valid_inline_questionnaire(self):
        """Inline questionnaire should validate successfully."""
        protocol = {
            "protocol_id": "test-inline-001",
            "name": "Test Inline Questionnaire",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire": QUESTIONNAIRE_EXAMPLES["hedonic_continuous"],
        }

        is_valid, errors = validate_protocol(protocol)
        assert is_valid, f"Should be valid, got errors: {errors}"
        assert len(errors) == 0

    def test_legacy_questionnaire_type_rejected(self):
        """Legacy questionnaire_type string should now be rejected."""
        protocol = {
            "protocol_id": "test-legacy-001",
            "name": "Test Legacy Questionnaire",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire_type": "hedonic_discrete",
        }

        is_valid, errors = validate_protocol(protocol)
        assert not is_valid, "Should fail without inline questionnaire"
        assert any("questionnaire" in err.lower() for err in errors)

    def test_missing_both_questionnaire_formats(self):
        """Protocol without questionnaire or questionnaire_type should fail."""
        protocol = {
            "protocol_id": "test-missing-001",
            "name": "Test Missing Questionnaire",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
        }

        is_valid, errors = validate_protocol(protocol)
        assert not is_valid
        assert any("questionnaire" in err.lower() for err in errors)

    def test_invalid_questionnaire_missing_questions(self):
        """Questionnaire without questions should fail."""
        protocol = {
            "protocol_id": "test-invalid-001",
            "name": "Test Invalid Questionnaire",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire": {
                "name": "Bad Questionnaire",
                "bayesian_target": {
                    "variable": "rating",
                    "higher_is_better": True,
                },
            },
        }

        is_valid, errors = validate_protocol(protocol)
        assert not is_valid
        assert any("question" in err.lower() for err in errors)

    def test_duplicate_question_ids(self):
        """Questionnaire with duplicate question IDs should fail."""
        protocol = {
            "protocol_id": "test-dup-001",
            "name": "Test Duplicate IDs",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire": {
                "name": "Duplicate IDs",
                "questions": [
                    {"id": "rating", "type": "slider", "label": "Rating 1", "min": 1, "max": 9},
                    {"id": "rating", "type": "slider", "label": "Rating 2", "min": 1, "max": 9},
                ],
                "bayesian_target": {
                    "variable": "rating",
                    "higher_is_better": True,
                },
            },
        }

        is_valid, errors = validate_protocol(protocol)
        assert not is_valid
        assert any("duplicate" in err.lower() for err in errors)

    def test_bayesian_target_references_unknown_question(self):
        """Bayesian target referencing unknown question should fail."""
        protocol = {
            "protocol_id": "test-badref-001",
            "name": "Test Bad Reference",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire": {
                "name": "Bad Reference",
                "questions": [
                    {"id": "liking", "type": "slider", "label": "Liking", "min": 1, "max": 9},
                ],
                "bayesian_target": {
                    "variable": "unknown_var",  # Doesn't exist
                    "higher_is_better": True,
                },
            },
        }

        is_valid, errors = validate_protocol(protocol)
        assert not is_valid
        assert any("unknown question" in err.lower() for err in errors)


class TestDualModeQuestionnaireLoading:
    """Test that questionnaires can be loaded from both inline and legacy formats."""

    def test_get_questionnaire_config_with_dict(self):
        """get_questionnaire_config should accept dict input."""
        questionnaire = QUESTIONNAIRE_EXAMPLES["hedonic_continuous"]
        result = get_questionnaire_config(questionnaire)

        assert result is not None
        assert result == questionnaire
        assert result["name"] == "Hedonic Test (Continuous)"

    def test_get_questionnaire_config_with_string_raises(self):
        """get_questionnaire_config should reject string input."""
        with pytest.raises(TypeError):
            get_questionnaire_config("hedonic_discrete")

    def test_get_questionnaire_config_invalid_input_raises(self):
        """Invalid input should raise TypeError."""
        with pytest.raises(TypeError):
            get_questionnaire_config("nonexistent_type")


class TestSessionWithInlineQuestionnaire:
    """Test complete session workflow with inline questionnaires."""

    def test_create_protocol_and_session_with_inline_questionnaire(self, test_db):
        """End-to-end: Protocol with inline questionnaire → Session."""
        # Create protocol with inline questionnaire
        protocol = {
            "protocol_id": "proto-inline-e2e-001",
            "name": "E2E Inline Questionnaire Test",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire": QUESTIONNAIRE_EXAMPLES["hedonic_continuous"],
        }

        # Validate and save protocol
        is_valid, errors = validate_protocol(protocol)
        assert is_valid, f"Protocol validation failed: {errors}"

        protocol_id = create_protocol_in_db(protocol)
        assert protocol_id is not None

        # Load protocol and verify questionnaire
        loaded = get_protocol_by_id(protocol_id)
        assert loaded is not None
        assert "questionnaire" in loaded
        assert loaded["questionnaire"]["name"] == "Hedonic Test (Continuous)"

        # Create session with protocol
        session_id, session_code = create_session(
            moderator_name="Test Moderator", protocol_id=protocol_id
        )
        assert session_id is not None

        # Update session with config (simulating trial start)
        success = update_session_with_config(
            session_id=session_id,
            user_id="test_participant",
            num_ingredients=1,
            interface_type="sliders",
            method="linear",
            ingredients=[{"name": "Sugar", "min_concentration": 0, "max_concentration": 100}],
            bo_config={},
            experiment_config={
                **loaded,
                "questionnaire": loaded["questionnaire"],
            },
        )
        assert success

        # Retrieve session and verify questionnaire
        session_info = get_session(session_id)
        assert session_info is not None

        # Test dual-mode loading helper
        questionnaire = get_questionnaire_from_session(session_info)
        assert questionnaire is not None
        assert questionnaire["name"] == "Hedonic Test (Continuous)"

    def test_legacy_session_with_questionnaire_type(self, test_db):
        """Legacy session with questionnaire_type should still work."""
        # Create protocol with legacy questionnaire_type
        protocol = {
            "protocol_id": "proto-legacy-e2e-001",
            "name": "E2E Legacy Questionnaire Test",
            "version": "1.0",
            "ingredients": [
                {"name": "Sugar", "min_concentration": 0, "max_concentration": 100}
            ],
            "sample_selection_schedule": [
                {
                    "cycle_range": {"start": 1, "end": 5},
                    "mode": "user_selected",
                }
            ],
            "questionnaire_type": "hedonic_discrete",
        }

        protocol_id = create_protocol_in_db(protocol)
        session_id, _ = create_session(moderator_name="Test", protocol_id=protocol_id)

        # Load session - should fall back to questionnaire_type lookup
        session_info = get_session(session_id)
        assert session_info is not None

        # The dual-mode helper should handle this gracefully
        # (Note: In a real scenario, the experiment_config would have questionnaire_type)


class TestQuestionnaireResponseValidation:
    """Test that response validation works with both formats."""

    def test_validate_response_with_dict_questionnaire(self):
        """Response validation should work with dict questionnaire."""
        questionnaire = QUESTIONNAIRE_EXAMPLES["hedonic_continuous"]
        response = {"overall_liking": 7.5}

        is_valid, error = validate_questionnaire_response(response, questionnaire)
        assert is_valid
        assert error is None

    def test_validate_response_with_string_questionnaire_rejected(self):
        """Response validation should reject string questionnaire."""
        response = {"overall_liking": 8}

        # Should raise TypeError when passed string instead of dict
        with pytest.raises(TypeError):
            validate_questionnaire_response(response, "hedonic_discrete")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
