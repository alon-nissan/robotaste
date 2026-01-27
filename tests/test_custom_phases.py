"""
Tests for custom phase rendering system.

Tests cover:
- Custom phase imports
- Database save/retrieve functionality
- Custom phase type routing
- Integration with PhaseRouter

Author: AI Agent
Date: 2026-01-27
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch

# Import functions to test
from robotaste.views.phases.custom.custom_phase import (
    render_custom_phase,
    render_text_phase,
    render_media_phase,
    render_survey_phase,
    render_break_phase
)
from robotaste.data.database import (
    init_database,
    create_session,
    save_custom_phase_data,
    get_session,
    DB_PATH
)
import robotaste.data.database as db_module


class TestCustomPhaseImports:
    """Test that all custom phase functions can be imported."""
    
    def test_import_render_custom_phase(self):
        """Test main custom phase renderer imports."""
        assert callable(render_custom_phase)
    
    def test_import_all_phase_types(self):
        """Test all phase type renderers import."""
        assert callable(render_text_phase)
        assert callable(render_media_phase)
        assert callable(render_survey_phase)
        assert callable(render_break_phase)


class TestSaveCustomPhaseData:
    """Test database save functionality for custom phase data."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        test_db = tempfile.mktemp(suffix='.db')
        original_db = db_module.DB_PATH
        db_module.DB_PATH = test_db
        
        init_database()
        
        yield test_db
        
        # Cleanup
        if os.path.exists(test_db):
            os.unlink(test_db)
        db_module.DB_PATH = original_db
    
    def test_save_custom_phase_data_basic(self, temp_db):
        """Test saving basic custom phase data."""
        # Create session
        session_id, _ = create_session("TEST123")
        
        # Save custom phase data
        test_data = {"question1": "answer1", "rating": 5}
        success = save_custom_phase_data(session_id, "test_phase", test_data)
        
        assert success
        
        # Verify saved
        session = get_session(session_id)
        config_raw = session["experiment_config"]
        config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
        
        assert "custom_phase_data" in config
        assert "test_phase" in config["custom_phase_data"]
        assert config["custom_phase_data"]["test_phase"]["data"] == test_data
    
    def test_save_multiple_custom_phases(self, temp_db):
        """Test saving data for multiple custom phases."""
        session_id, _ = create_session("TEST456")
        
        # Save first phase
        data1 = {"q1": "answer1"}
        save_custom_phase_data(session_id, "phase1", data1)
        
        # Save second phase
        data2 = {"q2": "answer2"}
        save_custom_phase_data(session_id, "phase2", data2)
        
        # Verify both saved
        session = get_session(session_id)
        config_raw = session["experiment_config"]
        config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
        
        assert len(config["custom_phase_data"]) == 2
        assert config["custom_phase_data"]["phase1"]["data"] == data1
        assert config["custom_phase_data"]["phase2"]["data"] == data2
    
    def test_save_custom_phase_data_with_timestamp(self, temp_db):
        """Test that timestamp is saved with custom phase data."""
        session_id, _ = create_session("TEST789")
        
        test_data = {"rating": 7}
        save_custom_phase_data(session_id, "test_phase", test_data)
        
        session = get_session(session_id)
        config_raw = session["experiment_config"]
        config = json.loads(config_raw) if isinstance(config_raw, str) else config_raw
        
        assert "timestamp" in config["custom_phase_data"]["test_phase"]
        # Timestamp should be ISO format string
        timestamp = config["custom_phase_data"]["test_phase"]["timestamp"]
        assert isinstance(timestamp, str)
        assert "T" in timestamp  # ISO format includes 'T'
    
    def test_save_custom_phase_data_invalid_session(self, temp_db):
        """Test saving data for non-existent session."""
        success = save_custom_phase_data("invalid-session-id", "phase", {"data": 1})
        assert not success


class TestPhaseRouterIntegration:
    """Test integration with PhaseRouter."""
    
    def test_phase_router_can_import_custom_phase(self):
        """Test that PhaseRouter can import custom phase renderer."""
        from robotaste.core.phase_router import PhaseRouter
        
        test_protocol = {
            "protocol_id": "test",
            "name": "Test",
            "version": "1.0",
            "phases": [
                {
                    "phase_id": "intro",
                    "phase_type": "custom",
                    "content": {
                        "type": "text",
                        "title": "Welcome",
                        "text": "Test"
                    }
                }
            ]
        }
        
        # Should initialize without error
        router = PhaseRouter(test_protocol, "test-session", "subject")
        assert router is not None
    
    def test_phase_router_has_custom_phase_method(self):
        """Test that PhaseRouter has _render_custom_phase method."""
        from robotaste.core.phase_router import PhaseRouter
        
        test_protocol = {
            "protocol_id": "test",
            "name": "Test",
            "version": "1.0",
            "phases": []
        }
        
        router = PhaseRouter(test_protocol, "test-session", "subject")
        assert hasattr(router, '_render_custom_phase')
        assert callable(router._render_custom_phase)


class TestCustomPhaseContentValidation:
    """Test validation and error handling for custom phase content."""
    
    @patch('streamlit.error')
    def test_render_custom_phase_no_content(self, mock_error):
        """Test error handling when content is None."""
        render_custom_phase("test_phase", None, "session-123")
        mock_error.assert_called()
    
    @patch('streamlit.error')
    def test_render_custom_phase_no_type(self, mock_error):
        """Test error handling when type is missing."""
        render_custom_phase("test_phase", {}, "session-123")
        mock_error.assert_called()
    
    @patch('streamlit.error')
    def test_render_custom_phase_unknown_type(self, mock_error):
        """Test error handling for unknown phase type."""
        content = {"type": "unknown_type"}
        render_custom_phase("test_phase", content, "session-123")
        mock_error.assert_called()


class TestCustomPhaseTypes:
    """Test individual custom phase type handlers."""
    
    @patch('streamlit.button', return_value=False)
    @patch('streamlit.markdown')
    @patch('streamlit.header')
    def test_render_text_phase_basic(self, mock_header, mock_markdown, mock_button):
        """Test basic text phase rendering."""
        content = {
            "title": "Test Title",
            "text": "Test text content"
        }
        render_text_phase("test_phase", content)
        
        mock_header.assert_called_with("Test Title")
        mock_markdown.assert_called()
    
    @patch('streamlit.button', return_value=False)
    @patch('streamlit.header')
    @patch('streamlit.error')
    def test_render_media_phase_no_url(self, mock_error, mock_header, mock_button):
        """Test media phase error handling when URL is missing."""
        content = {
            "title": "Test Media",
            "media_type": "image"
            # Missing media_url
        }
        render_media_phase("test_phase", content)
        
        mock_error.assert_called()
    
    @patch('streamlit.form_submit_button', return_value=False)
    @patch('streamlit.form')
    @patch('streamlit.header')
    @patch('streamlit.error')
    def test_render_survey_phase_no_questions(self, mock_error, mock_header, mock_form, mock_submit):
        """Test survey phase error handling when questions are missing."""
        content = {
            "title": "Test Survey"
            # Missing questions
        }
        render_survey_phase("test_phase", content, "session-123")
        
        mock_error.assert_called()
    
    @patch('streamlit.header')
    @patch('streamlit.error')
    def test_render_break_phase_no_duration(self, mock_error, mock_header):
        """Test break phase error handling when duration is missing."""
        content = {
            "title": "Break Time",
            "message": "Take a break"
            # Missing duration_seconds
        }
        render_break_phase("test_phase", content)
        
        mock_error.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
