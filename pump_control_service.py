#!/usr/bin/env python3
"""
Pump Control Service for RoboTaste

Background service that monitors the database for pending pump operations
and controls NE-4000 syringe pumps via serial communication.

This script runs independently on the moderator's computer (where pumps
are physically connected) and coordinates with the Streamlit server through
the shared SQLite database.

Usage:
    python pump_control_service.py [--db-path PATH] [--poll-interval SECONDS]

    --db-path: Path to robotaste.db (default: robotaste/data/robotaste.db)
    --poll-interval: Time between database polls in seconds (default: 0.5)
    --log-level: Logging level (DEBUG, INFO, WARNING, ERROR) (default: INFO)
"""

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

# Add robotaste package to path
sys.path.insert(0, str(Path(__file__).parent))

from robotaste.hardware.pump_controller import (
    NE4000Pump,
    PumpConnectionError,
    PumpCommandError,
    PumpTimeoutError
)
from robotaste.utils.pump_db import (
    get_pending_operations,
    get_operation_by_id,
    mark_operation_in_progress,
    mark_operation_completed,
    mark_operation_failed,
    log_pump_command
)
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection

# Global state
pumps: Dict[int, NE4000Pump] = {}  # address -> pump instance
running = True
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """Configure logging for the service."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('pump_control_service.log')
        ]
    )


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    logger.info(f"Received signal {signum}, initiating shutdown...")
    running = False


def get_protocol_for_session(session_id: str, db_path: str) -> Optional[Dict]:
    """
    Get protocol configuration for a session.

    Args:
        session_id: Session ID
        db_path: Database path

    Returns:
        Protocol dictionary or None
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT protocol_id FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

        if not row or not row[0]:
            logger.error(f"No protocol found for session {session_id}")
            return None

        protocol_id = row[0]
        protocol = get_protocol_by_id(protocol_id)

        return protocol

    except Exception as e:
        logger.error(f"Error loading protocol for session {session_id}: {e}")
        return None


def initialize_pumps(pump_config: Dict, db_path: str) -> bool:
    """
    Initialize pump connections based on protocol configuration.

    Args:
        pump_config: Pump configuration from protocol
        db_path: Database path

    Returns:
        True if all pumps initialized successfully
    """
    global pumps

    if not pump_config.get('enabled', False):
        logger.warning("Pump control is disabled in protocol configuration")
        return False

    serial_port = pump_config.get('serial_port')
    baud_rate = pump_config.get('baud_rate', 19200)
    pump_configs = pump_config.get('pumps', [])

    if not serial_port:
        logger.error("No serial port specified in pump configuration")
        return False

    if not pump_configs:
        logger.error("No pumps configured in protocol")
        return False

    logger.info(f"Initializing {len(pump_configs)} pump(s) on {serial_port} at {baud_rate} baud")

    all_success = True

    for pump_cfg in pump_configs:
        address = pump_cfg.get('address', 0)
        ingredient = pump_cfg.get('ingredient', f'Pump{address}')

        # Skip if already connected
        if address in pumps and pumps[address].is_connected():
            logger.debug(f"Pump {address} ({ingredient}) already connected")
            continue

        try:
            # Create pump instance
            pump = NE4000Pump(
                port=serial_port,
                address=address,
                baud=baud_rate,
                timeout=5.0
            )

            # Connect to pump
            pump.connect()

            # Configure syringe diameter
            diameter = pump_cfg.get('syringe_diameter_mm', 14.567)
            pump.set_diameter(diameter)

            # Store pump instance
            pumps[address] = pump

            logger.info(f"Initialized pump {address} ({ingredient}) - diameter: {diameter}mm")

        except Exception as e:
            logger.error(f"Failed to initialize pump {address} ({ingredient}): {e}")
            all_success = False

    return all_success


def get_pump_for_ingredient(ingredient: str, pump_config: Dict) -> Optional[NE4000Pump]:
    """
    Get pump instance for a specific ingredient.

    Args:
        ingredient: Ingredient name
        pump_config: Pump configuration from protocol

    Returns:
        Pump instance or None
    """
    pump_configs = pump_config.get('pumps', [])

    for pump_cfg in pump_configs:
        if pump_cfg.get('ingredient') == ingredient:
            address = pump_cfg.get('address')
            return pumps.get(address)

    return None


