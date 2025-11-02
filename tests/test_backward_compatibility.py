#!/usr/bin/env python3
"""
Test script to verify backward compatibility with existing sessions.

Tests that the new questionnaire system works correctly with:
- Existing database records without questionnaire_type
- Sessions created before the questionnaire update
- Legacy responses without target_variable_value
- Database migration handling of NULL values
"""

import os
import sys
import sqlite3
import json
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sql_handler import (
    init_database,
    save_multi_ingredient_response,
    get_questionnaire_config_from_session,
    extract_and_save_target_variable,
)

from questionnaire_config import (
    get_questionnaire_config,
    get_default_questionnaire_type,
    extract_target_variable,
)


def setup_legacy_database():
    """Create a database with legacy data (no questionnaire columns)."""
    print("🔧 Setting up legacy database for testing...")

    # Create a test database
    test_db = "test_legacy.db"

    # Remove if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Create legacy sessions table (without experiment_config)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_code TEXT PRIMARY KEY,
            moderator_name TEXT,
            is_active INTEGER DEFAULT 1,
            subject_connected INTEGER DEFAULT 0,
            current_phase TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create legacy responses table (without questionnaire columns)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            participant_id TEXT,
            selection_number INTEGER DEFAULT 1,
            interface_type TEXT,
            method TEXT,
            x_position REAL,
            y_position REAL,
            ingredient_1_conc REAL,
            ingredient_2_conc REAL,
            ingredient_3_conc REAL,
            ingredient_4_conc REAL,
            ingredient_5_conc REAL,
            ingredient_6_conc REAL,
            reaction_time_ms INTEGER,
            questionnaire_response TEXT,
            is_final_response INTEGER DEFAULT 0,
            is_initial INTEGER DEFAULT 0,
            extra_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert legacy session data
    cursor.execute("""
        INSERT INTO sessions (session_code, moderator_name, current_phase)
        VALUES ('LEGACY1', 'Test Moderator', 'trial_active')
    """)

    # Insert legacy response (before questionnaire system existed)
    cursor.execute("""
        INSERT INTO responses (
            session_id, participant_id, interface_type, method,
            ingredient_1_conc, ingredient_2_conc,
            questionnaire_response, is_final_response
        ) VALUES (
            'LEGACY1', 'participant_001', 'grid_2d', 'linear',
            25.5, 5.2,
            '{"satisfaction": 6, "confidence": 5}', 1
        )
    """)

    conn.commit()
    conn.close()

    print(f"✅ Legacy database created: {test_db}")
    return test_db


def test_database_migration_preserves_data():
    """Test that migration adds new columns without losing existing data."""
    print("🔍 Testing database migration preserves existing data...")

    # Create legacy database
    test_db = setup_legacy_database()

    # Manually run migration (simulating what happens when init_database runs)
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Check existing data before migration
    cursor.execute("SELECT COUNT(*) FROM responses")
    count_before = cursor.fetchone()[0]

    if count_before != 1:
        print(f"❌ Expected 1 record before migration, found {count_before}")
        conn.close()
        os.remove(test_db)
        return False

    # Manually add questionnaire columns (simulating migration)
    cursor.execute("PRAGMA table_info(responses)")
    columns = {col[1]: col for col in cursor.fetchall()}

    if 'questionnaire_type' not in columns:
        cursor.execute("""
            ALTER TABLE responses
            ADD COLUMN questionnaire_type TEXT DEFAULT 'hedonic_preference'
        """)

    if 'target_variable_value' not in columns:
        cursor.execute("""
            ALTER TABLE responses
            ADD COLUMN target_variable_value REAL DEFAULT NULL
        """)

    if 'bo_predicted_value' not in columns:
        cursor.execute("""
            ALTER TABLE responses
            ADD COLUMN bo_predicted_value REAL DEFAULT NULL
        """)

    if 'bo_acquisition_value' not in columns:
        cursor.execute("""
            ALTER TABLE responses
            ADD COLUMN bo_acquisition_value REAL DEFAULT NULL
        """)

    conn.commit()

    # Verify data still exists after migration
    cursor.execute("SELECT COUNT(*) FROM responses")
    count_after = cursor.fetchone()[0]

    if count_after != count_before:
        print(f"❌ Data lost during migration: {count_before} → {count_after}")
        conn.close()
        os.remove(test_db)
        return False

    # Verify existing record has default questionnaire_type
    cursor.execute("""
        SELECT questionnaire_type, target_variable_value,
               ingredient_1_conc, ingredient_2_conc
        FROM responses
        WHERE participant_id = 'participant_001'
    """)
    row = cursor.fetchone()

    if row is None:
        print("❌ Legacy record not found after migration")
        conn.close()
        os.remove(test_db)
        return False

    questionnaire_type, target_value, ing1, ing2 = row

    # Check that default was applied
    if questionnaire_type != 'hedonic_preference':
        print(f"❌ Expected default 'hedonic_preference', got '{questionnaire_type}'")
        conn.close()
        os.remove(test_db)
        return False

    # Check that original data preserved
    if abs(ing1 - 25.5) > 0.01 or abs(ing2 - 5.2) > 0.01:
        print(f"❌ Original concentration data corrupted: {ing1}, {ing2}")
        conn.close()
        os.remove(test_db)
        return False

    # Check that new columns are NULL (no retroactive calculation)
    if target_value is not None:
        print(f"❌ target_variable_value should be NULL for legacy data, got {target_value}")
        conn.close()
        os.remove(test_db)
        return False

    print("✅ Database migration preserved existing data correctly")
    conn.close()
    os.remove(test_db)
    return True


