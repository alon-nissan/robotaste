"""
Verify NE-4000 pump command formatting fixes.

Tests that diameter, rate, and volume commands are formatted correctly
with the 4-digit constraint and accepted by the pump (no S? rejection).
"""

import logging
import sys
from pump_controller import NE4000Pump

# Configure logging to show all details
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Configuration
PORT = "/dev/cu.PL2303G-USBtoUART120"
PUMP_ADDRESS = 0

def test_formatting():
    """Test that all three command types are formatted correctly."""

    logger.info("=" * 60)
    logger.info("NE-4000 FORMATTING VERIFICATION TEST")
    logger.info("=" * 60)

    pump = NE4000Pump(port=PORT, address=PUMP_ADDRESS)

    try:
        # Connect
        logger.info("\n1. CONNECTING TO PUMP...")
        pump.connect()
        status = pump.get_status()
        logger.info(f"✅ Connected - Status: {status['status']}")

        # Test 1: Diameter formatting (should be 26.70, not 26.700)
        logger.info("\n2. TESTING DIAMETER FORMATTING...")
        logger.info("Expected format: 'DIA 26.70' (4 digits)")
        pump.set_diameter(26.7)
        logger.info("✅ Diameter command completed")

        # Test 2: Rate formatting and auto-conversion (60000 UM -> 60.00 MM)
        logger.info("\n3. TESTING RATE FORMATTING & AUTO-CONVERSION...")
        logger.info("Expected format: 'RAT 60.00 MM' (auto-converted from 60000 UM)")
        pump.set_rate(60000, "UM")
        logger.info("✅ Rate command completed")

        # Test 3: Volume formatting (10 mL should be 10.00, not 10.000000)
        logger.info("\n4. TESTING VOLUME FORMATTING...")
        logger.info("Expected format: 'VOL 10.00' (4 digits)")
        pump.set_volume(10000)  # 10000 µL = 10 mL
        logger.info("✅ Volume command completed")

        logger.info("\n" + "=" * 60)
        logger.info("VERIFICATION COMPLETE")
        logger.info("=" * 60)
        logger.info("\nCheck logs above for:")
        logger.info("  • No 'S?' rejection responses")
        logger.info("  • All verification checks passed")
        logger.info("  • Formatted values match expected (4 digits max)")

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return False
    finally:
        pump.disconnect()
        logger.info("\nConnection closed.")

    return True

if __name__ == "__main__":
    success = test_formatting()
    sys.exit(0 if success else 1)