def dispense_sample(operation: Dict, protocol: Dict, db_path: str) -> None:
    """
    Execute a dispensing operation.

    Args:
        operation: Operation dictionary from database
        protocol: Protocol configuration
        db_path: Database path

    Raises:
        Exception on any error
    """
    operation_id = operation['id']
    recipe_json = operation['recipe_json']
    recipe = json.loads(recipe_json)

    logger.info(f"Starting operation {operation_id}: {recipe}")

    # Get pump configuration
    pump_config = protocol.get('pump_config', {})
    if not pump_config:
        raise ValueError("Protocol does not have pump configuration")

    # Ensure pumps are initialized
    if not pumps:
        success = initialize_pumps(pump_config, db_path)
        if not success:
            raise PumpConnectionError("Failed to initialize pumps")

    # Mark operation as in progress
    mark_operation_in_progress(operation_id, db_path)

    # Get dispensing parameters
    dispensing_rate = pump_config.get('dispensing_rate_ul_min', 2000)

    # Track actual dispensed volumes
    actual_volumes = {}
    errors = []

    # Dispense each ingredient
    for ingredient, volume_ul in recipe.items():
        logger.info(f"Dispensing {volume_ul:.3f} µL of {ingredient}")

        # Get pump for this ingredient
        pump = get_pump_for_ingredient(ingredient, pump_config)

        if not pump:
            error_msg = f"No pump configured for ingredient '{ingredient}'"
            logger.error(error_msg)
            errors.append(error_msg)
            log_pump_command(
                operation_id=operation_id,
                pump_address=-1,
                command=f"DISPENSE {ingredient}",
                success=False,
                error_message=error_msg,
                db_path=db_path
            )
            continue

        if not pump.is_connected():
            error_msg = f"Pump for {ingredient} (address {pump.address}) is not connected"
            logger.error(error_msg)
            errors.append(error_msg)
            log_pump_command(
                operation_id=operation_id,
                pump_address=pump.address,
                command=f"DISPENSE {volume_ul} UL",
                success=False,
                error_message=error_msg,
                db_path=db_path
            )
            continue

        try:
            # Log start
            log_pump_command(
                operation_id=operation_id,
                pump_address=pump.address,
                command=f"START DISPENSE {volume_ul:.3f} µL at {dispensing_rate} µL/min",
                response=None,
                success=True,
                db_path=db_path
            )

            # Dispense volume (this will block until complete)
            pump.dispense_volume(
                volume_ul=volume_ul,
                rate_ul_min=dispensing_rate,
                wait=True
            )

            # Record actual volume (assuming successful dispense = requested volume)
            actual_volumes[ingredient] = volume_ul

            # Log completion
            log_pump_command(
                operation_id=operation_id,
                pump_address=pump.address,
                command=f"COMPLETED DISPENSE",
                response=f"Dispensed {volume_ul:.3f} µL",
                success=True,
                db_path=db_path
            )

            logger.info(f"Successfully dispensed {volume_ul:.3f} µL of {ingredient}")

        except (PumpCommandError, PumpTimeoutError) as e:
            error_msg = f"Pump error dispensing {ingredient}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

            # Log error
            log_pump_command(
                operation_id=operation_id,
                pump_address=pump.address,
                command=f"DISPENSE {volume_ul} UL",
                success=False,
                error_message=str(e),
                db_path=db_path
            )

            # Stop pump for safety
            try:
                pump.stop()
            except:
                pass

    # Check if any errors occurred
    if errors:
        error_summary = "; ".join(errors)
        mark_operation_failed(operation_id, error_summary, db_path)
        raise Exception(f"Dispensing failed: {error_summary}")
    else:
        mark_operation_completed(operation_id, actual_volumes, db_path)
        logger.info(f"Operation {operation_id} completed successfully")


def cleanup_pumps():
    """Disconnect all pumps gracefully."""
    global pumps

    logger.info("Cleaning up pump connections...")

    for address, pump in pumps.items():
        try:
            if pump.is_connected():
                pump.disconnect()
                logger.info(f"Disconnected pump {address}")
        except Exception as e:
            logger.error(f"Error disconnecting pump {address}: {e}")

    pumps.clear()


def main_loop(db_path: str, poll_interval: float):
    """
    Main service loop.

    Args:
        db_path: Path to database
        poll_interval: Time between polls in seconds
    """
    global running

    logger.info("Pump control service started")
    logger.info(f"Database: {db_path}")
    logger.info(f"Poll interval: {poll_interval}s")

    while running:
        try:
            # Poll for pending operations
            pending = get_pending_operations(limit=1, db_path=db_path)

            if pending:
                operation = pending[0]
                operation_id = operation['id']
                session_id = operation['session_id']

                logger.info(f"Found pending operation {operation_id} for session {session_id}")

                # Load protocol
                protocol = get_protocol_for_session(session_id, db_path)

                if not protocol:
                    error_msg = f"Could not load protocol for session {session_id}"
                    logger.error(error_msg)
                    mark_operation_failed(operation_id, error_msg, db_path)
                    continue

                # Execute dispensing
                try:
                    dispense_sample(operation, protocol, db_path)
                except Exception as e:
                    error_msg = f"Dispensing failed: {str(e)}"
                    logger.error(error_msg)
                    mark_operation_failed(operation_id, error_msg, db_path)

            # Sleep before next poll
            time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            running = False
            break

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
            time.sleep(poll_interval)

    # Cleanup
    cleanup_pumps()
    logger.info("Pump control service stopped")


def main():
    """Entry point for the service."""
    parser = argparse.ArgumentParser(description="RoboTaste Pump Control Service")

    parser.add_argument(
        '--db-path',
        type=str,
        default='robotaste/data/robotaste.db',
        help='Path to robotaste.db database file'
    )

    parser.add_argument(
        '--poll-interval',
        type=float,
        default=0.5,
        help='Time between database polls in seconds (default: 0.5)'
    )

    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Verify database exists
    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Please specify correct path with --db-path")
        sys.exit(1)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run main loop
    try:
        main_loop(str(db_path), args.poll_interval)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        cleanup_pumps()
        sys.exit(1)


if __name__ == '__main__':
    main()
