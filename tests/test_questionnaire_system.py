#!/usr/bin/env python3
"""
Test script to verify the questionnaire configuration system.

Tests:
- Questionnaire configuration retrieval
- Questionnaire validation
- Target variable extraction
- Database schema migration for questionnaire support
- Backward compatibility with existing sessions
"""

import os
import sys
import sqlite3
import json
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from questionnaire_config import (
    get_questionnaire_config,
    get_default_questionnaire_type,
    list_available_questionnaires,
    validate_questionnaire_response,
    extract_target_variable,
    get_question_by_id,
    QUESTIONNAIRE_CONFIGS
)

from sql_handler import (
    init_database,
    get_questionnaire_config_from_session,
    extract_and_save_target_variable,
    get_participant_target_values,
    save_bayesian_prediction
)


def test_questionnaire_configs_exist():
    """Test that all required questionnaire configurations exist."""
    print("🔍 Testing questionnaire configurations exist...")

    required_questionnaires = [
        'hedonic_preference',
        'unified_feedback',
        'multi_attribute',
        'composite_preference'
    ]

    for questionnaire_type in required_questionnaires:
        config = get_questionnaire_config(questionnaire_type)
        if config is None:
            print(f"❌ Missing questionnaire configuration: {questionnaire_type}")
            return False

        # Verify required keys exist
        required_keys = ['name', 'description', 'questions', 'bayesian_target']
        for key in required_keys:
            if key not in config:
                print(f"❌ Missing key '{key}' in {questionnaire_type} configuration")
                return False

    print(f"✅ All {len(required_questionnaires)} questionnaire configurations exist")
    return True


def test_default_questionnaire():
    """Test that default questionnaire is hedonic_preference."""
    print("🔍 Testing default questionnaire type...")

    default_type = get_default_questionnaire_type()

    if default_type != 'hedonic_preference':
        print(f"❌ Default questionnaire should be 'hedonic_preference', got '{default_type}'")
        return False

    print("✅ Default questionnaire type is correct")
    return True


def test_hedonic_preference_structure():
    """Test the structure of hedonic preference questionnaire."""
    print("🔍 Testing hedonic preference questionnaire structure...")

    config = get_questionnaire_config('hedonic_preference')

    # Verify it has exactly one question
    if len(config['questions']) != 1:
        print(f"❌ Hedonic preference should have 1 question, has {len(config['questions'])}")
        return False

    question = config['questions'][0]

    # Verify question properties
    required_props = {
        'id': 'hedonic_score',
        'type': 'slider',
        'min': 1,
        'max': 9,
        'default': 5,
        'required': True
    }

    for prop, expected_value in required_props.items():
        if question.get(prop) != expected_value:
            print(f"❌ Question property '{prop}' should be {expected_value}, got {question.get(prop)}")
            return False

    # Verify scale labels exist
    if 'scale_labels' not in question:
        print("❌ Hedonic preference question missing scale_labels")
        return False

    # Verify all 9 scale points have labels
    scale_labels = question['scale_labels']
    expected_points = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    for point in expected_points:
        if point not in scale_labels:
            print(f"❌ Missing scale label for point {point}")
            return False

    # Verify Bayesian target configuration
    target_config = config['bayesian_target']
    if target_config['variable'] != 'hedonic_score':
        print(f"❌ Bayesian target should be 'hedonic_score', got '{target_config['variable']}'")
        return False

    if not target_config.get('higher_is_better', False):
        print("❌ Hedonic preference should have higher_is_better=True")
        return False

    print("✅ Hedonic preference questionnaire structure is correct")
    return True


def test_questionnaire_validation():
    """Test questionnaire response validation."""
    print("🔍 Testing questionnaire response validation...")

    # Test valid response for hedonic preference
    valid_response = {
        'hedonic_score': 7
    }

    is_valid, error = validate_questionnaire_response(valid_response, 'hedonic_preference')
    if not is_valid:
        print(f"❌ Valid response rejected: {error}")
        return False

    # Test missing required field
    invalid_response = {}
    is_valid, error = validate_questionnaire_response(invalid_response, 'hedonic_preference')
    if is_valid:
        print("❌ Should reject response missing required field")
        return False

    # Test out-of-range value
    out_of_range_response = {
        'hedonic_score': 15  # Max is 9
    }
    is_valid, error = validate_questionnaire_response(out_of_range_response, 'hedonic_preference')
    if is_valid:
        print("❌ Should reject out-of-range response")
        return False

    print("✅ Questionnaire validation works correctly")
    return True


def test_target_variable_extraction():
    """Test extracting target variable from questionnaire responses."""
    print("🔍 Testing target variable extraction...")

    # Test hedonic preference extraction
    config = get_questionnaire_config('hedonic_preference')
    response = {
        'hedonic_score': 8
    }

    target_value = extract_target_variable(response, config)
    if target_value != 8.0:
        print(f"❌ Expected target value 8.0, got {target_value}")
        return False

    # Test unified_feedback extraction
    unified_config = get_questionnaire_config('unified_feedback')
    unified_response = {
        'satisfaction': 6,
        'confidence': 5,
        'strategy': 'Systematic approach'
    }

    unified_target = extract_target_variable(unified_response, unified_config)
    if unified_target != 6.0:
        print(f"❌ Expected target value 6.0 for unified_feedback, got {unified_target}")
        return False

    # Test composite preference (weighted combination)
    composite_config = get_questionnaire_config('composite_preference')
    composite_response = {
        'liking': 8,
        'healthiness_perception': 6
    }

    composite_target = extract_target_variable(composite_response, composite_config)
    expected = 0.7 * 8 + 0.3 * 6  # 5.6 + 1.8 = 7.4
    if abs(composite_target - expected) > 0.01:
        print(f"❌ Expected composite target {expected}, got {composite_target}")
        return False

    print("✅ Target variable extraction works correctly")
    return True


