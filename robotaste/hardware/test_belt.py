#!/usr/bin/env python3
"""
Belt Controller Hardware Test Script

Interactive test script for verifying belt controller functionality.
Requires physical belt hardware to be connected.

Usage:
    python robotaste/hardware/test_belt.py [--port PORT] [--mock]

Author: RoboTaste Team
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from robotaste.hardware.belt_controller import (
    ConveyorBelt,
    BeltConnectionError,
    BeltCommandError,
    BeltTimeoutError,
    BeltPosition,
    BeltStatus
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_connection(belt: ConveyorBelt) -> bool:
    """Test basic connection."""
    print("\n=== Test 1: Connection ===")
    try:
        belt.connect()
        print(f"✅ Connected to belt on {belt.port}")
        print(f"   Status: {belt.get_status().value}")
        print(f"   Position: {belt.get_position().value}")
        return True
    except BeltConnectionError as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_move_to_spout(belt: ConveyorBelt) -> bool:
    """Test moving cup to spout position."""
    print("\n=== Test 2: Move to Spout ===")
    try:
        print("Moving cup to spout...")
        start = time.time()
        belt.move_to_spout(wait=True)
        elapsed = time.time() - start
        print(f"✅ Cup at spout (took {elapsed:.2f}s)")
        print(f"   Position: {belt.get_position().value}")
        return True
    except (BeltCommandError, BeltTimeoutError) as e:
        print(f"❌ Move to spout failed: {e}")
        return False


def test_move_to_display(belt: ConveyorBelt) -> bool:
    """Test moving cup to display position."""
    print("\n=== Test 3: Move to Display ===")
    try:
        print("Moving cup to display...")
        start = time.time()
        belt.move_to_display(wait=True)
        elapsed = time.time() - start
        print(f"✅ Cup at display (took {elapsed:.2f}s)")
        print(f"   Position: {belt.get_position().value}")
        return True
    except (BeltCommandError, BeltTimeoutError) as e:
        print(f"❌ Move to display failed: {e}")
        return False


def test_mixing(belt: ConveyorBelt, oscillations: int = 3) -> bool:
    """Test mixing oscillation."""
    print(f"\n=== Test 4: Mixing ({oscillations} oscillations) ===")
    try:
        # First ensure cup is at spout
        belt.move_to_spout(wait=True)
        
        print(f"Starting mixing with {oscillations} oscillations...")
        start = time.time()
        belt.mix(oscillations=oscillations, wait=True)
        elapsed = time.time() - start
        print(f"✅ Mixing complete (took {elapsed:.2f}s)")
        return True
    except (BeltCommandError, BeltTimeoutError) as e:
        print(f"❌ Mixing failed: {e}")
        return False


def test_full_cycle(belt: ConveyorBelt) -> bool:
    """Test full operation cycle: spout -> mix -> display."""
    print("\n=== Test 5: Full Cycle ===")
    try:
        print("Step 1: Moving to spout...")
        belt.move_to_spout(wait=True)
        print("   ✓ At spout")
        
        print("Step 2: Simulating dispense (waiting 2s)...")
        time.sleep(2.0)
        print("   ✓ Dispense complete")
        
        print("Step 3: Mixing (5 oscillations)...")
        belt.mix(oscillations=5, wait=True)
        print("   ✓ Mixing complete")
        
        print("Step 4: Moving to display...")
        belt.move_to_display(wait=True)
        print("   ✓ At display")
        
        print("✅ Full cycle complete!")
        return True
    except (BeltCommandError, BeltTimeoutError) as e:
        print(f"❌ Full cycle failed: {e}")
        return False


def test_emergency_stop(belt: ConveyorBelt) -> bool:
    """Test emergency stop functionality."""
    print("\n=== Test 6: Emergency Stop ===")
    try:
        print("Starting movement and then stopping...")
        belt.move_to_spout(wait=False)  # Don't wait
        time.sleep(0.2)  # Let it start moving
        belt.stop()
        print(f"✅ Emergency stop executed")
        print(f"   Status: {belt.get_status().value}")
        return True
    except Exception as e:
        print(f"❌ Emergency stop test failed: {e}")
        return False


def interactive_mode(belt: ConveyorBelt) -> None:
    """Interactive command mode for manual testing."""
    print("\n=== Interactive Mode ===")
    print("Commands:")
    print("  s - Move to spout")
    print("  d - Move to display")
    print("  m - Mix (5 oscillations)")
    print("  M - Mix (custom count)")
    print("  x - Emergency stop")
    print("  ? - Status")
    print("  q - Quit")
    print()

    while True:
        try:
            cmd = input("Belt> ").strip().lower()

            if cmd == 'q':
                print("Exiting...")
                break
            elif cmd == 's':
                belt.move_to_spout()
            elif cmd == 'd':
                belt.move_to_display()
            elif cmd == 'm':
                belt.mix(oscillations=5)
            elif cmd == 'M' or cmd == 'mix':
                count = int(input("Oscillation count: "))
                belt.mix(oscillations=count)
            elif cmd == 'x':
                belt.stop()
            elif cmd == '?':
                print(f"Status: {belt.get_status().value}")
                print(f"Position: {belt.get_position().value}")
            else:
                print("Unknown command. Use 's', 'd', 'm', 'x', '?', or 'q'")

        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Belt Controller Hardware Test")
    parser.add_argument(
        '--port',
        type=str,
        default='/dev/tty.usbmodem14101',
        help='Serial port for belt controller'
    )
    parser.add_argument(
        '--baud',
        type=int,
        default=9600,
        help='Baud rate (default: 9600)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Run in mock mode (no hardware required)'
    )
    parser.add_argument(
        '--interactive',
        '-i',
        action='store_true',
        help='Enter interactive mode after tests'
    )
    parser.add_argument(
        '--skip-tests',
        action='store_true',
        help='Skip automated tests, go straight to interactive mode'
    )

    args = parser.parse_args()

    print("=" * 50)
    print("RoboTaste Belt Controller Hardware Test")
    print("=" * 50)
    print(f"Port: {args.port}")
    print(f"Baud: {args.baud}")
    print(f"Mock mode: {args.mock}")

    belt = ConveyorBelt(
        port=args.port,
        baud=args.baud,
        mock_mode=args.mock
    )

    try:
        # Run tests
        if not args.skip_tests:
            results = []

            # Test 1: Connection
            if not test_connection(belt):
                print("\n❌ Cannot continue without connection")
                return 1

            # Test 2-6: Movement and mixing tests
            results.append(("Move to Spout", test_move_to_spout(belt)))
            results.append(("Move to Display", test_move_to_display(belt)))
            results.append(("Mixing", test_mixing(belt, oscillations=3)))
            results.append(("Full Cycle", test_full_cycle(belt)))
            results.append(("Emergency Stop", test_emergency_stop(belt)))

            # Summary
            print("\n" + "=" * 50)
            print("TEST SUMMARY")
            print("=" * 50)
            for name, passed in results:
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"  {name}: {status}")

            passed_count = sum(1 for _, p in results if p)
            total_count = len(results)
            print(f"\nTotal: {passed_count}/{total_count} tests passed")

        # Interactive mode
        if args.interactive or args.skip_tests:
            if not belt.is_connected():
                belt.connect()
            interactive_mode(belt)

    finally:
        belt.disconnect()
        print("\nBelt disconnected. Test complete.")

    return 0


if __name__ == '__main__':
    sys.exit(main())
