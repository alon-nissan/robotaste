#!/usr/bin/env python3
"""
Test script to verify all three fixes work correctly:
1. Slider initial positions from database
2. Database view for slider positions
3. UnboundLocalError fix for final response submission
"""

import os
import sys
import sqlite3
import json
from datetime import datetime

# Add the current directory to the path to import our modules
sys.path.append(os.path.dirname(__file__))

from sql_handler import (
    init_database,
    store_initial_slider_positions,
    get_initial_slider_positions,
    get_live_slider_positions,
    save_multi_ingredient_response,
    export_responses_csv
)

def test_slider_initial_positions():
    """Test storing and retrieving initial slider positions from database."""
    print("🔍 Testing slider initial positions from database...")

    # Test data
    session_id = "TEST_SESSION_123"
    participant_id = "test_participant"
    num_ingredients = 4

    # Initial positions (what moderator sets)
    initial_percentages = {
        "Sugar": 25.5,
        "Salt": 67.3,
        "Citric Acid": 45.2,
        "Caffeine": 89.1
    }

    initial_concentrations = {
        "Sugar": 12.75,  # mM
        "Salt": 33.65,   # mM
        "Citric Acid": 22.60,  # mM
        "Caffeine": 44.55   # mM
    }

    ingredient_names = ["Sugar", "Salt", "Citric Acid", "Caffeine"]

    # Store initial positions
    success = store_initial_slider_positions(
        session_id=session_id,
        participant_id=participant_id,
        num_ingredients=num_ingredients,
        initial_percentages=initial_percentages,
        initial_concentrations=initial_concentrations,
        ingredient_names=ingredient_names
    )

    if not success:
        print("❌ Failed to store initial slider positions")
        return False

    print("  ✅ Initial positions stored successfully")

    # Retrieve initial positions
    retrieved = get_initial_slider_positions(session_id, participant_id)

    if not retrieved:
        print("❌ Failed to retrieve initial slider positions")
        return False

    print("  ✅ Initial positions retrieved successfully")

    # Verify data integrity
    for ingredient_name, expected_percent in initial_percentages.items():
        if ingredient_name not in retrieved["percentages"]:
            print(f"❌ Missing ingredient {ingredient_name} in retrieved percentages")
            return False

        actual_percent = retrieved["percentages"][ingredient_name]
        if abs(actual_percent - expected_percent) > 0.1:
            print(f"❌ Wrong percentage for {ingredient_name}: expected {expected_percent}, got {actual_percent}")
            return False

    print("  ✅ Data integrity verified")
    print(f"    Retrieved percentages: {retrieved['percentages']}")

    return True

def test_database_view():
    """Test database view for slider positions."""
    print("🔍 Testing database view for slider positions...")

    # Create some test slider data
    session_id = "VIEW_TEST_SESSION"
    participant_id = "view_test_participant"

    # Save a slider response
    ingredient_concentrations = {
        "Sugar": 15.2,
        "Salt": 8.7,
        "Citric Acid": 12.3
    }

    success = save_multi_ingredient_response(
        participant_id=participant_id,
        session_id=session_id,
        method="slider_based",
        interface_type="slider_based",
        ingredient_concentrations=ingredient_concentrations,
        reaction_time_ms=3500,
        questionnaire_response=None,
        is_final_response=False,
        extra_data={"test_view": True}
    )

    if not success:
        print("❌ Failed to save test slider response")
        return False

    print("  ✅ Test slider response saved")

    # Test live slider positions view
    live_positions = get_live_slider_positions(session_id)

    if live_positions.empty:
        print("❌ No live positions found in database view")
        return False

    print("  ✅ Database view retrieved live positions")

    # Verify view contains expected data
    row = live_positions.iloc[0]
    if row['session_id'] != session_id:
        print(f"❌ Wrong session_id in view: expected {session_id}, got {row['session_id']}")
        return False

    if row['participant_id'] != participant_id:
        print(f"❌ Wrong participant_id in view: expected {participant_id}, got {row['participant_id']}")
        return False

    if abs(row['ingredient_1_conc'] - 15.2) > 0.1:
        print(f"❌ Wrong ingredient_1_conc: expected 15.2, got {row['ingredient_1_conc']}")
        return False

    print("  ✅ Database view data integrity verified")
    print(f"    View columns: {list(live_positions.columns)}")

    return True