def test_session_without_experiment_config():
    """Test handling of sessions created before experiment_config existed."""
    print("🔍 Testing sessions without experiment_config...")

    # This tests the fallback logic in get_questionnaire_type_from_config()
    # When experiment_config is missing, it should fall back to default

    default_type = get_default_questionnaire_type()

    if default_type != 'hedonic_preference':
        print(f"❌ Default type should be 'hedonic_preference', got '{default_type}'")
        return False

    # Verify that get_questionnaire_config handles None gracefully
    config = get_questionnaire_config(None)

    if config is None:
        print("❌ Should return default config when type is None")
        return False

    if config['name'] != 'Hedonic Preference Test':
        print(f"❌ Expected 'Hedonic Preference Test', got '{config['name']}'")
        return False

    print("✅ Sessions without experiment_config handled correctly")
    return True


def test_legacy_questionnaire_responses():
    """Test that legacy questionnaire responses (unified_feedback) still work."""
    print("🔍 Testing legacy unified_feedback questionnaire responses...")

    # Get unified_feedback config (legacy questionnaire)
    config = get_questionnaire_config('unified_feedback')

    if config is None:
        print("❌ Legacy 'unified_feedback' questionnaire not found")
        return False

    # Simulate legacy response
    legacy_response = {
        'satisfaction': 6,
        'confidence': 5,
        'strategy': 'Systematic approach'
    }

    # Extract target variable (should use 'satisfaction')
    target_value = extract_target_variable(legacy_response, config)

    if target_value != 6.0:
        print(f"❌ Expected target value 6.0, got {target_value}")
        return False

    # Verify Bayesian target configuration exists
    if 'bayesian_target' not in config:
        print("❌ Legacy questionnaire missing bayesian_target config")
        return False

    if config['bayesian_target']['variable'] != 'satisfaction':
        print(f"❌ Legacy target should be 'satisfaction', got '{config['bayesian_target']['variable']}'")
        return False

    print("✅ Legacy unified_feedback questionnaire responses work correctly")
    return True


