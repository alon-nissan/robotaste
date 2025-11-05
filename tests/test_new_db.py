"""
Test script for new database functions
"""

import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import new sql_handler
import sql_handler_new as sql


def test_database_initialization():
    """Test database initialization"""
    print("\n=== Testing Database Initialization ===")

    # Remove old test database if exists
    if os.path.exists("robotaste.db"):
        os.remove("robotaste.db")
        print("✓ Removed old database")

    # Initialize database
    success = sql.init_database()
    assert success, "Database initialization failed"
    print("✓ Database initialized successfully")

    # Verify file created
    assert os.path.exists("robotaste.db"), "Database file not created"
    print("✓ Database file exists")

    # Insert test questionnaire type
    with sql.get_database_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO questionnaire_types (id, name, data)
            VALUES (1, 'hedonic_preference', '{"target_variable": "overall_liking"}')
        """)
        conn.commit()
    print("✓ Test questionnaire type inserted")


def test_user_creation():
    """Test user creation"""
    print("\n=== Testing User Creation ===")

    # Create user
    success = sql.create_user("test_user_001")
    assert success, "User creation failed"
    print("✓ User created")

    # Get user
    user = sql.get_user("test_user_001")
    assert user is not None, "User not found"
    assert user["id"] == "test_user_001"
    print(f"✓ User retrieved: {user['id']}")

    # Create duplicate (should not fail)
    success = sql.create_user("test_user_001")
    assert success, "Duplicate user creation should not fail"
    print("✓ Duplicate user handled correctly")


def test_session_creation():
    """Test session creation"""
    print("\n=== Testing Session Creation ===")

    # Create user first
    sql.create_user("test_user_002")

    # Prepare session data
    ingredients = [
        {"position": 1, "name": "Sugar", "min": 0.73, "max": 73.0, "unit": "mM"},
        {"position": 2, "name": "Salt", "min": 0.10, "max": 10.0, "unit": "mM"}
    ]

    bo_config = {
        "enabled": True,
        "min_samples_for_bo": 3,
        "acquisition_function": "ei",
        "ei_xi": 0.01,
        "ucb_kappa": 2.0,
        "kernel_nu": 2.5,
        "alpha": 0.001,
        "n_restarts_optimizer": 10,
        "normalize_y": True,
        "random_state": 42,
        "only_final_responses": True
    }

    experiment_config = {
        "questionnaire_type": "hedonic_preference",
        "moderator_name": "Test Moderator"
    }

    # Create session
    session_id = sql.create_session(
        user_id="test_user_002",
        num_ingredients=2,
        interface_type="grid_2d",
        method="logarithmic",
        ingredients=ingredients,
        question_type_id=1,
        bo_config=bo_config,
        experiment_config=experiment_config
    )

    assert session_id is not None, "Session creation failed"
    print(f"✓ Session created: {session_id}")

    # Get session
    session = sql.get_session(session_id)
    assert session is not None, "Session not found"
    assert session["user_id"] == "test_user_002"
    assert session["state"] == "active"
    assert len(session["ingredients"]) == 2
    assert session["experiment_config"]["num_ingredients"] == 2
    assert session["experiment_config"]["current_cycle"] == 0
    print(f"✓ Session retrieved with {len(session['ingredients'])} ingredients")

    # Get BO config
    bo_conf = sql.get_bo_config(session_id)
    assert bo_conf is not None, "BO config not found"
    assert bo_conf["acquisition_function"] == "ei"
    assert bo_conf["kernel_nu"] == 2.5
    print("✓ BO configuration retrieved")

    return session_id


def test_sample_cycle(session_id):
    """Test sample/cycle operations"""
    print("\n=== Testing Sample/Cycle Operations ===")

    # Save first cycle
    sample_id_1 = sql.save_sample_cycle(
        session_id=session_id,
        cycle_number=1,
        ingredient_concentration={"Sugar": 36.5, "Salt": 5.2},
        selection_data={
            "interface_type": "grid_2d",
            "x_position": 0.5,
            "y_position": 0.7,
            "method": "logarithmic"
        },
        questionnaire_answer={
            "overall_liking": 7,
            "sweetness": 6,
            "comments": "Nice balance"
        },
        is_final=False
    )

    assert sample_id_1 is not None, "Sample 1 creation failed"
    print(f"✓ Cycle 1 saved: {sample_id_1}")

    # Increment cycle
    new_cycle = sql.increment_cycle(session_id)
    assert new_cycle == 1, f"Expected cycle 1, got {new_cycle}"
    print(f"✓ Cycle incremented to {new_cycle}")

    # Save second cycle
    sample_id_2 = sql.save_sample_cycle(
        session_id=session_id,
        cycle_number=2,
        ingredient_concentration={"Sugar": 20.0, "Salt": 3.0},
        selection_data={
            "interface_type": "grid_2d",
            "x_position": 0.3,
            "y_position": 0.4,
            "method": "logarithmic"
        },
        questionnaire_answer={
            "overall_liking": 5,
            "sweetness": 4,
            "comments": "Too mild"
        },
        is_final=False
    )

    assert sample_id_2 is not None, "Sample 2 creation failed"
    print(f"✓ Cycle 2 saved: {sample_id_2}")

    # Save third cycle (final)
    sample_id_3 = sql.save_sample_cycle(
        session_id=session_id,
        cycle_number=3,
        ingredient_concentration={"Sugar": 50.0, "Salt": 7.0},
        selection_data={
            "interface_type": "grid_2d",
            "x_position": 0.7,
            "y_position": 0.9,
            "method": "logarithmic"
        },
        questionnaire_answer={
            "overall_liking": 8,
            "sweetness": 8,
            "comments": "Perfect!"
        },
        is_final=True
    )

    assert sample_id_3 is not None, "Sample 3 creation failed"
    print(f"✓ Cycle 3 (final) saved: {sample_id_3}")

    # Get single sample
    sample = sql.get_sample(sample_id_1)
    assert sample is not None, "Sample retrieval failed"
    assert sample["cycle_number"] == 1
    assert sample["ingredient_concentration"]["Sugar"] == 36.5
    assert sample["questionnaire_answer"]["overall_liking"] == 7
    print("✓ Individual sample retrieved")

    # Get all samples
    samples = sql.get_session_samples(session_id)
    assert len(samples) == 3, f"Expected 3 samples, got {len(samples)}"
    print(f"✓ Retrieved {len(samples)} samples")

    # Get only final samples
    final_samples = sql.get_session_samples(session_id, only_final=True)
    assert len(final_samples) == 1, f"Expected 1 final sample, got {len(final_samples)}"
    assert final_samples[0]["is_final"] == True
    print(f"✓ Retrieved {len(final_samples)} final samples")


def test_training_data(session_id):
    """Test BO training data retrieval"""
    print("\n=== Testing Training Data Retrieval ===")

    # Get all training data
    df_all = sql.get_training_data(session_id, only_final=False)
    assert len(df_all) == 3, f"Expected 3 rows, got {len(df_all)}"
    assert "Sugar" in df_all.columns, "Sugar column not found"
    assert "Salt" in df_all.columns, "Salt column not found"
    assert "target_value" in df_all.columns, "target_value column not found"
    print(f"✓ Retrieved training data: {len(df_all)} rows")
    print(f"  Columns: {list(df_all.columns)}")
    print(f"  Sample data:\n{df_all.head()}")

    # Get only final training data
    df_final = sql.get_training_data(session_id, only_final=True)
    assert len(df_final) == 1, f"Expected 1 row, got {len(df_final)}"
    print(f"✓ Retrieved final training data: {len(df_final)} rows")


def test_export_csv(session_id):
    """Test CSV export"""
    print("\n=== Testing CSV Export ===")

    csv_data = sql.export_session_csv(session_id)
    assert len(csv_data) > 0, "CSV export failed"
    assert "session_id" in csv_data, "Missing session_id column"
    assert "cycle_number" in csv_data, "Missing cycle_number column"
    assert "concentration_Sugar" in csv_data, "Missing concentration columns"
    assert "q_overall_liking" in csv_data, "Missing questionnaire columns"

    lines = csv_data.strip().split('\n')
    assert len(lines) == 4, f"Expected 4 lines (header + 3 rows), got {len(lines)}"
    print(f"✓ CSV exported with {len(lines)-1} data rows")
    print("  Preview:")
    for line in lines[:2]:  # Header + first row
        print(f"    {line[:100]}...")


def test_session_state_updates(session_id):
    """Test session state management"""
    print("\n=== Testing Session State Updates ===")

    # Update to completed
    success = sql.update_session_state(session_id, "completed")
    assert success, "State update failed"
    print("✓ Session state updated to 'completed'")

    # Verify update
    session = sql.get_session(session_id)
    assert session["state"] == "completed", "State not updated correctly"
    print("✓ State change verified")

    # Get session stats
    stats = sql.get_session_stats(session_id)
    assert stats["total_cycles"] == 3, f"Expected 3 cycles, got {stats['total_cycles']}"
    assert stats["is_completed"] == True, "Should be marked as completed"
    print(f"✓ Session stats: {stats}")


def run_all_tests():
    """Run all tests"""
    print("=" * 60)
    print("RoboTaste Database Tests - New Architecture")
    print("=" * 60)

    try:
        # Initialize
        test_database_initialization()

        # User tests
        test_user_creation()

        # Session tests
        session_id = test_session_creation()

        # Sample/cycle tests
        test_sample_cycle(session_id)

        # BO training data tests
        test_training_data(session_id)

        # Export tests
        test_export_csv(session_id)

        # State management tests
        test_session_state_updates(session_id)

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)

        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
