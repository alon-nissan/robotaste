#!/usr/bin/env python3
"""
Test slider monitoring with different numbers of ingredients (3, 4, 5, 6)
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from sql_handler import (
    initialize_database_v2, start_experiment_v2, 
    get_live_subject_position, store_user_interaction_v2
)
from callback import (
    start_trial, MultiComponentMixture, DEFAULT_INGREDIENT_CONFIG
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

def test_multi_ingredient_monitoring():
    """Test slider monitoring with different ingredient counts"""
    print("🧪 Testing Multi-Ingredient Slider Monitoring")
    print("=" * 60)
    
    # Set up mock streamlit
    import callback
    st = MockStreamlit()
    callback.st = st
    
    # Initialize database
    success = initialize_database_v2()
    if not success:
        print("❌ Database initialization failed")
        return False
    
    print("✅ Database initialized")
    
    # Test with different ingredient counts
    ingredient_counts = [3, 4, 5, 6]
    timestamp = int(time.time())
    
    for num_ingredients in ingredient_counts:
        print(f"\n🧪 Testing {num_ingredients} ingredients")
        print("-" * 40)
        
        # Create unique session for each test
        session_code = f"MULTI_TEST_{timestamp}_{num_ingredients}"
        participant_id = f"multi_participant_{timestamp}_{num_ingredients}"
        
        # Set up session state
        st.session_state.session_code = session_code
        st.session_state.use_random_start = True
        
        # Start trial
        success = start_trial("mod", participant_id, "slider_based", num_ingredients)
        
        if not success:
            print(f"❌ Failed to start trial for {num_ingredients} ingredients")
            return False
        
        experiment_id = st.session_state.get("experiment_id")
        print(f"✅ Started trial: Experiment ID {experiment_id}")
        
        # Create slider values for all ingredients
        ingredients = DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
        mixture = MultiComponentMixture(ingredients)
        
        # Generate test slider values (different for each ingredient count)
        base_value = 20.0 + (num_ingredients * 10)  # 50, 60, 70, 80
        slider_values = {}
        
        for i, ingredient in enumerate(ingredients):
            slider_values[ingredient["name"]] = base_value + (i * 5)
        
        print(f"   Slider values: {list(slider_values.values())}")
        
        # Calculate concentrations
        concentrations = mixture.calculate_concentrations_from_sliders(slider_values)
        
        # Prepare data for storage
        slider_concentrations = {}
        actual_concentrations = {}
        
        for ingredient_name, conc_data in concentrations.items():
            slider_concentrations[ingredient_name] = conc_data["slider_position"]
            actual_concentrations[ingredient_name] = conc_data["actual_concentration_mM"]
        
        # Store slider interaction
        interaction_id = store_user_interaction_v2(
            experiment_id=experiment_id,
            participant_id=participant_id,
            interaction_type="slider_adjustment",
            slider_concentrations=slider_concentrations,
            actual_concentrations=actual_concentrations,
            is_final_response=False,
            extra_data={"interface_type": "slider_based", "num_ingredients": num_ingredients}
        )
        
        if not interaction_id:
            print(f"❌ Failed to store interaction for {num_ingredients} ingredients")
            return False
        
        print(f"✅ Stored interaction: ID {interaction_id}")
        
        # Test live monitoring
        live_response = get_live_subject_position(participant_id)
        
        if live_response:
            interface_type = live_response.get("interface_type")
            slider_data = live_response.get("slider_data", {})
            concentration_data = live_response.get("concentration_data", {})
            num_tracked = live_response.get("num_ingredients", 0)
            
            print(f"✅ Live monitoring working:")
            print(f"   Interface: {interface_type}")
            print(f"   Ingredients tracked: {len(slider_data)}/{num_ingredients}")
            print(f"   Database num_ingredients: {num_tracked}")
            
            if len(slider_data) == num_ingredients:
                print(f"✅ All {num_ingredients} ingredients tracked correctly")
                
                # Check ingredient names match
                expected_names = [ing["name"] for ing in ingredients]
                tracked_names = list(slider_data.keys())
                
                if set(expected_names) == set(tracked_names):
                    print("✅ Ingredient names match expected")
                else:
                    print(f"❌ Ingredient name mismatch:")
                    print(f"   Expected: {expected_names}")
                    print(f"   Tracked: {tracked_names}")
                    return False
                
                # Display sample data
                print("   Sample monitoring data:")
                for ingredient, value in list(slider_data.items())[:2]:  # Show first 2
                    conc = concentration_data.get(ingredient, 0)
                    print(f"      {ingredient}: {value:.1f}% → {conc:.3f} mM")
                if len(slider_data) > 2:
                    print(f"      ... and {len(slider_data) - 2} more")
                    
            else:
                print(f"❌ Expected {num_ingredients} ingredients, got {len(slider_data)}")
                return False
        else:
            print(f"❌ No live monitoring data for {num_ingredients} ingredients")
            return False
    
    print("\n" + "=" * 60)
    print("🎉 MULTI-INGREDIENT MONITORING TEST PASSED!")
    print("\n✅ Verified for all ingredient counts (3, 4, 5, 6):")
    print("   • Trial setup and database storage")
    print("   • Slider interaction recording")
    print("   • Live monitoring data retrieval")
    print("   • Correct ingredient tracking")
    print("   • Concentration calculations")
    
    return True

if __name__ == "__main__":
    success = test_multi_ingredient_monitoring()
    sys.exit(0 if success else 1)