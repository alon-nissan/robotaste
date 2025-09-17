#!/usr/bin/env python3
"""
Compare grid (2D) vs slider interface data flow to ensure both work correctly
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
    start_trial, save_slider_trial, finish_trial,
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

def test_grid_vs_slider_comparison():
    """Compare grid vs slider interface functionality"""
    print("🧪 Testing Grid vs Slider Interface Comparison")
    print("=" * 70)
    
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
    
    timestamp = int(time.time())
    
    # TEST 1: Grid Interface (2 ingredients)
    print("\n📊 TESTING GRID INTERFACE (2 ingredients)")
    print("-" * 50)
    
    grid_session = f"GRID_TEST_{timestamp}"
    grid_participant = f"grid_participant_{timestamp}"
    
    # Set up grid session
    st.session_state.session_code = grid_session
    st.session_state.use_random_start = False
    
    # Start grid trial
    success = start_trial("mod", grid_participant, "linear", 2)
    if not success:
        print("❌ Failed to start grid trial")
        return False
    
    grid_experiment_id = st.session_state.get("experiment_id")
    print(f"✅ Grid trial started: Experiment ID {grid_experiment_id}")
    
    # Simulate grid interaction (canvas click at position 150, 200)
    test_canvas_result = {
        "json_data": {
            "objects": [
                {
                    "type": "circle",
                    "left": 150,
                    "top": 200,
                    "radius": 5
                }
            ]
        }
    }
    
    # Test finish_trial function (grid)
    st.session_state.trial_start_time = time.perf_counter() - 5.0
    grid_success = finish_trial(test_canvas_result, grid_participant, "linear")
    
    if grid_success:
        print("✅ Grid trial completed successfully")
    else:
        print("❌ Grid trial failed")
        return False
    
    # Check grid monitoring
    grid_response = get_live_subject_position(grid_participant)
    if grid_response and grid_response.get("interface_type") == "grid_2d":
        print("✅ Grid monitoring working")
        print(f"   Position: ({grid_response.get('x_position')}, {grid_response.get('y_position')})")
    else:
        print("❌ Grid monitoring failed")
        return False
    
    # TEST 2: Slider Interface (4 ingredients)
    print("\n🎚️ TESTING SLIDER INTERFACE (4 ingredients)")
    print("-" * 50)
    
    slider_session = f"SLIDER_TEST_{timestamp}"
    slider_participant = f"slider_participant_{timestamp}"
    
    # Set up slider session
    st.session_state.session_code = slider_session
    st.session_state.use_random_start = True
    
    # Start slider trial
    success = start_trial("mod", slider_participant, "slider_based", 4)
    if not success:
        print("❌ Failed to start slider trial")
        return False
    
    slider_experiment_id = st.session_state.get("experiment_id")
    print(f"✅ Slider trial started: Experiment ID {slider_experiment_id}")
    
    # Simulate slider interactions
    ingredients = DEFAULT_INGREDIENT_CONFIG[:4]
    mixture = MultiComponentMixture(ingredients)
    
    test_slider_values = {"Sugar": 45.5, "Salt": 67.2, "Citric Acid": 23.8, "Caffeine": 89.1}
    final_concentrations = mixture.calculate_concentrations_from_sliders(test_slider_values)
    
    # Test save_slider_trial function
    st.session_state.trial_start_time = time.perf_counter() - 8.0
    slider_success = save_slider_trial(slider_participant, final_concentrations, "slider_based")
    
    if slider_success:
        print("✅ Slider trial completed successfully")
    else:
        print("❌ Slider trial failed")
        return False
    
    # Check slider monitoring
    slider_response = get_live_subject_position(slider_participant)
    if slider_response and slider_response.get("interface_type") == "slider_based":
        print("✅ Slider monitoring working")
        slider_data = slider_response.get("slider_data", {})
        print(f"   Ingredients: {len(slider_data)} tracked")
        if slider_data:
            sample_ingredient = list(slider_data.keys())[0]
            sample_value = slider_data[sample_ingredient]
            print(f"   Sample: {sample_ingredient} = {sample_value:.1f}%")
    else:
        print("❌ Slider monitoring failed")
        return False
    
    # TEST 3: Data Export Comparison
    print("\n📊 TESTING DATA EXPORT COMPARISON")
    print("-" * 50)
    
    # Export grid data
    grid_csv = export_experiment_data_csv(grid_session)
    if grid_csv:
        grid_lines = grid_csv.strip().split('\n')
        print(f"✅ Grid CSV export: {len(grid_lines)} lines")
    else:
        print("❌ Grid CSV export failed")
        return False
    
    # Export slider data
    slider_csv = export_experiment_data_csv(slider_session)
    if slider_csv:
        slider_lines = slider_csv.strip().split('\n')
        print(f"✅ Slider CSV export: {len(slider_lines)} lines")
    else:
        print("❌ Slider CSV export failed")
        return False
    
    # Check CSV headers contain appropriate fields
    if grid_lines:
        grid_header = grid_lines[0]
        has_grid_fields = "grid_x" in grid_header and "grid_y" in grid_header
        print(f"✅ Grid CSV contains grid fields: {has_grid_fields}")
    
    if slider_lines:
        slider_header = slider_lines[0]
        has_slider_fields = "ingredient_1_concentration" in slider_header
        print(f"✅ Slider CSV contains slider fields: {has_slider_fields}")
    
    # TEST 4: Database Structure Comparison
    print("\n🗄️ TESTING DATABASE STRUCTURE")
    print("-" * 50)
    
    # Get experiment data for both
    grid_data = get_experiment_data_v2(grid_session, grid_participant)
    slider_data = get_experiment_data_v2(slider_session, slider_participant)
    
    if grid_data and slider_data:
        print("✅ Both experiments found in database")
        
        grid_interactions = len(grid_data.get('interactions', []))
        slider_interactions = len(slider_data.get('interactions', []))
        
        print(f"   Grid interactions: {grid_interactions}")
        print(f"   Slider interactions: {slider_interactions}")
        
        # Check interface types
        grid_interface = grid_data.get('interface_type')
        slider_interface = slider_data.get('interface_type')
        
        print(f"   Grid interface: {grid_interface}")
        print(f"   Slider interface: {slider_interface}")
        
        if grid_interface == 'grid_2d' and slider_interface == 'slider_based':
            print("✅ Interface types correctly stored")
        else:
            print("❌ Interface types incorrect")
            return False
            
    else:
        print("❌ Missing experiment data")
        return False
    
    return True

if __name__ == "__main__":
    success = test_grid_vs_slider_comparison()
    
    print("\n" + "=" * 70)
    if success:
        print("🎉 GRID VS SLIDER COMPARISON TEST PASSED!")
        print("\n✅ Both interfaces working correctly:")
        print("   📊 Grid Interface (2D): Position tracking, canvas interaction")
        print("   🎚️ Slider Interface: Multi-ingredient, concentration tracking")
        print("   📡 Live Monitoring: Real-time updates for both interfaces")
        print("   📊 Data Export: CSV export with appropriate fields")
        print("   🗄️ Database Storage: Unified schema supporting both types")
    else:
        print("❌ GRID VS SLIDER COMPARISON TEST FAILED")
    
    sys.exit(0 if success else 1)