#!/usr/bin/env python3
"""
Test slider interface data recording specifically
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sql_handler import initialize_database_v2, start_experiment_v2, get_experiment_data_v2
from callback import save_slider_trial, MultiComponentMixture, DEFAULT_INGREDIENT_CONFIG
import time

# Mock streamlit session state
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
    def success(self, msg): print(f"SUCCESS: {msg}")

def test_slider_recording():
    """Test slider interface data recording"""
    print("🧪 Testing Slider Interface Data Recording")
    print("=" * 50)
    
    # Set up mock streamlit
    import callback
    st = MockStreamlit()
    callback.st = st
    
    # Initialize database
    success = initialize_database_v2()
    if not success:
        print("❌ Database initialization failed")
        return False
    
    # Create test experiment
    timestamp = int(time.time())
    session_code = f"SLIDER_TEST_{timestamp}"
    participant_id = f"slider_participant_{timestamp}"
    
    experiment_id = start_experiment_v2(
        session_code=session_code,
        participant_id=participant_id,
        interface_type="slider_based",
        method="slider_based",
        num_ingredients=4,
        use_random_start=True,
        ingredient_config=DEFAULT_INGREDIENT_CONFIG[:4]
    )
    
    if not experiment_id:
        print("❌ Failed to create test experiment")
        return False
    
    print(f"✅ Created test experiment: {experiment_id}")
    
    # Set up session state like a real trial
    st.session_state.experiment_id = experiment_id
    st.session_state.participant = participant_id
    st.session_state.trial_start_time = time.perf_counter() - 5.0  # Simulate 5 second trial
    
    # Create test slider concentrations (simulate user moving sliders)
    ingredients = DEFAULT_INGREDIENT_CONFIG[:4]
    mixture = MultiComponentMixture(ingredients)
    
    test_slider_values = {
        "Sugar": 45.5,
        "Salt": 67.2,
        "Citric Acid": 23.8,
        "Caffeine": 89.1
    }
    
    # Calculate concentrations (this is what the UI does)
    concentrations = mixture.calculate_concentrations_from_sliders(test_slider_values)
    print(f"📊 Test concentrations: {list(concentrations.keys())}")
    
    # Test the save_slider_trial function
    print("💾 Testing save_slider_trial function...")
    success = save_slider_trial(participant_id, concentrations, "slider_based")
    
    if success:
        print("✅ save_slider_trial returned True")
    else:
        print("❌ save_slider_trial returned False")
        return False
    
    # Check if data was actually saved to database
    print("🔍 Checking database for saved data...")
    experiment_data = get_experiment_data_v2(session_code, participant_id)
    
    if experiment_data and experiment_data.get('interactions'):
        interactions = experiment_data['interactions']
        print(f"✅ Found {len(interactions)} interactions in database")
        
        # Check for slider data
        for i, interaction in enumerate(interactions):
            print(f"   Interaction {i+1}: type='{interaction.get('interaction_type')}', "
                  f"slider_data={bool(interaction.get('slider_concentrations'))}")
        
        return True
    else:
        print("❌ No interactions found in database")
        print(f"   Experiment data: {experiment_data}")
        return False

if __name__ == "__main__":
    success = test_slider_recording()
    if success:
        print("\n🎉 Slider recording test PASSED")
    else:
        print("\n❌ Slider recording test FAILED")
    sys.exit(0 if success else 1)