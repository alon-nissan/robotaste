"""
Logging configuration for RoboTaste pump operations.
Sets up dedicated file logging for pump debugging.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_pump_logging(log_level=logging.INFO):
    """
    Configure comprehensive logging for pump operations.

    Creates:
    - Console handler (stdout) with INFO level
    - File handler (pump_operations.log) with DEBUG level
    - Formats with timestamps and module names

    Args:
        log_level: Minimum log level for console output (default: INFO)

    Returns:
        Path to log file
    """

    # Create logs directory if needed
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Create log file with timestamp
    log_file = log_dir / f"pump_operations_{datetime.now().strftime('%Y%m%d')}.log"

    # Get pump-related loggers
    pump_controller_logger = logging.getLogger("robotaste.hardware.pump_controller")
    pump_integration_logger = logging.getLogger("robotaste.core.pump_integration")

    # Set levels
    pump_controller_logger.setLevel(logging.DEBUG)
    pump_integration_logger.setLevel(logging.DEBUG)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(levelname)s | %(message)s'
    )

    # Console handler (INFO level)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)

    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Add handlers
    for logger in [pump_controller_logger, pump_integration_logger]:
        logger.handlers.clear()  # Remove existing handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    logging.info(f"Pump logging configured: {log_file}")

    return log_file


# Auto-setup when imported
setup_pump_logging()
