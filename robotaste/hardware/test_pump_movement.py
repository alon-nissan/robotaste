from pump_controller import NE4000Pump
import time

# --- CONFIGURATION ---
# REPLACE THIS with the port you found (e.g., "/dev/tty.usbserial-AB123")
PORT = "/dev/cu.PL2303G-USBtoUART120"

# Check your syringe! A BD 10mL syringe is usually ~14.5mm.
# Check Page 48 of the manual if unsure.
SYRINGE_DIAMETER_MM = 14.5
# ---------------------


def run_test():
    print(f"Attempting to connect to pump on {PORT}...")

    # Initialize controller (assuming Address 0 for single pump)
    pump = NE4000Pump(port=PORT, address=0)

    try:
        # 1. Connect
        pump.connect()
        status = pump.get_status()
        print(f"✅ Connection Successful! Pump Status: {status['status']}")

        # 2. Configure Syringe
        print(f"Setting syringe diameter to {SYRINGE_DIAMETER_MM} mm...")
        pump.set_diameter(SYRINGE_DIAMETER_MM)

        # 3. Movement Test (Dry Run)
        print("▶️ TEST: Dispensing 0.1 mL (100 µL)...")
        # dispense_volume(volume_ul, rate_ul_min, wait=True)
        pump.dispense_volume(volume_ul=100, rate_ul_min=2000, wait=True)

        print("✅ Dispense complete.")

    except Exception as e:
        print(f"❌ Error: {e}")
        print("Troubleshooting tips:")
        print(
            "1. Check if the pump address is set to 00 on the physical device (Setup > Ad:00)."
        )
        print("2. Check if the baud rate on the device is 19200.")
    finally:
        pump.disconnect()
        print("Connection closed.")


if __name__ == "__main__":
    run_test()
