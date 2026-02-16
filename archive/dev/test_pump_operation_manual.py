#!/usr/bin/env python3
"""
Manual test script to verify pump operation creation and execution.
Run this to test the pump integration without going through Streamlit.
"""
import json
import time
import sys

# Add robotaste to path
sys.path.insert(0, '.')

from robotaste.core.pump_integration import create_pump_operation_for_cycle
from robotaste.utils.pump_db import get_pending_operations, get_operation_by_id
from robotaste.data.database import get_database_connection

def test_pump_integration():
    print("=" * 70)
    print("Manual Pump Operation Test")
    print("=" * 70)

    # Load protocol
    print("\n[1/5] Loading protocol...")
    with open('protocols/test_protocol_4cycles_with_pumps_new_format.json', 'r') as f:
        protocol = json.load(f)

    protocol_id = protocol['protocol_id']
    print(f"  Protocol ID: {protocol_id}")
    print(f"  Pump enabled: {protocol['pump_config']['enabled']}")

    # Create a test session
    print("\n[2/5] Creating test session...")
    test_session_id = "test_pump_session_001"

    # Insert session into database
    with get_database_connection() as conn:
        cursor = conn.cursor()

        # Delete old test session if exists
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (test_session_id,))

        # Create new test session
        cursor.execute(
            """
            INSERT INTO sessions (session_id, session_code, protocol_id, current_phase, current_cycle, state)
            VALUES (?, ?, ?, 'robot_preparing', 1, 'active')
            """,
            (test_session_id, "TEST001", protocol_id)
        )
        conn.commit()

    print(f"  Session ID: {test_session_id}")

    # Create pump operation for cycle 1
    print("\n[3/5] Creating pump operation for cycle 1...")
    operation_id = create_pump_operation_for_cycle(
        session_id=test_session_id,
        cycle_number=1
    )

    if operation_id:
        print(f"  ✅ Operation created: {operation_id}")
    else:
        print("  ❌ Failed to create operation")
        return False

    # Check operation details
    print("\n[4/5] Checking operation details...")
    operation = get_operation_by_id(operation_id)

    if operation:
        recipe = json.loads(operation['recipe_json'])
        print(f"  Status: {operation['status']}")
        print(f"  Recipe:")
        for ingredient, volume_ul in recipe.items():
            print(f"    - {ingredient}: {volume_ul:.1f} µL")
    else:
        print("  ❌ Operation not found")
        return False

    # Check for pending operations
    print("\n[5/5] Checking for pending operations...")
    pending = get_pending_operations(limit=5)

    print(f"  Pending operations: {len(pending)}")

    if pending:
        for op in pending:
            print(f"    - Operation {op['id']} for cycle {op['cycle_number']}")
        print("\n✅ Pump operation ready for service to pick up!")
        print("\nNext step: Start pump_control_service.py to execute the operation")
        print("Run: python3 pump_control_service.py --protocol protocols/test_protocol_4cycles_with_pumps_new_format.json")
    else:
        print("  ❌ No pending operations found")
        return False

    print("\n" + "=" * 70)
    return True

if __name__ == "__main__":
    success = test_pump_integration()
    exit(0 if success else 1)
