import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import json

# Mock streamlit before it's imported by other modules
import sys
sys.modules['streamlit'] = MagicMock()

from robotaste.views import subject as subject_view
from robotaste.core.state_machine import ExperimentPhase

# A more robust mock for the session_state, behaving a bit more like a dictionary
class MockSessionState(dict):
    def __init__(self, *args, **kwargs):
        super(MockSessionState, self).__init__(*args, **kwargs)
        self.__dict__ = self

    def __getattr__(self, item):
        return self.get(item)

    def __setattr__(self, key, value):
        self[key] = value

@pytest.fixture
def mock_st(monkeypatch):
    """Fixture to mock all streamlit calls."""
    mock_streamlit = MagicMock()
    
    # Load the test protocol
    with open("tests/test_protocol_mixed_mode.json", "r") as f:
        protocol_config = json.load(f)

    # Initialize session state
    session_state = MockSessionState(
        session_id="test_session_123",
        participant="test_participant_123",
        session_code="test_code",
        phase=ExperimentPhase.SELECTION.value,
        num_ingredients=2,
        interface_type="2d_grid",
        experiment_config=protocol_config,
        cycle_data={},
        next_selection_data={},
    )
    
    # Use PropertyMock to mock st.session_state
    monkeypatch.setattr(sys.modules['streamlit'], 'session_state', session_state, raising=False)
    monkeypatch.setattr(sys.modules['streamlit'], 'rerun', MagicMock(), raising=False)


    return mock_streamlit

def test_subject_interface_predetermined_cycle(mock_st):
    """
    Tests if the subject interface correctly handles a 'predetermined' cycle.
    """
    # GIVEN a subject in a session on a predetermined cycle
    st = sys.modules['streamlit']
    st.session_state.phase = ExperimentPhase.SELECTION.value

    with patch('robotaste.views.subject.prepare_cycle_sample') as mock_prepare, \
         patch('robotaste.views.subject.state_helpers.transition') as mock_transition, \
         patch('robotaste.views.subject.get_current_cycle', return_value=1), \
         patch('robotaste.views.subject.grid_interface') as mock_grid_interface:

        mock_prepare.return_value = {
            'mode': 'predetermined',
            'concentrations': {'Sugar': 10.0, 'Salt': 2.0}
        }

        # WHEN the subject interface is rendered
        subject_view.subject_interface()

        # THEN it should call prepare_cycle_sample and call the correct interface function
        mock_prepare.assert_called_with("test_session_123", 1)
        assert st.session_state.cycle_data['mode'] == 'predetermined'
        mock_grid_interface.assert_called_with(st.session_state.cycle_data)


def test_grid_interface_predetermined_mode():
    """
    Tests the grid_interface logic for a 'predetermined' sample.
    """
    st = sys.modules['streamlit']
    
    cycle_data = {
        'mode': 'predetermined',
        'concentrations': {'Sugar': 10.0, 'Salt': 2.0}
    }
    st.session_state.phase = ExperimentPhase.SELECTION.value
    st.session_state.num_ingredients = 2
    st.session_state.interface_type = "2d_grid"

    with patch('robotaste.views.subject.state_helpers.transition') as mock_transition, \
         patch('robotaste.views.subject.get_current_cycle', return_value=1), \
         patch('robotaste.views.subject.sync_session_state'):

        # WHEN grid_interface is called in predetermined mode
        subject_view.grid_interface(cycle_data)

        # THEN it should set next_selection_data and transition to LOADING
        assert st.session_state.next_selection_data['selection_mode'] == 'predetermined'
        assert st.session_state.next_selection_data['ingredient_concentrations'] == {'Sugar': 10.0, 'Salt': 2.0}
        
        mock_transition.assert_called_with(
            st.session_state.get_current_phase(),
            new_phase=ExperimentPhase.LOADING,
            session_id="test_session_123"
        )

def test_grid_interface_bo_selected_mode_no_override():
    """
    Tests the grid_interface logic for a 'bo_selected' sample without override.
    """
    st = sys.modules['streamlit']
    st.session_state.override_bo = False
    
    cycle_data = {
        'mode': 'bo_selected',
        'suggestion': {
            'concentrations': {'Sugar': 25.0, 'Salt': 5.0},
            'grid_coordinates': {'x': 200, 'y': 200},
            'predicted_value': 8.5
        }
    }
    st.session_state.phase = ExperimentPhase.SELECTION.value
    st.session_state.num_ingredients = 2
    st.session_state.interface_type = "2d_grid"

    # Mock the button click to proceed
    st.button = MagicMock(side_effect=lambda label, **kwargs: "Proceed" in label)


    with patch('robotaste.views.subject.state_helpers.transition') as mock_transition, \
         patch('robotaste.views.subject.get_current_cycle', return_value=6), \
         patch('robotaste.views.subject.sync_session_state'), \
         patch('robotaste.views.subject.st_canvas'), \
         patch('robotaste.views.subject.create_canvas_drawing'):

        # WHEN grid_interface is called in BO mode and user proceeds
        subject_view.grid_interface(cycle_data)

        # THEN it should set next_selection_data for BO and transition
        assert st.session_state.next_selection_data['selection_mode'] == 'bo_selected'
        assert st.session_state.next_selection_data['ingredient_concentrations'] == {'Sugar': 25.0, 'Salt': 5.0}
        assert st.session_state.next_selection_data['method'] == 'bayesian_optimization'
        
        mock_transition.assert_called_with(
            st.session_state.get_current_phase(),
            new_phase=ExperimentPhase.LOADING,
            session_id="test_session_123"
        )
        assert st.session_state.override_bo == False

def test_grid_interface_bo_selected_with_override():
    """
    Tests the grid_interface logic for a 'bo_selected' sample when user chooses to override.
    """
    st = sys.modules['streamlit']
    st.session_state.override_bo = False

    cycle_data = {'mode': 'bo_selected', 'suggestion': {...}}
    st.session_state.phase = ExperimentPhase.SELECTION.value
    st.session_state.num_ingredients = 2
    st.session_state.interface_type = "2d_grid"

    # Mock the override button click
    def button_mock(label, **kwargs):
        if "Override" in label:
            kwargs['on_click']() # Simulate the on_click call
            return True
        return False
    st.button = MagicMock(side_effect=button_mock)
    
    with patch('robotaste.views.subject.sync_session_state'), \
         patch('robotaste.views.subject.st_canvas'), \
         patch('robotaste.views.subject.create_canvas_drawing'):

        # WHEN grid_interface is called and user overrides
        subject_view.grid_interface(cycle_data)

        # THEN the override_bo flag should be set to True
        assert st.session_state.override_bo == True
