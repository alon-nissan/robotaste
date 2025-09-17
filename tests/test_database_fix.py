#!/usr/bin/env python3
"""
Test script to verify the database schema fixes for slider responses.
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
    save_multi_ingredient_response,
    export_responses_csv,
    get_participant_responses
)

def test_database_schema():
    """Test that the database schema supports multi-ingredient responses."""
    print("🔍 Testing database schema...")

    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database")
        return False

    # Check that the responses table has the new columns
    conn = sqlite3.connect("experiment_sync.db")
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(responses)")
    columns = [column[1] for column in cursor.fetchall()]

    required_columns = [
        'session_id', 'selection_number', 'interface_type',
        'ingredient_1_conc', 'ingredient_2_conc', 'ingredient_3_conc',
        'ingredient_4_conc', 'ingredient_5_conc', 'ingredient_6_conc',
        'questionnaire_response', 'is_final_response'
    ]

    missing_columns = [col for col in required_columns if col not in columns]

    if missing_columns:
        print(f"❌ Missing columns: {missing_columns}")
        return False

    print("✅ Database schema is correct")
    conn.close()
    return True

def test_slider_response_saving():
    """Test saving multi-ingredient slider responses."""
    print("🔍 Testing slider response saving...")

    # Test data for a 4-ingredient slider response
    test_data = {
        "participant_id": "test_participant_001",
        "session_id": "TEST123",
        "ingredient_concentrations": {
            "Sugar": 25.5,
            "Salt": 5.2,
            "Citric Acid": 12.8,
            "Caffeine": 3.1
        },
        "questionnaire_responses": {
            "sweetness": 7,
            "saltiness": 4,
            "sourness": 6,
            "bitterness": 3,
            "overall_liking": 6
        }
    }

    # Save test response
    success = save_multi_ingredient_response(
        participant_id=test_data["participant_id"],
        session_id=test_data["session_id"],
        method="slider_based",
        interface_type="slider_based",
        ingredient_concentrations=test_data["ingredient_concentrations"],
        reaction_time_ms=2500,
        questionnaire_response=test_data["questionnaire_responses"],
        is_final_response=True,
        extra_data={
            "test_data": True,
            "ingredient_count": len(test_data["ingredient_concentrations"])
        }
    )

    if not success:
        print("❌ Failed to save slider response")
        return False

    print("✅ Slider response saved successfully")
    return True

def test_data_retrieval():
    """Test retrieving saved responses."""
    print("🔍 Testing data retrieval...")

    # Get responses for test participant
    responses_df = get_participant_responses("test_participant_001")

    if responses_df.empty:
        print("❌ No responses found for test participant")
        return False

    # Check that the response has the correct data
    latest_response = responses_df.iloc[0]

    # Check ingredient concentrations
    if latest_response['ingredient_1_conc'] != 25.5:  # Sugar
        print(f"❌ Incorrect ingredient_1_conc: {latest_response['ingredient_1_conc']}")
        return False

    if latest_response['ingredient_2_conc'] != 5.2:  # Salt
        print(f"❌ Incorrect ingredient_2_conc: {latest_response['ingredient_2_conc']}")
        return False

    # Check questionnaire response
    if latest_response['questionnaire_response']:
        questionnaire_data = json.loads(latest_response['questionnaire_response'])
        if questionnaire_data.get('sweetness') != 7:
            print(f"❌ Incorrect questionnaire data: {questionnaire_data}")
            return False

    print("✅ Data retrieval successful")
    print(f"   - Interface type: {latest_response['interface_type']}")
    print(f"   - Method: {latest_response['method']}")
    print(f"   - Is final: {latest_response['is_final_response']}")
    print(f"   - Ingredients: {latest_response['ingredient_1_conc']}, {latest_response['ingredient_2_conc']}, {latest_response['ingredient_3_conc']}, {latest_response['ingredient_4_conc']}")
    return True

def test_csv_export():
    """Test CSV export functionality."""
    print("🔍 Testing CSV export...")

    csv_data = export_responses_csv("TEST123")

    if not csv_data:
        print("❌ No CSV data exported")
        return False

    # Check that CSV contains expected headers
    lines = csv_data.strip().split('\n')
    header = lines[0]

    expected_headers = [
        'participant_id', 'session_id', 'interface_type',
        'ingredient_1_conc', 'ingredient_2_conc', 'ingredient_3_conc',
        'questionnaire_response', 'is_final_response'
    ]

    for expected_header in expected_headers:
        if expected_header not in header:
            print(f"❌ Missing header: {expected_header}")
            return False

    # Check that we have at least one data row
    if len(lines) < 2:
        print("❌ No data rows in CSV")
        return False

    print("✅ CSV export successful")
    print(f"   - Exported {len(lines) - 1} rows")
    return True

def test_2_ingredient_compatibility():
    """Test that 2-ingredient (grid) responses still work."""
    print("🔍 Testing 2-ingredient compatibility...")

    # Test traditional 2-ingredient response (like grid interface)
    success = save_multi_ingredient_response(
        participant_id="test_participant_002",
        session_id="TEST123",
        method="linear",
        interface_type="grid_2d",
        ingredient_concentrations={
            "Sugar": 18.5,
            "Salt": 7.2
        },
        x_position=150.0,
        y_position=200.0,
        reaction_time_ms=1800,
        questionnaire_response={"overall_liking": 5},
        is_final_response=True,
        extra_data={"grid_interface": True}
    )

    if not success:
        print("❌ Failed to save 2-ingredient response")
        return False

    print("✅ 2-ingredient compatibility successful")
    return True

def main():
    """Run all tests."""
    print("🧪 Starting database fix verification tests...")
    print("=" * 50)

    tests = [
        test_database_schema,
        test_slider_response_saving,
        test_data_retrieval,
        test_csv_export,
        test_2_ingredient_compatibility
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
        print()

    print("=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! The database fixes are working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)