def test_database_migration():
    """Test that database has questionnaire support columns."""
    print("🔍 Testing database schema migration for questionnaire support...")

    # Initialize database (runs migrations)
    if not init_database():
        print("❌ Failed to initialize database")
        return False

    # Check that responses table has questionnaire columns
    conn = sqlite3.connect("experiment_sync.db")
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(responses)")
    columns = {column[1]: column for column in cursor.fetchall()}

    required_columns = [
        'questionnaire_type',
        'bo_predicted_value',
        'bo_acquisition_value',
        'target_variable_value'
    ]

    missing_columns = [col for col in required_columns if col not in columns]

    if missing_columns:
        print(f"❌ Missing database columns: {missing_columns}")
        conn.close()
        return False

    # Verify default value for questionnaire_type
    questionnaire_type_col = columns['questionnaire_type']
    default_value = questionnaire_type_col[4]  # Column 4 is the default value

    # The default should be 'hedonic_preference' or NULL
    # (wrapped in quotes if it's a string default)
    if default_value and 'hedonic_preference' not in str(default_value):
        print(f"⚠️  Warning: questionnaire_type default is '{default_value}', expected 'hedonic_preference'")

    print("✅ Database schema includes questionnaire support columns")
    conn.close()
    return True


def test_list_available_questionnaires():
    """Test listing all available questionnaires."""
    print("🔍 Testing list_available_questionnaires()...")

    questionnaires = list_available_questionnaires()

    if len(questionnaires) < 4:
        print(f"❌ Expected at least 4 questionnaires, got {len(questionnaires)}")
        return False

    # Verify format: list of tuples (key, name, description)
    for q in questionnaires:
        if not isinstance(q, tuple) or len(q) != 3:
            print(f"❌ Invalid questionnaire format: {q}")
            return False

        key, name, description = q
        if not all([key, name, description]):
            print(f"❌ Incomplete questionnaire metadata: {q}")
            return False

    print(f"✅ Found {len(questionnaires)} available questionnaires")
    return True


def test_get_question_by_id():
    """Test retrieving specific questions by ID."""
    print("🔍 Testing get_question_by_id()...")

    # Test valid question retrieval
    question = get_question_by_id('hedonic_preference', 'hedonic_score')
    if question is None:
        print("❌ Failed to retrieve hedonic_score question")
        return False

    if question['id'] != 'hedonic_score':
        print(f"❌ Expected question ID 'hedonic_score', got '{question['id']}'")
        return False

    # Test invalid question ID
    invalid_question = get_question_by_id('hedonic_preference', 'nonexistent_id')
    if invalid_question is not None:
        print("❌ Should return None for invalid question ID")
        return False

    print("✅ get_question_by_id() works correctly")
    return True


def test_backward_compatibility():
    """Test that system handles sessions without questionnaire_type."""
    print("🔍 Testing backward compatibility with legacy sessions...")

    # Test that default questionnaire is used when type is not specified
    default_type = get_default_questionnaire_type()
    config = get_questionnaire_config(None)  # None should fall back to default

    if config is None:
        print("❌ Should return default questionnaire when type is None")
        return False

    # Verify it returned hedonic_preference (the default)
    if config.get('name') != 'Hedonic Preference Test':
        print(f"❌ Expected default to be Hedonic Preference Test, got {config.get('name')}")
        return False

    print("✅ Backward compatibility check passed")
    return True


def test_sql_handler_questionnaire_functions():
    """Test sql_handler helper functions for questionnaire support."""
    print("🔍 Testing sql_handler questionnaire helper functions...")

    # This is a basic existence check - full integration testing would require
    # setting up mock session data

    try:
        # Verify functions are importable and callable
        from sql_handler import (
            get_questionnaire_config_from_session,
            extract_and_save_target_variable,
            get_participant_target_values,
            save_bayesian_prediction
        )

        # Check function signatures exist
        import inspect

        # get_questionnaire_config_from_session should take session_id
        sig = inspect.signature(get_questionnaire_config_from_session)
        if 'session_id' not in sig.parameters:
            print("❌ get_questionnaire_config_from_session missing session_id parameter")
            return False

        # extract_and_save_target_variable should take response_id, questionnaire_response, questionnaire_type
        sig = inspect.signature(extract_and_save_target_variable)
        required_params = ['response_id', 'questionnaire_response', 'questionnaire_type']
        for param in required_params:
            if param not in sig.parameters:
                print(f"❌ extract_and_save_target_variable missing {param} parameter")
                return False

        print("✅ sql_handler questionnaire helper functions exist with correct signatures")
        return True

    except ImportError as e:
        print(f"❌ Failed to import sql_handler functions: {e}")
        return False


def run_all_tests():
    """Run all questionnaire system tests."""
    print("\n" + "="*70)
    print("QUESTIONNAIRE SYSTEM TEST SUITE")
    print("="*70 + "\n")

    tests = [
        ("Questionnaire Configs Exist", test_questionnaire_configs_exist),
        ("Default Questionnaire Type", test_default_questionnaire),
        ("Hedonic Preference Structure", test_hedonic_preference_structure),
        ("Questionnaire Validation", test_questionnaire_validation),
        ("Target Variable Extraction", test_target_variable_extraction),
        ("Database Schema Migration", test_database_migration),
        ("List Available Questionnaires", test_list_available_questionnaires),
        ("Get Question By ID", test_get_question_by_id),
        ("Backward Compatibility", test_backward_compatibility),
        ("SQL Handler Functions", test_sql_handler_questionnaire_functions),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test '{test_name}' raised an exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
            print()

    # Print summary
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("="*70)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("="*70 + "\n")

    return all(result for _, result in results)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
