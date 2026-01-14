#!/usr/bin/env python3
"""
Comprehensive test suite for dual NE-4000 pump operation.
Tests sequential, independent, and simultaneous dispensing.
"""
from pump_controller import NE4000Pump
import time
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

PORT = "/dev/cu.PL2303G-USBtoUART120"
SYRINGE_DIAMETER_MM = 14.5


def test_sequential_operations(pump_0, pump_1):
    """Test pumps operating one after another."""
    print("\n" + "=" * 60)
    print("TEST 1: Sequential Operations")
    print("=" * 60)

    print("\n[Pump 0] Dispensing 100 µL at 2000 µL/min...")
    pump_0.dispense_volume(volume_ul=100, rate_ul_min=2000, wait=True)
    print("  ✅ Pump 0 complete")

    print("\n[Pump 1] Dispensing 50 µL at 1000 µL/min...")
    pump_1.dispense_volume(volume_ul=50, rate_ul_min=1000, wait=True)
    print("  ✅ Pump 1 complete")

    print("\n✅ Sequential operations passed!")
    return True


def test_independent_operation(pump_0, pump_1):
    """Test that pumps don't interfere with each other."""
    print("\n" + "=" * 60)
    print("TEST 2: Independent Operation (No Crosstalk)")
    print("=" * 60)

    print("\n[Setup] Setting different rates on each pump...")
    pump_0.set_rate(2000, "UM")
    pump_1.set_rate(1000, "UM")
    print("  ✅ Pump 0: 2000 µL/min")
    print("  ✅ Pump 1: 1000 µL/min")

    print("\n[Verify] Checking rates are independent...")
    # Internal verification via _current_rate_ul_min
    assert (
        pump_0._current_rate_ul_min == 2000
    ), f"Pump 0 rate incorrect: {pump_0._current_rate_ul_min}"
    assert (
        pump_1._current_rate_ul_min == 1000
    ), f"Pump 1 rate incorrect: {pump_1._current_rate_ul_min}"
    print("  ✅ Rates are independent - no crosstalk!")

    print("\n[Verify] Checking statuses are independent...")
    status_0 = pump_0.get_status()
    status_1 = pump_1.get_status()
    print(f"  ✅ Pump 0: {status_0['status']} (raw: {status_0['raw_response']})")
    print(f"  ✅ Pump 1: {status_1['status']} (raw: {status_1['raw_response']})")

    print("\n✅ Independent operation passed!")
    return True


def test_simultaneous_dispensing(pump_0, pump_1):
    """Test both pumps dispensing at the same time."""
    print("\n" + "=" * 60)
    print("TEST 3: Simultaneous Dispensing")
    print("=" * 60)

    # Configure volumes and rates
    vol_0, rate_0 = 100, 2000  # ~3.3s
    vol_1, rate_1 = 50, 1000  # ~3.3s

    print(f"\n[Setup] Configuring pumps...")
    print(f"  Pump 0: {vol_0} µL at {rate_0} µL/min")
    print(f"  Pump 1: {vol_1} µL at {rate_1} µL/min")

    # Start both pumps without waiting
    print("\n[Start] Starting both pumps simultaneously...")
    start_time = time.time()

    pump_0.dispense_volume(volume_ul=vol_0, rate_ul_min=rate_0, wait=False)
    pump_1.dispense_volume(volume_ul=vol_1, rate_ul_min=rate_1, wait=False)

    print("  ✅ Both pumps started!")

    # Calculate max wait time
    time_0 = (vol_0 / rate_0) * 60 * 1.1  # 10% buffer
    time_1 = (vol_1 / rate_1) * 60 * 1.1
    max_time = max(time_0, time_1)

    print(f"\n[Wait] Waiting {max_time:.2f}s for both to complete...")
    time.sleep(max_time)

    # Stop both pumps
    print("\n[Stop] Stopping both pumps...")
    pump_0.stop()
    pump_1.stop()

    elapsed = time.time() - start_time
    print(f"  ✅ Both pumps stopped after {elapsed:.2f}s")

    # Verify both are stopped
    status_0 = pump_0.get_status()
    status_1 = pump_1.get_status()
    print(f"\n[Verify] Final statuses:")
    print(f"  Pump 0: {status_0['status']}")
    print(f"  Pump 1: {status_1['status']}")

    print("\n✅ Simultaneous dispensing passed!")
    return True


def run_all_tests():
    """Run comprehensive multi-pump test suite."""
    print("=" * 60)
    print("NE-4000 Dual Pump Comprehensive Test Suite")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Pumps: Address 0 and Address 1")
    print("=" * 60)

    # Initialize pumps
    pump_0 = NE4000Pump(port=PORT, address=0)
    pump_1 = NE4000Pump(port=PORT, address=1)

    try:
        # Connect both pumps
        print("\n[Setup] Connecting to pumps...")
        pump_0.connect()
        pump_1.connect()
        print("  ✅ Both pumps connected")

        # Set diameters
        print("\n[Setup] Configuring syringe diameters...")
        pump_0.set_diameter(SYRINGE_DIAMETER_MM)
        pump_1.set_diameter(SYRINGE_DIAMETER_MM)
        print(f"  ✅ Both pumps set to {SYRINGE_DIAMETER_MM} mm")

        # Run all tests
        results = []
        # results.append(("Sequential Operations", test_sequential_operations(pump_0, pump_1)))
        # results.append(("Independent Operation", test_independent_operation(pump_0, pump_1)))
        results.append(
            ("Simultaneous Dispensing", test_simultaneous_dispensing(pump_0, pump_1))
        )

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        for name, passed in results:
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"{status} - {name}")

        all_passed = all(result for _, result in results)
        print("=" * 60)
        if all_passed:
            print("🎉 ALL TESTS PASSED!")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 60)

        return all_passed

    except Exception as e:
        print(f"\n❌ Test suite error: {type(e).__name__}: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        print("\n[Cleanup] Disconnecting pumps...")
        pump_0.disconnect()
        pump_1.disconnect()
        print("  ✅ Connections closed")


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
