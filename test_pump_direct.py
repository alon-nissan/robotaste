#!/usr/bin/env python3
"""
Direct pump operation test - bypasses session complexity.
Creates a pump operation directly with known volumes.
"""
import json
import sys
sys.path.insert(0, '.')

from robotaste.utils.pump_db import create_pump_operation, get_pending_operations, get_operation_by_id

def test_direct_pump_operation():
    print("=" * 70)
    print("Direct Pump Operation Test")
    print("=" * 70)

    # Create a simple test recipe (Cycle 2: 25 mM Sugar)
    # From our calculations: 250 µL sugar + 9750 µL water = 10mL
    recipe = {
        "Sugar": 250.0,
        "Water": 9750.0
    }

    print("\n[1/3] Creating pump operation...")
    print(f"  Recipe: {recipe}")

    operation_id = create_pump_operation(
        session_id="direct_test_001",
        cycle_number=1,
        trial_number=1,
        recipe_json=json.dumps(recipe)
    )

    print(f"  ✅ Operation created with ID: {operation_id}")

    # Check operation details
    print("\n[2/3] Verifying operation...")
    operation = get_operation_by_id(operation_id)

    if operation:
        print(f"  Status: {operation['status']}")
        print(f"  Session: {operation['session_id']}")
        print(f"  Cycle: {operation['cycle_number']}")
        recipe_check = json.loads(operation['recipe_json'])
        print(f"  Recipe:")
        for ingredient, volume_ul in recipe_check.items():
            print(f"    - {ingredient}: {volume_ul:.1f} µL")
    else:
        print("  ❌ Operation not found")
        return False

    # Check for pending operations
    print("\n[3/3] Checking pending operations queue...")
    pending = get_pending_operations(limit=10)

    print(f"  Total pending operations: {len(pending)}")
    for op in pending:
        print(f"    - Operation {op['id']}: Session {op['session_id']}, Cycle {op['cycle_number']}")

    print("\n" + "=" * 70)
    print("✅ PUMP OPERATION READY!")
    print("\nNext steps:")
    print("1. Make sure pumps are connected to: /dev/cu.PL2303G-USBtoUART120")
    print("2. Start pump service:")
    print("   python3 pump_control_service.py --protocol tests/test_protocol_4cycles_with_pumps.json")
    print("\n   The service will:")
    print("   - Connect to both pumps (addresses 0 and 1)")
    print("   - Pick up the pending operation")
    print("   - Dispense 250 µL sugar + 9750 µL water simultaneously")
    print("   - Complete in ~11 seconds")
    print("=" * 70)

    return True

if __name__ == "__main__":
    success = test_direct_pump_operation()
    exit(0 if success else 1)
