"""
Test NE-4000 volume command with ML/UL unit selection.

Tests that:
- Volumes >= 1 mL use ML unit
- Volumes < 1 mL use UL unit
- Both formats are accepted by pump
- Verification correctly handles both units
"""

import logging
import sys
from pump_controller import NE4000Pump

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

# Configuration
PORT = "/dev/cu.PL2303G-USBtoUART120"
PUMP_ADDRESS = 0

def test_volume_units():
    """Test volume commands with different magnitudes."""

    logger.info("=" * 60)
    logger.info("NE-4000 VOLUME UNIT SELECTION TEST")
    logger.info("=" * 60)

    pump = NE4000Pump(port=PORT, address=PUMP_ADDRESS)

    try:
        # Connect
        logger.info("\n1. CONNECTING TO PUMP...")
        pump.connect()
        status = pump.get_status()
        logger.info(f"✅ Connected - Status: {status['status']}")

        # Set diameter first
        pump.set_diameter(26.7)

        # Test Case 1: Large volume (should use ML)
        logger.info("\n2. TEST: Large volume (10 mL = 10000 µL)")
        logger.info("Expected: 'VOL 10.00 ML'")
        pump.set_volume(10000)
        logger.info("✅ Large volume test completed")

        # Test Case 2: Medium volume >= 1 mL (should use ML)
        logger.info("\n3. TEST: Medium volume (1.5 mL = 1500 µL)")
        logger.info("Expected: 'VOL 1.500 ML'")
        pump.set_volume(1500)
        logger.info("✅ Medium volume test completed")

        # Test Case 3: Exactly 1 mL (should use ML)
        logger.info("\n4. TEST: Exactly 1 mL (1000 µL)")
        logger.info("Expected: 'VOL 1.000 ML'")
        pump.set_volume(1000)
        logger.info("✅ 1 mL boundary test completed")

        # Test Case 4: Small volume < 1 mL (should use UL)
        logger.info("\n5. TEST: Small volume (500 µL)")
        logger.info("Expected: 'VOL 500 UL'")
        pump.set_volume(500)
        logger.info("✅ Small volume test completed")

        # Test Case 5: Very small volume (should use UL)
        logger.info("\n6. TEST: Very small volume (100 µL)")
        logger.info("Expected: 'VOL 100 UL'")
        pump.set_volume(100)
        logger.info("✅ Very small volume test completed")

        # Test Case 6: Tiny volume (should use UL with decimals)
        logger.info("\n7. TEST: Tiny volume (50 µL)")
        logger.info("Expected: 'VOL 50.00 UL'")
        pump.set_volume(50)
        logger.info("✅ Tiny volume test completed")

        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED")
        logger.info("=" * 60)
        logger.info("\nCheck logs above for:")
        logger.info("  • Volumes >= 1 mL formatted as ML")
        logger.info("  • Volumes < 1 mL formatted as UL")
        logger.info("  • All commands accepted (no S? rejection)")
        logger.info("  • All verifications passed")

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return False
    finally:
        pump.disconnect()
        logger.info("\nConnection closed.")

    return True

if __name__ == "__main__":
    success = test_volume_units()
    sys.exit(0 if success else 1)
