#!/usr/bin/env python3
"""
Test complete slider workflow: setup -> interaction -> monitoring -> recording
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sql_handler import (
    initialize_database_v2, start_experiment_v2, 
    get_live_subject_position, store_user_interaction_v2,
    get_experiment_data_v2, export_experiment_data_csv
)
from callback import (
    start_trial, save_slider_trial, 
    MultiComponentMixture, DEFAULT_INGREDIENT_CONFIG
)
import time

# Mock streamlit for testing
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

class MockStreamlit:
    def __init__(self):
        self.session_state = MockSessionState()
    
    def error(self, msg): print(f"ERROR: {msg}")
    def warning(self, msg): print(f"WARNING: {msg}")
    def info(self, msg): print(f"INFO: {msg}")
    def success(self, msg): print(f"SUCCESS: {msg}")
    def rerun(self): pass

def test_complete_slider_workflow():
    """Test complete slider workflow end-to-end"""
    print("🧪 Testing Complete Slider Workflow")
    print("=" * 60)
    
    # Set up mock streamlit
    import callback, main_app
    st = MockStreamlit()
    callback.st = st
    
    # Initialize database
    success = initialize_database_v2()
    if not success:
        print("❌ Database initialization failed")
        return False
    
    print("✅ Database initialized")
    
    # STEP 1: Moderator Setup
    print("\n📋 STEP 1: Moderator Setup")
    timestamp = int(time.time())
    session_code = f"COMPLETE_TEST_{timestamp}"
    participant_id = f"complete_participant_{timestamp}"
    
    # Set up session state like a real moderator session
    st.session_state.session_code = session_code
    st.session_state.use_random_start = True
    
    # Start trial (this is what happens when moderator clicks "Start Trial")
    print(f"   Setting up session: {session_code}")
    success = start_trial("mod", participant_id, "slider_based", 4)
    
    if not success:
        print("❌ Failed to start trial")
        return False
    
    print(f"✅ Trial started successfully")
    print(f"   Experiment ID: {st.session_state.get('experiment_id')}")
    print(f"   Random start values: {len(st.session_state.get('random_slider_values', {}))}")
    
    # STEP 2: Subject Slider Interactions
    print("\n🎚️ STEP 2: Subject Slider Interactions")
    
    # Simulate subject moving sliders (what happens in the UI)
    ingredients = DEFAULT_INGREDIENT_CONFIG[:4]
    mixture = MultiComponentMixture(ingredients)
    
    # Simulate multiple slider adjustments
    slider_movements = [
        {"Sugar": 30.0, "Salt": 40.0, "Citric Acid": 50.0, "Caffeine": 60.0},
        {"Sugar": 35.0, "Salt": 45.0, "Citric Acid": 55.0, "Caffeine": 65.0},
        {"Sugar": 40.0, "Salt": 50.0, "Citric Acid": 60.0, "Caffeine": 70.0}
    ]
    
    experiment_id = st.session_state.get("experiment_id")
    
    for i, slider_values in enumerate(slider_movements, 1):
        print(f"   Movement {i}: {slider_values}")
        
        # Calculate concentrations
        concentrations = mixture.calculate_concentrations_from_sliders(slider_values)
        
        # Prepare data like the UI does
        slider_concentrations = {}
        actual_concentrations = {}
        
        for ingredient_name, conc_data in concentrations.items():
            slider_concentrations[ingredient_name] = conc_data["slider_position"]
            actual_concentrations[ingredient_name] = conc_data["actual_concentration_mM"]
        
        # Store real-time adjustment
        interaction_id = store_user_interaction_v2(
            experiment_id=experiment_id,
            participant_id=participant_id,
            interaction_type="slider_adjustment",
            slider_concentrations=slider_concentrations,
            actual_concentrations=actual_concentrations,
            is_final_response=False,
            extra_data={"interface_type": "slider_based", "movement_number": i}
        )
        
        if interaction_id:
            print(f"   ✅ Stored movement {i}: ID {interaction_id}")
        else:
            print(f"   ❌ Failed to store movement {i}")
            return False
    
    # STEP 3: Live Monitoring
    print("\n📺 STEP 3: Live Monitoring Test")
    
    # Test what moderator would see in live monitoring
    live_response = get_live_subject_position(participant_id)
    
    if live_response:
        interface_type = live_response.get("interface_type")
        slider_data = live_response.get("slider_data", {})
        concentration_data = live_response.get("concentration_data", {})
        is_submitted = live_response.get("is_submitted")
        
        print(f"✅ Live monitoring active")
        print(f"   Interface: {interface_type}")
        print(f"   Status: {'Final' if is_submitted else 'Live'}")
        print(f"   Ingredients tracked: {len(slider_data)}")
        
        if slider_data:
            print("   Current slider positions:")
            for ingredient, value in slider_data.items():
                conc = concentration_data.get(ingredient, 0)
                print(f"      {ingredient}: {value:.1f}% → {conc:.3f} mM")
    else:
        print("❌ No live monitoring data found")
        return False
    
    # STEP 4: Final Submission
    print("\n✅ STEP 4: Final Submission")
    
    # Final slider values
    final_slider_values = {"Sugar": 45.5, "Salt": 67.2, "Citric Acid": 23.8, "Caffeine": 89.1}
    final_concentrations = mixture.calculate_concentrations_from_sliders(final_slider_values)
    
    # Save final submission (this is what happens when user clicks "Finish")
    st.session_state.trial_start_time = time.perf_counter() - 10.0  # 10 second trial
    success = save_slider_trial(participant_id, final_concentrations, "slider_based")
    
    if success:
        print("✅ Final submission saved successfully")
    else:
        print("❌ Failed to save final submission")
        return False
    
    # STEP 5: Data Verification
    print("\n🔍 STEP 5: Data Verification")
    
    # Get complete experiment data
    experiment_data = get_experiment_data_v2(session_code, participant_id)
    
    if experiment_data:
        interactions = experiment_data.get('interactions', [])
        print(f"✅ Found {len(interactions)} total interactions")
        
        # Count different types
        adjustments = [i for i in interactions if i.get('interaction_type') == 'slider_adjustment']
        finals = [i for i in interactions if i.get('interaction_type') == 'final_selection']
        
        print(f"   Slider adjustments: {len(adjustments)}")
        print(f"   Final selections: {len(finals)}")
        
        if len(adjustments) >= 3 and len(finals) >= 1:
            print("✅ Correct interaction types stored")
        else:
            print("❌ Missing expected interactions")
            return False
        
    else:
        print("❌ No experiment data found")
        return False
    
    # STEP 6: Export Test
    print("\n📊 STEP 6: Data Export Test")
    
    csv_data = export_experiment_data_csv(session_code)
    if csv_data:
        lines = csv_data.strip().split('\n')
        print(f"✅ CSV export successful: {len(lines)} lines")
        
        # Check for slider data in CSV
        header = lines[0] if lines else ""
        if "ingredient_1_concentration" in header:
            print("✅ CSV contains slider concentration data")
        else:
            print("❌ CSV missing slider data columns")
            return False
    else:
        print("❌ CSV export failed")
        return False
    
    return True

if __name__ == "__main__":
    success = test_complete_slider_workflow()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 COMPLETE SLIDER WORKFLOW TEST PASSED!")
        print("\n✅ Verified Functionality:")
        print("   • Moderator trial setup")
        print("   • Real-time slider adjustments with monitoring")
        print("   • Live position tracking")
        print("   • Final submission recording")
        print("   • Complete data export")
    else:
        print("❌ COMPLETE SLIDER WORKFLOW TEST FAILED")
    
    sys.exit(0 if success else 1)