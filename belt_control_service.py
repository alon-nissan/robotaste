#!/usr/bin/env python3
"""
Belt Control Service for RoboTaste

Background service that monitors the database for pending belt operations
and controls the conveyor belt via Arduino serial communication.

This script runs independently on the moderator's computer (where the belt
is physically connected) and coordinates with the Streamlit server through
the shared SQLite database.

Usage:
    python belt_control_service.py [--db-path PATH] [--poll-interval SECONDS]

    --db-path: Path to robotaste.db (default: robotaste.db)
    --poll-interval: Time between database polls in seconds (default: 0.5)
    --log-level: Logging level (DEBUG, INFO, WARNING, ERROR) (default: INFO)
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add robotaste package to path
sys.path.insert(0, str(Path(__file__).parent))

from robotaste.hardware.belt_controller import (
    ConveyorBelt,
    BeltConnectionError,
    BeltCommandError,
    BeltTimeoutError
)
from robotaste.utils.belt_db import (
    get_pending_belt_operations,
    get_belt_operation_by_id,
    mark_belt_operation_in_progress,
    mark_belt_operation_completed,
    mark_belt_operation_failed,
    mark_belt_operation_skipped,
    log_belt_command
)
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection

# Global state
belt: Optional[ConveyorBelt] = None
running = True
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """Configure logging for the service."""
    from robotaste.utils.logging_manager import setup_logging as configure_logging
    configure_logging(component="belt_service", log_level=log_level)


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


def initialize_belt(belt_config: Dict, db_path: str) -> bool:
    """
    Initialize belt connection based on protocol configuration.

    Args:
        belt_config: Belt configuration from protocol
        db_path: Database path

    Returns:
        True if belt initialized successfully
    """
    global belt

    if not belt_config.get('enabled', False):
        logger.warning("Belt control is disabled in protocol configuration")
        return False

    serial_port = belt_config.get('serial_port')
    baud_rate = belt_config.get('baud_rate', 9600)
    timeout = belt_config.get('timeout_seconds', 30)

    if not serial_port:
        logger.error("No serial port specified in belt configuration")
        return False

    # Check if already connected
    if belt and belt.is_connected():
        logger.debug("Belt already connected")
        return True

    logger.info(f"Initializing belt on {serial_port} at {baud_rate} baud")

    try:
        belt = ConveyorBelt(
            port=serial_port,
            baud=baud_rate,
            timeout=timeout
        )

        belt.connect()

        logger.info(f"Belt connected on {serial_port}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize belt: {e}")
        return False


def execute_belt_operation(operation: Dict, protocol: Dict, db_path: str) -> None:
    """
    Execute a belt operation.

    Args:
        operation: Operation dictionary from database
        protocol: Protocol configuration
        db_path: Database path

    Raises:
        Exception on any error
    """
    global belt

    operation_id = operation['id']
    operation_type = operation['operation_type']
    target_position = operation.get('target_position')
    mix_count = operation.get('mix_count')

    logger.info(f"Starting belt operation {operation_id}: {operation_type}")

    # Get belt configuration
    belt_config = protocol.get('belt_config', {})
    if not belt_config:
        raise ValueError("Protocol does not have belt configuration")

    # Ensure belt is initialized
    if not belt or not belt.is_connected():
        success = initialize_belt(belt_config, db_path)
        if not success:
            raise BeltConnectionError("Failed to initialize belt")

    # Mark operation as in progress
    mark_belt_operation_in_progress(operation_id, db_path)

    try:
        if operation_type == "position_spout":
            logger.info(f"Moving cup to spout position...")
            belt.move_to_spout(wait=True)
            log_belt_command(operation_id, "MOVE_TO_SPOUT", "OK", True, db_path=db_path)
            
        elif operation_type == "position_display":
            logger.info(f"Moving cup to display position...")
            belt.move_to_display(wait=True)
            log_belt_command(operation_id, "MOVE_TO_DISPLAY", "OK", True, db_path=db_path)
            
        elif operation_type == "mix":
            oscillations = mix_count or 5
            logger.info(f"Mixing with {oscillations} oscillations...")
            belt.mix(oscillations=oscillations, wait=True)
            log_belt_command(operation_id, f"MIX {oscillations}", "OK", True, db_path=db_path)
            
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

        # Mark as completed
        mark_belt_operation_completed(operation_id, db_path)
        logger.info(f"Belt operation {operation_id} completed successfully")

    except (BeltCommandError, BeltTimeoutError) as e:
        error_msg = str(e)
        logger.error(f"Belt operation {operation_id} failed: {error_msg}")
        log_belt_command(operation_id, operation_type, None, False, error_msg, db_path)

        # For mixing operations, skip and continue
        if operation_type == "mix":
            mark_belt_operation_skipped(operation_id, f"Mixing skipped: {error_msg}", db_path)
            logger.warning(f"Mixing skipped, continuing with next operation")
        else:
            mark_belt_operation_failed(operation_id, error_msg, db_path)
            raise


def cleanup_belt():
    """Disconnect belt gracefully."""
    global belt

    logger.info("Cleaning up belt connection...")

    if belt:
        try:
            if belt.is_connected():
                belt.disconnect()
                logger.info("Belt disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting belt: {e}")

    belt = None


def main_loop(db_path: str, poll_interval: float):
    """
    Main service loop.

    Args:
        db_path: Path to database
        poll_interval: Time between polls in seconds
    """
    global running

    logger.info("Belt control service started")
    logger.info(f"Database: {db_path}")
    logger.info(f"Poll interval: {poll_interval}s")

    while running:
        try:
            # Poll for pending operations
            pending = get_pending_belt_operations(limit=1, db_path=db_path)

            if pending:
                operation = pending[0]
                operation_id = operation['id']
                session_id = operation['session_id']

                logger.info(f"Found pending belt operation {operation_id} for session {session_id}")

                # Load protocol
                protocol = get_protocol_for_session(session_id, db_path)

                if not protocol:
                    error_msg = f"Could not load protocol for session {session_id}"
                    logger.error(error_msg)
                    mark_belt_operation_failed(operation_id, error_msg, db_path)
                    continue

                # Execute operation
                try:
                    execute_belt_operation(operation, protocol, db_path)
                except Exception as e:
                    error_msg = f"Belt operation failed: {str(e)}"
                    logger.error(error_msg)
                    # Already marked as failed in execute_belt_operation

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
    cleanup_belt()
    logger.info("Belt control service stopped")


def main():
    """Entry point for the service."""
    parser = argparse.ArgumentParser(description="RoboTaste Belt Control Service")

    parser.add_argument(
        '--db-path',
        type=str,
        default='robotaste.db',
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
        cleanup_belt()
        sys.exit(1)


if __name__ == '__main__':
    main()
