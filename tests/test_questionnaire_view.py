import pytest
from unittest.mock import patch, MagicMock
import sys

# Mock streamlit before it's imported by other modules
sys.modules['streamlit'] = MagicMock()

# Import the module explicitly
import robotaste.views.questionnaire as questionnaire_view

@pytest.fixture
def mock_st(monkeypatch):
    """Fixture to mock all streamlit calls."""
    mock_streamlit = MagicMock()
    monkeypatch.setattr(sys.modules['streamlit'], 'session_state', {}, raising=False)
    
    # Mock columns to return a list of mocks
    def mock_columns(count):
        return [MagicMock() for _ in range(count)]
    
    mock_streamlit.columns.side_effect = mock_columns
    
    # Update the module's st reference just in case
    questionnaire_view.st = mock_streamlit
    
    return mock_streamlit

def test_visual_layout_discrete(mock_st):
    """
    Test that the visual layout (columns) is used for appropriate discrete sliders.
    """
    # Mock config
    config = {
        "name": "Test Questionnaire",
        "questions": [
            {
                "id": "q1",
                "type": "slider",
                "label": "Test Label",
                "min": 1,
                "max": 5,
                "step": 1,
                "scale_labels": {1: "Low", 5: "High"},
            }
        ]
    }

    # Patch get_questionnaire_config on the module object
    with patch.object(questionnaire_view, 'get_questionnaire_config', return_value=config):
        # Call render
        questionnaire_view.render_questionnaire("test_type", "p1")

        # Verify st.columns was called with correct count (1 to 5 = 5 steps)
        mock_st.columns.assert_called_with(5)
        
        # Verify markdown was called for labels
        # We expect calls for: Title, Question Label, "Low", "High"
        assert mock_st.markdown.call_count >= 1
        
        # Verify st.slider was called with collapsed visibility
        mock_st.slider.assert_called_with(
            label="Test Label",
            min_value=1,
            max_value=5,
            value=1,
            step=1,
            key="questionnaire_test_type_p1_q1",
            label_visibility="collapsed",
            format="%d"
        )

def test_visual_layout_continuous(mock_st):
    """
    Test that the visual layout (columns) is used for appropriate continuous sliders
    (like intensity_continuous).
    """
    # Mock config for a continuous slider (step < 1) with integer labels
    config = {
        "name": "Continuous Test",
        "questions": [
            {
                "id": "q_cont",
                "type": "slider",
                "label": "Continuous Label",
                "min": 1.0,
                "max": 9.0,
                "step": 0.01,
                "display_type": "slider_continuous",
                "scale_labels": {1: "Min", 5: "Mid", 9: "Max"},
            }
        ]
    }

    with patch.object(questionnaire_view, 'get_questionnaire_config', return_value=config):
        # Call render
        questionnaire_view.render_questionnaire("continuous_type", "p1")

        # Verify st.columns was called with correct count based on integer range
        # 1 to 9 = 9 steps (slots)
        mock_st.columns.assert_called_with(9)
        
        # Verify st.slider was called with collapsed visibility and float params
        mock_st.slider.assert_called_with(
            label="Continuous Label",
            min_value=1.0,
            max_value=9.0,
            value=1.0, # Default to min
            step=0.01,
            key="questionnaire_continuous_type_p1_q_cont",
            label_visibility="collapsed",
            format="%.2f"
        )

def test_fallback_layout_rendering(mock_st):
    """
    Test that fallback layout is used for sliders with too many steps.
    """
    # Mock config with large range
    config = {
        "name": "Test Questionnaire",
        "questions": [
            {
                "id": "q2",
                "type": "slider",
                "label": "Large Scale",
                "min": 1,
                "max": 20, # Range 19 -> 20 steps, > 12 limit
                "step": 1,
                "scale_labels": {1: "Min", 20: "Max"},
            }
        ]
    }

    with patch.object(questionnaire_view, 'get_questionnaire_config', return_value=config):
        # Call render
        questionnaire_view.render_questionnaire("test_type_large", "p1")

        # Verify st.columns was NOT called (for the layout)
        mock_st.columns.assert_not_called()
        
        # Verify st.slider was called with correct max_value (proving config was used)
        mock_st.slider.assert_called()
        args, kwargs = mock_st.slider.call_args
        assert kwargs['max_value'] == 20
        # Check label_visibility is collapsed (fallback logic for labeled slider)
        assert kwargs['label_visibility'] == 'collapsed'