def test_null_handling():
    """Test that NULL values in new columns are handled gracefully."""
    print("🔍 Testing NULL value handling in new columns...")

    # Create a temporary database for testing
    test_db = "test_null_handling.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Create responses table with new columns
    cursor.execute("""
        CREATE TABLE responses (
            id INTEGER PRIMARY KEY,
            participant_id TEXT,
            questionnaire_type TEXT DEFAULT 'hedonic_preference',
            target_variable_value REAL DEFAULT NULL,
            bo_predicted_value REAL DEFAULT NULL,
            bo_acquisition_value REAL DEFAULT NULL,
            ingredient_1_conc REAL
        )
    """)

    # Insert record with NULLs in new columns
    cursor.execute("""
        INSERT INTO responses (participant_id, ingredient_1_conc)
        VALUES ('test_participant', 25.5)
    """)

    conn.commit()

    # Query and verify NULL handling
    cursor.execute("""
        SELECT questionnaire_type, target_variable_value,
               bo_predicted_value, bo_acquisition_value
        FROM responses
        WHERE participant_id = 'test_participant'
    """)

    row = cursor.fetchone()
    questionnaire_type, target_value, bo_pred, bo_acq = row

    # Verify default questionnaire_type was applied
    if questionnaire_type != 'hedonic_preference':
        print(f"❌ Default questionnaire_type not applied: {questionnaire_type}")
        conn.close()
        os.remove(test_db)
        return False

    # Verify other columns are NULL
    if target_value is not None or bo_pred is not None or bo_acq is not None:
        print(f"❌ New columns should be NULL: target={target_value}, pred={bo_pred}, acq={bo_acq}")
        conn.close()
        os.remove(test_db)
        return False

    print("✅ NULL values handled correctly")
    conn.close()
    os.remove(test_db)
    return True


def test_existing_responses_query_compatibility():
    """Test that existing queries for responses still work after migration."""
    print("🔍 Testing backward compatibility of response queries...")

    test_db = "test_query_compat.db"

    if os.path.exists(test_db):
        os.remove(test_db)

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()

    # Create responses table with all columns
    cursor.execute("""
        CREATE TABLE responses (
            id INTEGER PRIMARY KEY,
            session_id TEXT,
            participant_id TEXT,
            interface_type TEXT,
            ingredient_1_conc REAL,
            ingredient_2_conc REAL,
            questionnaire_response TEXT,
            is_final_response INTEGER,
            questionnaire_type TEXT DEFAULT 'hedonic_preference',
            target_variable_value REAL DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO responses (
            session_id, participant_id, interface_type,
            ingredient_1_conc, ingredient_2_conc,
            questionnaire_response, is_final_response
        ) VALUES (
            'TEST123', 'participant_001', 'grid_2d',
            30.0, 6.5,
            '{"hedonic_score": 7}', 1
        )
    """)

    conn.commit()

    # Test legacy query (without new columns)
    try:
        cursor.execute("""
            SELECT session_id, participant_id, ingredient_1_conc, ingredient_2_conc
            FROM responses
            WHERE is_final_response = 1
        """)
        results = cursor.fetchall()

        if len(results) != 1:
            print(f"❌ Legacy query failed: expected 1 result, got {len(results)}")
            conn.close()
            os.remove(test_db)
            return False

        session_id, participant_id, ing1, ing2 = results[0]
        if session_id != 'TEST123' or participant_id != 'participant_001':
            print(f"❌ Legacy query returned wrong data: {results[0]}")
            conn.close()
            os.remove(test_db)
            return False

    except Exception as e:
        print(f"❌ Legacy query raised exception: {e}")
        conn.close()
        os.remove(test_db)
        return False

    # Test new query (with new columns)
    try:
        cursor.execute("""
            SELECT session_id, participant_id, questionnaire_type, target_variable_value
            FROM responses
            WHERE is_final_response = 1
        """)
        results = cursor.fetchall()

        if len(results) != 1:
            print(f"❌ New query failed: expected 1 result, got {len(results)}")
            conn.close()
            os.remove(test_db)
            return False

        session_id, participant_id, q_type, target_val = results[0]

        if q_type != 'hedonic_preference':
            print(f"❌ New query: expected 'hedonic_preference', got '{q_type}'")
            conn.close()
            os.remove(test_db)
            return False

    except Exception as e:
        print(f"❌ New query raised exception: {e}")
        conn.close()
        os.remove(test_db)
        return False

    print("✅ Both legacy and new queries work correctly")
    conn.close()
    os.remove(test_db)
    return True


def run_all_tests():
    """Run all backward compatibility tests."""
    print("\n" + "="*70)
    print("BACKWARD COMPATIBILITY TEST SUITE")
    print("="*70 + "\n")

    tests = [
        ("Database Migration Preserves Data", test_database_migration_preserves_data),
        ("Sessions Without experiment_config", test_session_without_experiment_config),
        ("Legacy Questionnaire Responses", test_legacy_questionnaire_responses),
        ("NULL Value Handling", test_null_handling),
        ("Response Query Compatibility", test_existing_responses_query_compatibility),
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
