"""
Test script for Phases 4-5: Session Manager and State Machine
Updated for real-time phase sync and no backward compatibility
"""

import os
import sys
import json
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Import modules to test
import sql_handler as sql
import session_manager as session_mgr
import state_machine as sm

# Mock streamlit for testing
class MockSessionState:
    def __init__(self):
        self._state = {}

    def __setattr__(self, key, value):
        if key == '_state':
            super().__setattr__(key, value)
        else:
            self._state[key] = value

    def __getattr__(self, key):
        if key == '_state':
            return super().__getattribute__(key)
        return self._state.get(key)

    def __contains__(self, key):
        """Support 'in' operator for checking if key exists"""
        return key in self._state

    def get(self, key, default=None):
        return self._state.get(key, default)


class MockStreamlit:
    def __init__(self):
        self.session_state = MockSessionState()


# Replace streamlit module
sys.modules['streamlit'] = MockStreamlit()
import streamlit as st

# Reload modules after mock
import importlib
importlib.reload(session_mgr)
importlib.reload(sm)


def setup_test_database():
    """Initialize test database with questionnaire type"""
    print("\n=== Setting Up Test Database ===")

    # Remove old test database
    if os.path.exists("robotaste.db"):
        os.remove("robotaste.db")
        print("✓ Removed old database")

    # Initialize database
    success = sql.init_database()
    assert success, "Database initialization failed"
    print("✓ Database initialized")

    # Questionnaire types are already inserted by schema, verify they exist
    with sql.get_database_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM questionnaire_types WHERE id = 1")
        count = cursor.fetchone()[0]
        assert count > 0, "Questionnaire type not found"
    print("✓ Test questionnaire types verified")


def test_state_machine_phases():
    """Test state machine phase definitions and transitions"""
    print("\n=== Testing State Machine Phases ===")

    # Test enum values
    assert sm.ExperimentPhase.WAITING.value == "waiting"
    assert sm.ExperimentPhase.ROBOT_PREPARING.value == "robot_preparing"
    assert sm.ExperimentPhase.TASTING.value == "tasting"
    assert sm.ExperimentPhase.QUESTIONNAIRE.value == "questionnaire"
    assert sm.ExperimentPhase.SELECTION.value == "selection"
    assert sm.ExperimentPhase.COMPLETE.value == "complete"
    print("✓ All 6 phases defined correctly")

    # Test from_string
    phase = sm.ExperimentPhase.from_string("waiting")
    assert phase == sm.ExperimentPhase.WAITING
    print("✓ from_string() works")

    # Test valid transitions
    assert sm.ExperimentStateMachine.can_transition(
        sm.ExperimentPhase.WAITING,
        sm.ExperimentPhase.ROBOT_PREPARING
    )
    print("✓ WAITING → ROBOT_PREPARING transition valid")

    assert sm.ExperimentStateMachine.can_transition(
        sm.ExperimentPhase.SELECTION,
        sm.ExperimentPhase.ROBOT_PREPARING
    )
    print("✓ SELECTION → ROBOT_PREPARING (next cycle) transition valid")

    assert sm.ExperimentStateMachine.can_transition(
        sm.ExperimentPhase.SELECTION,
        sm.ExperimentPhase.COMPLETE
    )
    print("✓ SELECTION → COMPLETE (finish) transition valid")

    # Test invalid transitions
    assert not sm.ExperimentStateMachine.can_transition(
        sm.ExperimentPhase.WAITING,
        sm.ExperimentPhase.TASTING
    )
    print("✓ WAITING → TASTING transition correctly rejected")

    assert not sm.ExperimentStateMachine.can_transition(
        sm.ExperimentPhase.QUESTIONNAIRE,
        sm.ExperimentPhase.COMPLETE
    )
    print("✓ QUESTIONNAIRE → COMPLETE transition correctly rejected")


