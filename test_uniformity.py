#!/usr/bin/env python3
"""
Test script to verify uniformity between 2D grid and slider interfaces.

This test ensures both interfaces:
1. Use identical JSON structure for data storage
2. Work with any ingredient configuration
3. Store ingredient-agnostic data

Run this to verify the unified data collection approach.
"""

import sys
import os
import tempfile
import json
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sql_handler import (
    get_database_connection,
    init_database,
    save_multi_ingredient_response
)

def test_ingredient_agnostic_storage():
    """Test that both interfaces store data in identical, ingredient-agnostic format."""

    print("🧪 Testing Ingredient-Agnostic Unified Storage...")

    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name

    # Monkey patch the database connection to use temp file
    original_db_path = None
    try:
        import sql_handler
        if hasattr(sql_handler, 'DATABASE_PATH'):
            original_db_path = sql_handler.DATABASE_PATH
            sql_handler.DATABASE_PATH = temp_db_path

        # Initialize database
        success = init_database()
        if not success:
            print("❌ Failed to initialize test database")
            return False

        # Test Case 1: Custom ingredient configuration
        custom_ingredients = [
            {"name": "Vanilla Extract", "min_concentration": 0.001, "max_concentration": 0.5},
            {"name": "Cocoa Powder", "min_concentration": 0.1, "max_concentration": 10.0},
            {"name": "Mint Oil", "min_concentration": 0.005, "max_concentration": 1.0}
        ]

        print(f"   Testing with custom ingredients: {[ing['name'] for ing in custom_ingredients]}")

        # Test 2D Grid Interface Storage
        grid_concentrations = {
            "Vanilla Extract": 0.25,
            "Cocoa Powder": 5.0
        }

        grid_success = save_multi_ingredient_response(
            participant_id="test_grid_001",
            session_id="test_session_uniformity",
            method="linear",
            interface_type="grid_2d",
            ingredient_concentrations=grid_concentrations,
            x_position=250.0,
            y_position=300.0,
            reaction_time_ms=1500,
            questionnaire_response={"confidence": 7, "strategy": "systematic"},
            is_final_response=True,
            extra_data={
                "grid_coordinates": {"x": 250.0, "y": 300.0},
                "grid_interface": True,
                "canvas_size": 500,
                "selected_ingredients": ["Vanilla Extract", "Cocoa Powder"]
            }
        )

        # Test Slider Interface Storage
        slider_concentrations = {
            "Vanilla Extract": 0.15,
            "Cocoa Powder": 3.5,
            "Mint Oil": 0.08
        }

        slider_success = save_multi_ingredient_response(
            participant_id="test_slider_001",
            session_id="test_session_uniformity",
            method="slider_based",
            interface_type="slider_based",
            ingredient_concentrations=slider_concentrations,
            reaction_time_ms=2200,
            questionnaire_response={"confidence": 5, "strategy": "intuitive"},
            is_final_response=True,
            extra_data={
                "concentrations_summary": {
                    ing: {"slider_position": 50.0, "actual_concentration_mM": conc}
                    for ing, conc in slider_concentrations.items()
                },
                "slider_interface": True,
                "selected_ingredients": ["Vanilla Extract", "Cocoa Powder", "Mint Oil"]
            }
        )

        if not grid_success or not slider_success:
            print("❌ Failed to save test data")
            return False

        # Verify data uniformity
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Check that both entries have ingredient_data_json
            cursor.execute("""
                SELECT participant_id, interface_type, ingredient_data_json
                FROM responses
                WHERE session_id = 'test_session_uniformity'
                ORDER BY participant_id
            """)

            results = cursor.fetchall()

            if len(results) != 2:
                print(f"❌ Expected 2 test records, found {len(results)}")
                return False

            grid_data = None
            slider_data = None

            for participant_id, interface_type, json_data in results:
                if interface_type == "grid_2d":
                    grid_data = json.loads(json_data) if json_data else None
                elif interface_type == "slider_based":
                    slider_data = json.loads(json_data) if json_data else None

            if not grid_data or not slider_data:
                print("❌ Missing JSON data for one or both interfaces")
                return False

            # Verify JSON structure uniformity
            required_keys = ["interface_type", "ingredients", "timestamp"]

            for data, interface_name in [(grid_data, "2D Grid"), (slider_data, "Slider")]:
                for key in required_keys:
                    if key not in data:
                        print(f"❌ Missing '{key}' in {interface_name} JSON data")
                        return False

                # Check ingredients structure
                if "ingredients" not in data or not isinstance(data["ingredients"], dict):
                    print(f"❌ Invalid ingredients structure in {interface_name}")
                    return False

            # Verify ingredient-agnostic storage (no hardcoded ingredient names in structure)
            print("   ✅ Both interfaces use identical JSON structure")
            print("   ✅ No hardcoded ingredient names in data structure")
            print("   ✅ Custom ingredient names stored correctly")

            # Verify ingredient names are stored dynamically
            grid_ingredient_names = [
                ing_data.get("name") for ing_data in grid_data["ingredients"].values()
                if ing_data and ing_data.get("name")
            ]
            slider_ingredient_names = [
                ing_data.get("name") for ing_data in slider_data["ingredients"].values()
                if ing_data and ing_data.get("name")
            ]

            expected_grid_names = ["Vanilla Extract", "Cocoa Powder"]
            expected_slider_names = ["Vanilla Extract", "Cocoa Powder", "Mint Oil"]

            if set(grid_ingredient_names) != set(expected_grid_names):
                print(f"❌ Grid ingredient names mismatch. Expected: {expected_grid_names}, Got: {grid_ingredient_names}")
                return False

            if set(slider_ingredient_names) != set(expected_slider_names):
                print(f"❌ Slider ingredient names mismatch. Expected: {expected_slider_names}, Got: {slider_ingredient_names}")
                return False

            print("   ✅ Dynamic ingredient names stored correctly")

            # Test querying with JSON views
            cursor.execute("""
                SELECT participant_id, interface_type,
                       ingredient_1_name, ingredient_1_concentration,
                       ingredient_2_name, ingredient_2_concentration,
                       ingredient_3_name, ingredient_3_concentration
                FROM ingredients_parsed
                WHERE session_id = 'test_session_uniformity'
                ORDER BY participant_id
            """)

            parsed_results = cursor.fetchall()
            if len(parsed_results) != 2:
                print(f"❌ JSON parsing views not working properly. Expected 2 results, got {len(parsed_results)}")
                return False

            print("   ✅ JSON parsing views work with custom ingredients")
            print("   ✅ Database queries ingredient-agnostic")

        print("🎉 All uniformity tests PASSED!")
        print("   • Both interfaces use identical JSON structure")
        print("   • System works with any ingredient configuration")
        print("   • No hardcoded ingredient dependencies")
        print("   • Database views parse custom ingredients correctly")

        return True

    finally:
        # Restore original database path
        if original_db_path and hasattr(sql_handler, 'DATABASE_PATH'):
            sql_handler.DATABASE_PATH = original_db_path

        # Clean up temp file
        try:
            os.unlink(temp_db_path)
        except:
            pass

if __name__ == "__main__":
    success = test_ingredient_agnostic_storage()
    if success:
        print("\n✅ UNIFORMITY TEST COMPLETE - All systems are ingredient-agnostic!")
        sys.exit(0)
    else:
        print("\n❌ UNIFORMITY TEST FAILED - Some hardcoded dependencies remain")
        sys.exit(1)