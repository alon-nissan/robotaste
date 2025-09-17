#!/usr/bin/env python3
"""
Comprehensive workflow test for RoboTaste application
Tests the entire flow from moderator setup to subject response
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sql_handler import (
    initialize_database_v2,
    start_experiment_v2, 
    store_initial_positions_v2,
    store_user_interaction_v2,
    get_initial_positions_v2,
    get_experiment_data_v2,
    export_experiment_data_csv
)
from callback import (
    start_trial,
    save_slider_trial,
    get_stored_random_values,
    ensure_random_values_loaded,
    DEFAULT_INGREDIENT_CONFIG,
    MultiComponentMixture
)
import streamlit as st

# Mock streamlit session state for testing
class MockSessionState:
    def __init__(self):
        self.data = {}
    
    def get(self, key, default=None):
        return self.data.get(key, default)
    
    def __setattr__(self, name, value):
        if name == 'data':
            super().__setattr__(name, value)
        else:
            self.data[name] = value
    
    def __getattr__(self, name):
        return self.data.get(name)
    
    def keys(self):
        return self.data.keys()

# Mock st module for testing
class MockStreamlit:
    def __init__(self):
        self.session_state = MockSessionState()
    
    def error(self, msg): print(f"ERROR: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def info(self, msg): print(f"INFO: {msg}")
    def success(self, msg): print(f"SUCCESS: {msg}")

def test_database_initialization():
    """Test database v2.0 initialization"""
    print("🔧 Testing Database Initialization")
    success = initialize_database_v2()
    if success:
        print("   ✅ Database initialized successfully")
        return True
    else:
        print("   ❌ Database initialization failed")
        return False

def test_moderator_workflow():
    """Test complete moderator workflow"""
    print("\n👨‍💼 Testing Moderator Workflow")
    
    # Mock streamlit for testing
    global st
    st = MockStreamlit()
    
    # Import callback module and replace its st with our mock
    import callback
    callback.st = st
    
    # Test 1: Session setup - use unique identifiers for each test run
    import time
    timestamp = int(time.time())
    st.session_state.session_code = f"TEST_WORKFLOW_{timestamp}"
    st.session_state.use_random_start = True
    print(f"   📋 Session code: {st.session_state.session_code}")
    
    # Test 2: Start trial for 4-ingredient experiment
    print("   🚀 Starting 4-ingredient trial with random start...")
    success = start_trial("mod", f"test_participant_{timestamp}", "slider_based", 4)
    
    if success:
        print("   ✅ Trial started successfully")
        print(f"   🆔 Experiment ID: {st.session_state.experiment_id}")
        print(f"   🎲 Random values: {st.session_state.random_slider_values}")
        return True
    else:
        print("   ❌ Trial start failed")
        return False

def test_random_start_persistence():
    """Test that random start values are properly stored and retrieved"""
    print("\n🎲 Testing Random Start Persistence")
    
    experiment_id = st.session_state.get("experiment_id")
    if not experiment_id:
        print("   ❌ No experiment ID available")
        return False
    
    # Test retrieval of stored random values  
    # Get the participant_id from session state (it contains the timestamp)
    participant_id = st.session_state.get("participant", "test_participant")
    stored_values = get_stored_random_values(participant_id)
    
    if stored_values:
        print(f"   ✅ Random values retrieved: {stored_values}")
        
        # Compare with session state values
        session_values = st.session_state.get("random_slider_values", {})
        if stored_values == session_values:
            print("   ✅ Database and session values match")
            return True
        else:
            print(f"   ⚠️ Mismatch - Session: {session_values}")
            return False
    else:
        print("   ❌ No random values retrieved from database")
        return False

def test_slider_concentration_calculations():
    """Test slider concentration calculations"""
    print("\n🧪 Testing Slider Concentration Calculations")
    
    # Test slider values
    test_slider_values = {
        "Sugar": 45.5,
        "Salt": 67.2, 
        "Citric Acid": 23.8,
        "Caffeine": 89.1
    }
    
    # Create mixture for testing
    ingredients = DEFAULT_INGREDIENT_CONFIG[:4]
    mixture = MultiComponentMixture(ingredients)
    
    try:
        concentrations = mixture.calculate_concentrations_from_sliders(test_slider_values)
        
        print("   ✅ Concentration calculations successful:")
        for ingredient, conc_data in concentrations.items():
            actual_conc = conc_data["actual_concentration_mM"]
            slider_pos = conc_data["slider_position"]
            print(f"      {ingredient}: {slider_pos:.1f}% → {actual_conc:.2f} mM")
        
        return True
    except Exception as e:
        print(f"   ❌ Concentration calculation failed: {e}")
        return False

def test_data_storage():
    """Test storing user interactions"""
    print("\n💾 Testing Data Storage")
    
    experiment_id = st.session_state.get("experiment_id")
    if not experiment_id:
        print("   ❌ No experiment ID available")
        return False
    
    # Test slider concentrations
    slider_concentrations = {
        "Sugar": 45.5,
        "Salt": 67.2,
        "Citric Acid": 23.8,
        "Caffeine": 89.1
    }
    
    actual_concentrations = {
        "Sugar": 33.15,
        "Salt": 6.82,
        "Citric Acid": 1.21,
        "Caffeine": 0.89
    }
    
    # Store user interaction
    participant_id = st.session_state.get("participant", "test_participant")
    interaction_id = store_user_interaction_v2(
        experiment_id=experiment_id,
        participant_id=participant_id,
        interaction_type="final_selection",
        slider_concentrations=slider_concentrations,
        actual_concentrations=actual_concentrations,
        reaction_time_ms=2500,
        is_final_response=True,
        extra_data={"test": "workflow"}
    )
    
    if interaction_id:
        print(f"   ✅ User interaction stored: ID {interaction_id}")
        return True
    else:
        print("   ❌ Failed to store user interaction")
        return False

def test_data_export():
    """Test CSV data export"""
    print("\n📊 Testing Data Export")
    
    session_code = st.session_state.get("session_code", "TEST_WORKFLOW")
    csv_data = export_experiment_data_csv(session_code)
    
    if csv_data:
        lines = csv_data.strip().split('\n')
        print(f"   ✅ CSV export successful: {len(lines)} lines")
        
        # Check for expected content
        header = lines[0] if lines else ""
        if "participant_id" in header and "ingredient_1_concentration" in header:
            print("   ✅ CSV contains expected columns")
            return True
        else:
            print("   ⚠️ CSV missing expected columns")
            return False
    else:
        print("   ❌ CSV export failed")
        return False

def test_monitoring_data_retrieval():
    """Test data retrieval for monitoring"""
    print("\n📡 Testing Monitoring Data Retrieval")
    
    session_code = st.session_state.get("session_code", "TEST_WORKFLOW")
    participant_id = st.session_state.get("participant", "test_participant")
    experiment_data = get_experiment_data_v2(session_code, participant_id)
    
    if experiment_data:
        print("   ✅ Experiment data retrieved successfully")
        print(f"      Interface: {experiment_data.get('interface_type')}")
        print(f"      Ingredients: {experiment_data.get('num_ingredients')}")
        print(f"      Interactions: {len(experiment_data.get('interactions', []))}")
        
        # Check for random start data
        if experiment_data.get('initial_positions'):
            print("   ✅ Initial positions found")
            return True
        else:
            print("   ⚠️ No initial positions found")
            return False
    else:
        print("   ❌ Failed to retrieve experiment data")
        return False

def main():
    print("🧪 RoboTaste Complete Workflow Test")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 7
    
    try:
        # Test 1: Database initialization
        if test_database_initialization():
            tests_passed += 1
        
        # Test 2: Moderator workflow
        if test_moderator_workflow():
            tests_passed += 1
        
        # Test 3: Random start persistence
        if test_random_start_persistence():
            tests_passed += 1
        
        # Test 4: Concentration calculations
        if test_slider_concentration_calculations():
            tests_passed += 1
        
        # Test 5: Data storage
        if test_data_storage():
            tests_passed += 1
        
        # Test 6: Data export
        if test_data_export():
            tests_passed += 1
        
        # Test 7: Monitoring data retrieval
        if test_monitoring_data_retrieval():
            tests_passed += 1
        
        print("\n" + "=" * 50)
        print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
        
        if tests_passed == total_tests:
            print("🎉 ALL TESTS PASSED! Application is ready for use.")
            print("\n✅ Verified Functionality:")
            print("   • Database v2.0 initialization")
            print("   • Moderator trial start workflow") 
            print("   • Random start value persistence")
            print("   • Multi-ingredient concentration calculations")
            print("   • User interaction data storage")
            print("   • CSV data export for researchers")
            print("   • Real-time monitoring data retrieval")
            return True
        else:
            failed_tests = total_tests - tests_passed
            print(f"⚠️ {failed_tests} test(s) failed. Review issues above.")
            return False
        
    except Exception as e:
        print(f"\n❌ Test suite failed with error: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)