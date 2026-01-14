#!/usr/bin/env python3
"""
Debug test for NE-4000 pump connection.
Tests connection with verbose output and shorter timeouts.
"""
from pump_controller import NE4000Pump
import logging
import sys

# Enable debug logging to see what's happening
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

PORT = "/dev/cu.PL2303G-USBtoUART120"
SYRINGE_DIAMETER_MM = 14.5

def run_debug_test():
    print("=" * 60)
    print("NE-4000 Pump Connection Debug Test")
    print("=" * 60)
    print(f"Port: {PORT}")
    print(f"Address: 0")
    print(f"Baud: 19200")
    print(f"Timeout: 2.0 seconds (shorter for debugging)")
    print("=" * 60)

    # Use shorter timeout for debugging
    pump = NE4000Pump(port=PORT, address=0, timeout=2.0, max_retries=2)

    try:
        print("\n[1/3] Attempting to connect to pump...")
        sys.stdout.flush()

        pump.connect()
        print("✅ Connection successful!")

        print("\n[2/3] Getting pump status...")
        sys.stdout.flush()

        status = pump.get_status()
        print(f"✅ Status: {status['status']} (raw: {status['raw_response']})")

        print("\n[3/3] Setting syringe diameter...")
        sys.stdout.flush()

        pump.set_diameter(SYRINGE_DIAMETER_MM)
        print(f"✅ Diameter set to {SYRINGE_DIAMETER_MM} mm")

        print("\n" + "=" * 60)
        print("🎉 All tests passed! Pump is ready to use.")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        print("\n" + "=" * 60)
        print("Troubleshooting Guide:")
        print("=" * 60)
        print("1. Check pump power - is it turned on?")
        print("2. Check pump address - press 'Menu' > 'Setup' > verify 'Ad:00'")
        print("3. Check baud rate - press 'Menu' > 'Setup' > verify '19200'")
        print("4. Check cable connection - is USB adapter firmly connected?")
        print("5. Try unplugging and replugging the USB adapter")
        print("6. Check if another program is using the serial port")
        print("=" * 60)

    finally:
        print("\nClosing connection...")
        sys.stdout.flush()
        pump.disconnect()
        print("✅ Connection closed")

if __name__ == "__main__":
    run_debug_test()