def test_state_machine_transitions_with_db_sync():
    """Test state machine transitions sync to database"""
    print("\n=== Testing State Machine Transitions with DB Sync ===")

    # Create a test session first
    sql.create_user("test_user_phase_sync")
    session_id = sql.create_session(
        user_id="test_user_phase_sync",
        num_ingredients=2,
        interface_type="grid_2d",
        method="linear",
        ingredients=[
            {"position": 1, "name": "A", "min": 0, "max": 100, "unit": "%"},
            {"position": 2, "name": "B", "min": 0, "max": 100, "unit": "%"}
        ],
        question_type_id=1,
        bo_config={"enabled": False},
        experiment_config={}
    )

    # Initialize phase
    st.session_state.phase = "waiting"
    print("✓ Phase initialized to 'waiting'")

    # Test transition with DB sync
    sm.ExperimentStateMachine.transition(
        sm.ExperimentPhase.ROBOT_PREPARING,
        session_id=session_id
    )
    assert st.session_state.phase == "robot_preparing"
    print("✓ Session state updated to 'robot_preparing'")

    # Verify phase was synced to database
    session = sql.get_session(session_id)
    assert session["current_phase"] == "robot_preparing"
    print("✓ Phase synced to database (current_phase = 'robot_preparing')")

    # Test full cycle
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.TASTING, session_id=session_id)
    session = sql.get_session(session_id)
    assert session["current_phase"] == "tasting"
    print("✓ TASTING phase synced to database")

    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.QUESTIONNAIRE, session_id=session_id)
    session = sql.get_session(session_id)
    assert session["current_phase"] == "questionnaire"
    print("✓ QUESTIONNAIRE phase synced to database")

    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.SELECTION, session_id=session_id)
    session = sql.get_session(session_id)
    assert session["current_phase"] == "selection"
    print("✓ SELECTION phase synced to database")

    # Test completion (should update both current_phase and state)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.COMPLETE, session_id=session_id)
    session = sql.get_session(session_id)
    assert session["current_phase"] == "complete"
    assert session["state"] == "completed"
    print("✓ COMPLETE phase synced + session state set to 'completed'")


def test_session_manager_create_session():
    """Test session manager session creation"""
    print("\n=== Testing Session Manager - Create Session ===")

    # Prepare experiment config
    experiment_config = {
        "user_id": "test_user_session_mgr",
        "num_ingredients": 2,
        "interface_type": "grid_2d",
        "method": "logarithmic",
        "ingredients": [
            {"position": 1, "name": "Sugar", "min": 0.73, "max": 73.0, "unit": "mM"},
            {"position": 2, "name": "Salt", "min": 0.10, "max": 10.0, "unit": "mM"}
        ],
        "question_type_id": 1,
        "bayesian_optimization": {
            "enabled": True,
            "acquisition_function": "ei",
            "min_samples_for_bo": 3
        }
    }

    # Create session
    session_id = session_mgr.create_session("Test Moderator", experiment_config)
    assert session_id is not None
    assert len(session_id) > 0
    print(f"✓ Session created: {session_id}")

    # Verify session exists in database
    session = sql.get_session(session_id)
    assert session is not None
    assert session["user_id"] == "test_user_session_mgr"
    assert session["state"] == "active"
    assert session["current_phase"] == "waiting"
    print("✓ Session verified in database (current_phase = 'waiting')")

    # Verify moderator name was added to config
    exp_config = session["experiment_config"]
    assert exp_config["moderator_name"] == "Test Moderator"
    print("✓ Moderator name added to config")

    return session_id


def test_session_manager_join_session(session_id):
    """Test session manager join functionality"""
    print("\n=== Testing Session Manager - Join Session ===")

    # Test valid join
    can_join = session_mgr.join_session(session_id)
    assert can_join == True
    print("✓ Subject can join active session")

    # Test invalid session ID
    can_join = session_mgr.join_session("nonexistent-session-id")
    assert can_join == False
    print("✓ Cannot join nonexistent session")

    # Test completed session
    sql.update_session_state(session_id, "completed")
    can_join = session_mgr.join_session(session_id)
    assert can_join == False
    print("✓ Cannot join completed session")

    # Restore to active
    sql.update_session_state(session_id, "active")


