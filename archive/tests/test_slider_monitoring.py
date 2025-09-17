#!/usr/bin/env python3
"""
Test slider interface live monitoring specifically
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sql_handler import (
    initialize_database_v2, start_experiment_v2, 
    get_live_subject_position, get_latest_slider_interaction,
    store_user_interaction_v2
)
from callback import DEFAULT_INGREDIENT_CONFIG
import time

def test_slider_monitoring():
    """Test slider interface live monitoring"""
    print("🧪 Testing Slider Interface Live Monitoring")
    print("=" * 50)
    
    # Initialize database
    success = initialize_database_v2()
    if not success:
        print("❌ Database initialization failed")
        return False
    
    # Create test experiment
    timestamp = int(time.time())
    session_code = f"MONITOR_TEST_{timestamp}"
    participant_id = f"monitor_participant_{timestamp}"
    
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
    
    # Test 1: Check monitoring with no interactions yet
    print("\n🔍 Test 1: Monitoring with no interactions")
    response = get_live_subject_position(participant_id)
    
    if response is None:
        print("✅ No response found (as expected)")
    else:
        print(f"⚠️ Unexpected response found: {response}")
    
    # Test 2: Add a slider interaction and test monitoring
    print("\n🔍 Test 2: Monitoring after slider interaction")
    test_slider_concentrations = {
        "Sugar": 45.5,
        "Salt": 67.2,
        "Citric Acid": 23.8,
        "Caffeine": 89.1
    }
    
    test_actual_concentrations = {
        "Sugar": 33.15,
        "Salt": 6.82,
        "Citric Acid": 1.21,
        "Caffeine": 0.89
    }
    
    # Store a user interaction (simulating slider movement)
    interaction_id = store_user_interaction_v2(
        experiment_id=experiment_id,
        participant_id=participant_id,
        interaction_type="slider_adjustment",
        slider_concentrations=test_slider_concentrations,
        actual_concentrations=test_actual_concentrations,
        reaction_time_ms=3000,
        is_final_response=False,
        extra_data={"interface_type": "slider_based"}
    )
    
    if interaction_id:
        print(f"✅ Stored slider interaction: {interaction_id}")
    else:
        print("❌ Failed to store slider interaction")
        return False
    
    # Test the direct function
    print("\n🔍 Test 3: Testing get_latest_slider_interaction directly")
    slider_response = get_latest_slider_interaction(participant_id)
    
    if slider_response:
        print("✅ get_latest_slider_interaction returned data:")
        print(f"   Interface: {slider_response.get('interface_type')}")
        print(f"   Submitted: {slider_response.get('is_submitted')}")
        print(f"   Slider data: {len(slider_response.get('slider_data', {}))}")
        print(f"   Concentration data: {len(slider_response.get('concentration_data', {}))}")
    else:
        print("❌ get_latest_slider_interaction returned None")
        return False
    
    # Test the main monitoring function
    print("\n🔍 Test 4: Testing get_live_subject_position")
    live_response = get_live_subject_position(participant_id)
    
    if live_response:
        print("✅ get_live_subject_position returned data:")
        print(f"   Interface: {live_response.get('interface_type')}")
        print(f"   Method: {live_response.get('method')}")
        print(f"   Submitted: {live_response.get('is_submitted')}")
        print(f"   Has slider_data: {'slider_data' in live_response}")
        print(f"   Has concentration_data: {'concentration_data' in live_response}")
        
        if 'slider_data' in live_response:
            print(f"   Slider data keys: {list(live_response['slider_data'].keys())}")
            
        return True
    else:
        print("❌ get_live_subject_position returned None")
        return False

if __name__ == "__main__":
    success = test_slider_monitoring()
    if success:
        print("\n🎉 Slider monitoring test PASSED")
    else:
        print("\n❌ Slider monitoring test FAILED")
    sys.exit(0 if success else 1)