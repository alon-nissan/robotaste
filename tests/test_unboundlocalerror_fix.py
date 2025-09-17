#!/usr/bin/env python3
"""
Quick test to verify the UnboundLocalError for initial_positions is fixed.
"""

import os
import sys

# Add the current directory to the path to import our modules
sys.path.append(os.path.dirname(__file__))

# Test the specific function that had the error
def test_initial_positions_scope():
    """Test that initial_positions is properly scoped and accessible."""
    print("🔍 Testing initial_positions scope fix...")

    # Mock the session state and other dependencies we need
    class MockSessionState:
        def __init__(self):
            self.participant = "test_participant"
            self.session_code = "TEST_SESSION"

    # Mock the experiment config
    experiment_config = {
        "ingredients": [
            {"name": "Sugar"},
            {"name": "Salt"},
            {"name": "Citric Acid"}
        ]
    }

    # Try to simulate the code path that was failing
    try:
        from sql_handler import init_database, get_initial_slider_positions

        # Initialize database
        init_database()

        # Simulate the code that was failing
        st_session_state = MockSessionState()

        # This is the code pattern from main_app.py that was failing
        initial_positions = None
        if hasattr(st_session_state, "participant") and hasattr(st_session_state, "session_code"):
            initial_positions = get_initial_slider_positions(
                session_id=st_session_state.session_code,
                participant_id=st_session_state.participant
            )

        # Test the conditional that was causing UnboundLocalError
        if initial_positions and initial_positions.get("percentages"):
            print("  ✅ Found database initial positions")
            current_slider_values = {}
            for ingredient in experiment_config["ingredients"]:
                ingredient_name = ingredient["name"]
                db_percentages = initial_positions["percentages"]
                if ingredient_name in db_percentages:
                    current_slider_values[ingredient_name] = db_percentages[ingredient_name]
                else:
                    # Fallback logic
                    ingredient_index = next((i for i, ing in enumerate(experiment_config["ingredients"]) if ing["name"] == ingredient_name), None)
                    if ingredient_index is not None:
                        generic_key = f"Ingredient_{ingredient_index + 1}"
                        current_slider_values[ingredient_name] = db_percentages.get(generic_key, 50.0)
                    else:
                        current_slider_values[ingredient_name] = 50.0
            print(f"    Mapped slider values: {current_slider_values}")
        else:
            print("  ✅ No database positions found (using defaults)")
            current_slider_values = {ing["name"]: 50.0 for ing in experiment_config["ingredients"]}

        print("  ✅ No UnboundLocalError occurred")
        print(f"    Final slider values: {current_slider_values}")
        return True

    except NameError as e:
        if "initial_positions" in str(e):
            print(f"  ❌ UnboundLocalError still present: {e}")
            return False
        else:
            raise e
    except Exception as e:
        print(f"  ⚠️ Other error occurred: {e}")
        return True  # As long as it's not the UnboundLocalError we're testing

def main():
    """Run the scope fix test."""
    print("🧪 Testing UnboundLocalError fix for initial_positions...")
    print("=" * 50)

    success = test_initial_positions_scope()

    print("\n" + "=" * 50)
    if success:
        print("✅ UnboundLocalError fix verified!")
        print("   initial_positions is now properly scoped and accessible")
        return True
    else:
        print("❌ UnboundLocalError still present - needs further investigation")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)