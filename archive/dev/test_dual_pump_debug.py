#!/usr/bin/env python3
"""
Debug test for dual NE-4000 pump setup.
Verifies both pumps are connected and addressable.
"""
from pump_controller import NE4000Pump
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

PORT = "/dev/cu.PL2303G-USBtoUART120"
SYRINGE_DIAMETER_MM = 14.5

def run_dual_pump_debug():
    print("=" * 60)
    print("NE-4000 Dual Pump Debug Test")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Expected: Pump 0 (address 0) and Pump 1 (address 1)")
    print("=" * 60)

    # Initialize both pumps
    pump_0 = NE4000Pump(port=PORT, address=0, timeout=2.0)
    pump_1 = NE4000Pump(port=PORT, address=1, timeout=2.0)

    try:
        # Test Pump 0
        print("\n[1/4] Testing Pump 0 (address 0)...")
        pump_0.connect()
        status_0 = pump_0.get_status()
        print(f"  ✅ Pump 0: Status={status_0['status']}, Raw={status_0['raw_response']}")

        # Test Pump 1
        print("\n[2/4] Testing Pump 1 (address 1)...")
        pump_1.connect()
        status_1 = pump_1.get_status()
        print(f"  ✅ Pump 1: Status={status_1['status']}, Raw={status_1['raw_response']}")

        # Set diameters
        print("\n[3/4] Setting syringe diameters...")
        pump_0.set_diameter(SYRINGE_DIAMETER_MM)
        print(f"  ✅ Pump 0: Diameter set to {SYRINGE_DIAMETER_MM} mm")
        pump_1.set_diameter(SYRINGE_DIAMETER_MM)
        print(f"  ✅ Pump 1: Diameter set to {SYRINGE_DIAMETER_MM} mm")

        # Verify no crosstalk
        print("\n[4/4] Verifying independent addressing...")
        status_0_after = pump_0.get_status()
        status_1_after = pump_1.get_status()
        print(f"  ✅ Pump 0 still responds independently: {status_0_after['status']}")
        print(f"  ✅ Pump 1 still responds independently: {status_1_after['status']}")

        print("\n" + "=" * 60)
        print("🎉 Both pumps connected and addressable!")
        print("=" * 60)
        print(f"Pump 0: Address=0, Status={status_0_after['status']}")
        print(f"Pump 1: Address=1, Status={status_1_after['status']}")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        print("\nTroubleshooting:")
        print("1. Both pumps powered on?")
        print("2. Pump addresses set correctly? (Setup > Ad:00 and Ad:01)")
        print("3. Network cable connected? (Pump 0 'To Network' → Pump 1 'To Computer')")
        print("4. Same baud rate (19200) on both pumps?")
        return False

    finally:
        pump_0.disconnect()
        pump_1.disconnect()
        print("\n✅ Connections closed")

    return True

if __name__ == "__main__":
    run_dual_pump_debug()