def test_session_manager_get_session_info(session_id):
    """Test session manager get_session_info (no backward compatibility)"""
    print("\n=== Testing Session Manager - Get Session Info ===")

    # Get session info (returns raw session dict from sql handler)
    session_info = session_mgr.get_session_info(session_id)
    assert session_info is not None
    print("✓ Session info retrieved")

    # Check direct fields from database
    assert "session_id" in session_info
    assert session_info["session_id"] == session_id
    print("✓ session_id field present")

    assert "user_id" in session_info
    assert session_info["user_id"] == "test_user_session_mgr"
    print("✓ user_id field present")

    assert "state" in session_info
    assert session_info["state"] == "active"
    print("✓ state field present")

    assert "current_phase" in session_info
    assert session_info["current_phase"] == "waiting"
    print("✓ current_phase field present (for device sync)")

    assert "experiment_config" in session_info
    config = session_info["experiment_config"]  # Already parsed dict
    assert config["num_ingredients"] == 2
    print("✓ experiment_config field present (already parsed)")

    assert "ingredients" in session_info
    assert len(session_info["ingredients"]) == 2
    print("✓ ingredients field present")

    assert "questionnaire_name" in session_info
    print("✓ questionnaire_name field present")


def test_session_manager_sync_state(session_id):
    """Test session manager state sync"""
    print("\n=== Testing Session Manager - Sync State ===")

    # Sync session state
    success = session_mgr.sync_session_state(session_id, "moderator")
    assert success == True
    print("✓ State synced successfully")

    # Check session_state was populated
    assert st.session_state.session_id == session_id
    assert st.session_state.device_role == "moderator"
    print("✓ Session state populated")

    # Check config values extracted
    assert st.session_state.interface_type == "grid_2d"
    assert st.session_state.num_ingredients == 2
    assert st.session_state.method == "logarithmic"
    assert len(st.session_state.ingredients) == 2
    assert st.session_state.moderator_name == "Test Moderator"
    assert st.session_state.current_phase == "waiting"
    print("✓ Config values extracted to session_state (including current_phase)")


def test_session_manager_urls_and_qr(session_id):
    """Test session manager URL generation"""
    print("\n=== Testing Session Manager - URLs and QR ===")

    # Generate URLs
    urls = session_mgr.generate_session_urls(session_id)
    assert "moderator" in urls
    assert "subject" in urls
    assert session_id in urls["moderator"]
    assert session_id in urls["subject"]
    assert "role=moderator" in urls["moderator"]
    assert "role=subject" in urls["subject"]
    print(f"✓ URLs generated:")
    print(f"  Moderator: {urls['moderator'][:60]}...")
    print(f"  Subject: {urls['subject'][:60]}...")

    # Test QR code generation
    qr_data = session_mgr.create_qr_code(urls["subject"])
    assert qr_data.startswith("data:image/png;base64,")
    assert len(qr_data) > 100  # Should have significant data
    print("✓ QR code generated")