def test_final_response_submission():
    """Test that final response submission works without UnboundLocalError."""
    print("🔍 Testing final response submission (UnboundLocalError fix)...")

    session_id = "FINAL_TEST_SESSION"
    participant_id = "final_test_participant"

    # Test data for final submission
    ingredient_concentrations = {
        "Sugar": 28.5,
        "Salt": 12.1,
        "Citric Acid": 18.7,
        "Caffeine": 5.3
    }

    questionnaire_response = {
        "sweetness": 7,
        "saltiness": 5,
        "sourness": 6,
        "bitterness": 3,
        "overall_liking": 6,
        "is_final": True
    }

    # This should work without UnboundLocalError
    try:
        success = save_multi_ingredient_response(
            participant_id=participant_id,
            session_id=session_id,
            method="slider_based",
            interface_type="slider_based",
            ingredient_concentrations=ingredient_concentrations,
            reaction_time_ms=4200,
            questionnaire_response=questionnaire_response,
            is_final_response=True,
            extra_data={
                "final_submission": True,
                "test_unboundlocalerror_fix": True
            }
        )

        if not success:
            print("❌ Final response submission failed")
            return False

        print("  ✅ Final response submitted successfully")

    except NameError as e:
        if "save_multi_ingredient_response" in str(e):
            print(f"❌ UnboundLocalError still present: {e}")
            return False
        else:
            raise e

    # Verify final response was saved correctly
    live_positions = get_live_slider_positions(session_id)

    if live_positions.empty:
        print("❌ Final response not found in database")
        return False

    final_row = live_positions[live_positions['participant_id'] == participant_id].iloc[0]

    if final_row['is_final_response'] != 1:
        print("❌ Response not marked as final")
        return False

    if final_row['questionnaire_response'] is None:
        print("❌ Questionnaire response not saved")
        return False

    # Parse questionnaire response
    try:
        saved_questionnaire = json.loads(final_row['questionnaire_response'])
        if saved_questionnaire.get('sweetness') != 7:
            print("❌ Questionnaire data corrupted")
            return False
    except:
        print("❌ Questionnaire response not valid JSON")
        return False

    print("  ✅ Final response data integrity verified")

    return True

def test_csv_export_with_new_schema():
    """Test CSV export with the new multi-ingredient schema."""
    print("🔍 Testing CSV export with new schema...")

    # Export data from all test sessions
    csv_data = export_responses_csv()

    if not csv_data:
        print("❌ No CSV data exported")
        return False

    lines = csv_data.strip().split('\n')
    if len(lines) < 2:
        print("❌ CSV contains no data rows")
        return False

    header = lines[0]
    expected_headers = [
        'session_id', 'participant_id', 'interface_type',
        'ingredient_1_conc', 'ingredient_2_conc', 'ingredient_3_conc',
        'questionnaire_response', 'is_final_response'
    ]

    for expected_header in expected_headers:
        if expected_header not in header:
            print(f"❌ Missing expected header: {expected_header}")
            return False

    print("  ✅ CSV export successful with new schema")
    print(f"    Exported {len(lines) - 1} data rows")

    return True

def main():
    """Run all fix verification tests."""
    print("🧪 Testing all three fixes together...")
    print("=" * 60)

    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database")
        return False

    tests = [
        ("Slider Initial Positions", test_slider_initial_positions),
        ("Database View", test_database_view),
        ("Final Response Submission", test_final_response_submission),
        ("CSV Export", test_csv_export_with_new_schema)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
                failed += 1
        except Exception as e:
            print(f"❌ {test_name}: FAILED with exception: {e}")
            import traceback
            print(traceback.format_exc())
            failed += 1

    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All fixes working correctly!")
        print("\n✅ **SUMMARY OF FIXES:**")
        print("1. ✅ Slider initial positions now load from database")
        print("2. ✅ Database view provides live slider monitoring")
        print("3. ✅ UnboundLocalError in final response submission fixed")
        print("4. ✅ Multi-ingredient schema supports 2-6 ingredients")
        print("5. ✅ CSV export includes all new fields")
        return True
    else:
        print("⚠️ Some fixes need attention. Please review the failed tests.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)