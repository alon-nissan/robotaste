#!/usr/bin/env python3
"""
Test script to verify the complete slider workflow works end-to-end.
"""

import os
import sys

# Add the current directory to the path to import our modules
sys.path.append(os.path.dirname(__file__))

from sql_handler import (
    init_database,
    save_multi_ingredient_response,
    export_responses_csv,
    get_participant_responses
)

def test_complete_slider_workflow():
    """Test the complete slider workflow: Finish button → Questionnaire → Final submission."""
    print("🔍 Testing complete slider workflow...")

    participant_id = "test_slider_participant"
    session_id = "SLIDER_TEST"

    # Step 1: User clicks "Finish" button - saves initial response
    print("  Step 1: User clicks 'Finish' button...")

    ingredient_concentrations = {
        "Sugar": 35.2,
        "Salt": 8.1,
        "Citric Acid": 15.5
    }

    success_1 = save_multi_ingredient_response(
        participant_id=participant_id,
        session_id=session_id,
        method="slider_based",
        interface_type="slider_based",
        ingredient_concentrations=ingredient_concentrations,
        reaction_time_ms=3200,
        questionnaire_response=None,  # No questionnaire yet
        is_final_response=False,  # Not final until questionnaire
        extra_data={
            "concentrations_summary": {
                "Sugar": {"slider_position": 70.4, "actual_concentration_mM": 35.2},
                "Salt": {"slider_position": 81.0, "actual_concentration_mM": 8.1},
                "Citric Acid": {"slider_position": 62.0, "actual_concentration_mM": 15.5}
            },
            "slider_interface": True,
            "finish_button_clicked": True
        }
    )

    if not success_1:
        print("❌ Failed to save initial slider response")
        return False

    print("    ✅ Initial slider response saved")

    # Step 2: User completes questionnaire - saves final response
    print("  Step 2: User completes questionnaire...")

    questionnaire_responses = {
        "sweetness": 8,
        "saltiness": 6,
        "sourness": 7,
        "bitterness": 2,
        "overall_liking": 7,
        "is_final": True
    }

    success_2 = save_multi_ingredient_response(
        participant_id=participant_id,
        session_id=session_id,
        method="slider_based",
        interface_type="slider_based",
        ingredient_concentrations=ingredient_concentrations,
        reaction_time_ms=3200,
        questionnaire_response=questionnaire_responses,
        is_final_response=True,  # Final submission
        extra_data={
            "concentrations_summary": {
                "Sugar": {"slider_position": 70.4, "actual_concentration_mM": 35.2},
                "Salt": {"slider_position": 81.0, "actual_concentration_mM": 8.1},
                "Citric Acid": {"slider_position": 62.0, "actual_concentration_mM": 15.5}
            },
            "slider_interface": True,
            "final_submission": True
        }
    )

    if not success_2:
        print("❌ Failed to save final slider response")
        return False

    print("    ✅ Final slider response with questionnaire saved")

    # Step 3: Verify both responses are in database
    print("  Step 3: Verifying data in database...")

    responses_df = get_participant_responses(participant_id)

    if len(responses_df) != 2:
        print(f"❌ Expected 2 responses, found {len(responses_df)}")
        return False

    # Check that we have one non-final and one final response
    final_responses = responses_df[responses_df['is_final_response'] == 1]
    non_final_responses = responses_df[responses_df['is_final_response'] == 0]

    if len(final_responses) != 1:
        print(f"❌ Expected 1 final response, found {len(final_responses)}")
        return False

    if len(non_final_responses) != 1:
        print(f"❌ Expected 1 non-final response, found {len(non_final_responses)}")
        return False

    print("    ✅ Both responses found in database")

    # Step 4: Check data integrity
    print("  Step 4: Checking data integrity...")

    final_response = final_responses.iloc[0]

    # Check ingredient concentrations
    if abs(final_response['ingredient_1_conc'] - 35.2) > 0.1:
        print(f"❌ Incorrect Sugar concentration: {final_response['ingredient_1_conc']}")
        return False

    if abs(final_response['ingredient_2_conc'] - 8.1) > 0.1:
        print(f"❌ Incorrect Salt concentration: {final_response['ingredient_2_conc']}")
        return False

    if abs(final_response['ingredient_3_conc'] - 15.5) > 0.1:
        print(f"❌ Incorrect Citric Acid concentration: {final_response['ingredient_3_conc']}")
        return False

    # Check questionnaire data
    if final_response['questionnaire_response']:
        import json
        questionnaire_data = json.loads(final_response['questionnaire_response'])
        if questionnaire_data.get('sweetness') != 8:
            print(f"❌ Incorrect questionnaire sweetness: {questionnaire_data.get('sweetness')}")
            return False

    print("    ✅ Data integrity verified")

    # Step 5: Test export
    print("  Step 5: Testing data export...")

    csv_data = export_responses_csv(session_id)
    lines = csv_data.strip().split('\n')

    if len(lines) != 3:  # Header + 2 data rows
        print(f"❌ Expected 3 lines in CSV (header + 2 rows), found {len(lines)}")
        return False

    print("    ✅ Data export successful")

    print("✅ Complete slider workflow test passed!")
    return True

def test_6_ingredient_scenario():
    """Test a 6-ingredient slider scenario."""
    print("🔍 Testing 6-ingredient scenario...")

    participant_id = "test_6_ingredient"
    session_id = "SIX_INGREDIENT_TEST"

    ingredient_concentrations = {
        "Sugar": 25.0,
        "Salt": 5.0,
        "Citric Acid": 12.0,
        "Caffeine": 3.0,
        "Vanilla": 8.0,
        "Menthol": 2.0
    }

    success = save_multi_ingredient_response(
        participant_id=participant_id,
        session_id=session_id,
        method="slider_based",
        interface_type="slider_based",
        ingredient_concentrations=ingredient_concentrations,
        reaction_time_ms=4500,
        questionnaire_response={"overall_liking": 6},
        is_final_response=True,
        extra_data={"ingredient_count": 6}
    )

    if not success:
        print("❌ Failed to save 6-ingredient response")
        return False

    # Verify all 6 ingredients are stored
    responses_df = get_participant_responses(participant_id)
    response = responses_df.iloc[0]

    expected_values = [25.0, 5.0, 12.0, 3.0, 8.0, 2.0]
    actual_values = [
        response['ingredient_1_conc'],
        response['ingredient_2_conc'],
        response['ingredient_3_conc'],
        response['ingredient_4_conc'],
        response['ingredient_5_conc'],
        response['ingredient_6_conc']
    ]

    for i, (expected, actual) in enumerate(zip(expected_values, actual_values)):
        if abs(actual - expected) > 0.1:
            print(f"❌ Incorrect ingredient_{i+1}_conc: expected {expected}, got {actual}")
            return False

    print("✅ 6-ingredient scenario test passed!")
    return True

def main():
    """Run slider workflow tests."""
    print("🧪 Starting slider workflow verification tests...")
    print("=" * 60)

    # Initialize database
    if not init_database():
        print("❌ Failed to initialize database")
        return False

    tests = [
        test_complete_slider_workflow,
        test_6_ingredient_scenario
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
            import traceback
            print(traceback.format_exc())
            failed += 1
        print()

    print("=" * 60)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All slider workflow tests passed!")
        print("✅ The slider interface should now register responses in the database correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)