def test_integration_full_workflow():
    """Test integrated workflow: session creation → cycles with phase sync → completion"""
    print("\n=== Testing Integrated Workflow with Phase Sync ===")

    # 1. Create session
    experiment_config = {
        "user_id": "integration_test_user",
        "num_ingredients": 2,
        "interface_type": "slider_based",
        "method": "linear",
        "ingredients": [
            {"position": 1, "name": "Sweet", "min": 0, "max": 100, "unit": "%"},
            {"position": 2, "name": "Salty", "min": 0, "max": 100, "unit": "%"}
        ],
        "question_type_id": 1,
        "bayesian_optimization": {
            "enabled": False
        }
    }

    session_id = session_mgr.create_session("Integration Test Moderator", experiment_config)
    print(f"✓ Session created: {session_id}")

    # 2. Sync state
    session_mgr.sync_session_state(session_id, "subject")
    print("✓ State synced")

    # 3. Initialize phase (reset from any previous state)
    st.session_state.phase = "waiting"
    print("✓ Phase initialized")

    # 4. Start first cycle with phase sync
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.ROBOT_PREPARING, session_id=session_id)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.TASTING, session_id=session_id)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.QUESTIONNAIRE, session_id=session_id)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.SELECTION, session_id=session_id)
    print("✓ Completed cycle 1 workflow")

    # Verify current_phase in database
    session = sql.get_session(session_id)
    assert session["current_phase"] == "selection"
    print("✓ Database shows current_phase = 'selection'")

    # 5. Save cycle 1 data
    sample_id_1 = sql.save_sample_cycle(
        session_id=session_id,
        cycle_number=1,
        ingredient_concentration={"Sweet": 50.0, "Salty": 30.0},
        selection_data={"interface_type": "slider_based", "sweet_slider": 0.6, "salty_slider": 0.4},
        questionnaire_answer={"overall_liking": 6},
        is_final=False
    )
    assert sample_id_1 is not None
    print(f"✓ Cycle 1 data saved: {sample_id_1}")

    # 6. Second cycle
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.ROBOT_PREPARING, session_id=session_id)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.TASTING, session_id=session_id)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.QUESTIONNAIRE, session_id=session_id)
    sm.ExperimentStateMachine.transition(sm.ExperimentPhase.SELECTION, session_id=session_id)

    sample_id_2 = sql.save_sample_cycle(
        session_id=session_id,
        cycle_number=2,
        ingredient_concentration={"Sweet": 70.0, "Salty": 50.0},
        selection_data={"interface_type": "slider_based", "sweet_slider": 0.8, "salty_slider": 0.6},
        questionnaire_answer={"overall_liking": 8},
        is_final=True
    )
    print(f"✓ Cycle 2 data saved: {sample_id_2}")

    # 7. Complete session (should sync both current_phase and state)
    sm.ExperimentStateMachine.transition(
        sm.ExperimentPhase.COMPLETE,
        session_id=session_id
    )
    print("✓ Session completed")

    # 8. Verify both current_phase and state in database
    session = sql.get_session(session_id)
    assert session["state"] == "completed"
    assert session["current_phase"] == "complete"
    print("✓ Database updated: state='completed', current_phase='complete'")

    # 9. Verify samples
    samples = sql.get_session_samples(session_id)
    assert len(samples) == 2
    print(f"✓ Retrieved {len(samples)} samples")

    # 10. Verify training data
    training_data = sql.get_training_data(session_id, only_final=True)
    assert len(training_data) == 1
    assert training_data.iloc[0]["Sweet"] == 70.0
    print("✓ Training data extracted correctly")


def run_all_tests():
    """Run all tests"""
    print("=" * 70)
    print("RoboTaste Phases 4-5 Tests - WITH REAL-TIME PHASE SYNC")
    print("=" * 70)

    try:
        # Setup
        setup_test_database()

        # State machine tests
        test_state_machine_phases()
        test_state_machine_transitions_with_db_sync()

        # Session manager tests
        session_id = test_session_manager_create_session()
        test_session_manager_join_session(session_id)
        test_session_manager_get_session_info(session_id)
        test_session_manager_sync_state(session_id)
        test_session_manager_urls_and_qr(session_id)

        # Integration test
        test_integration_full_workflow()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nPhases 4-5 Implementation Summary:")
        print("  ✓ State machine: 6 phases with real-time DB sync")
        print("  ✓ Session manager: No backward compatibility")
        print("  ✓ Phase sync: current_phase column synced on every transition")
        print("  ✓ Multi-device ready: All phase changes persist to database")
        print("  ✓ Full workflow tested end-to-end")
        print("\nFiles created:")
        print("  • session_manager_new.py (~305 lines, -100 from cleanup)")
        print("  • state_machine_new.py (325 lines)")
        print("  • test_phases_4_5.py (this file)")
        print("\nReady for Phase 6: moderator_interface.py updates!")
        print("=" * 70)

        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
