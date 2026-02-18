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
    PumpTimeoutError,
    SeparatedBurstCommandBuilder,
    PumpBurstConfig
)
from robotaste.utils.pump_db import (
    get_pending_operations,
    get_operation_by_id,
    mark_operation_in_progress,
    mark_operation_completed,
    mark_operation_failed
)
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection
from robotaste.core.pump_volume_manager import update_volume_after_dispense

# Global state
pumps: Dict[int, NE4000Pump] = {}  # address -> pump instance
burst_init_sessions: Dict[str, bool] = {}  # session_id -> True if DIA/RAT/DIR/VOL-unit set
running = True
logger = logging.getLogger(__name__)


def setup_logging(log_level: str = "INFO"):
    """Configure logging for the service."""
    from robotaste.utils.logging_manager import setup_logging as configure_logging
    configure_logging(component="service", log_level=log_level)


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
    pump_config_by_ingredient = {
        cfg.get('ingredient'): cfg
        for cfg in pump_configs
        if cfg.get('ingredient')
    }

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

            logger.debug(f"Initialized pump {address} ({ingredient}) - diameter: {diameter}mm")

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


def _build_burst_configs(
    recipe: Dict[str, float],
    pump_config: Dict,
    command_delay: float = 0.2
) -> List[PumpBurstConfig]:
    """Build PumpBurstConfig list from recipe and pump_config."""
    pump_configs = pump_config.get('pumps', [])
    dispensing_rate = pump_config.get('dispensing_rate_ul_min', 2000)

    configs = []
    for pump_cfg in pump_configs:
        ingredient = pump_cfg.get('ingredient')
        address = pump_cfg.get('address')
        if address is None or ingredient is None:
            continue
        volume_ul = recipe.get(ingredient, 0)
        if volume_ul < 0.001:
            continue
        configs.append(PumpBurstConfig(
            address=address,
            rate_ul_min=dispensing_rate,
            volume_ul=volume_ul,
            diameter_mm=pump_cfg.get('syringe_diameter_mm', 26.7),
            volume_unit=pump_cfg.get('volume_unit', 'ML'),
            direction="INF"
        ))
    return configs


def _burst_init_pumps(session_id: str, pump_config: Dict, command_delay: float = 0.3) -> None:
    """
    One-time burst init: set DIA, RAT, VOL unit, DIR for all pumps.
    Called once per session on the first burst dispensing cycle.
    """
    if burst_init_sessions.get(session_id, False):
        logger.debug(f"Burst parameters already initialized for session {session_id}")
        return

    logger.info(f"⚡ Initializing burst parameters for session {session_id}...")

    # Build configs with volume=0 (just need address/diameter/rate/unit/dir)
    pump_configs = pump_config.get('pumps', [])
    dispensing_rate = pump_config.get('dispensing_rate_ul_min', 2000)

    configs = []
    for pump_cfg in pump_configs:
        address = pump_cfg.get('address')
        if address is None:
            continue
        configs.append(PumpBurstConfig(
            address=address,
            rate_ul_min=dispensing_rate,
            volume_ul=0,
            diameter_mm=pump_cfg.get('syringe_diameter_mm', 26.7),
            volume_unit=pump_cfg.get('volume_unit', 'ML'),
            direction="INF"
        ))

    if not configs:
        raise ValueError("No pump configurations found for burst init")

    any_pump = next(iter(pumps.values()))
    builder = SeparatedBurstCommandBuilder

    # 1. Diameters
    logger.info(f"  📏 Setting diameters for {len(configs)} pumps...")
    cmd = builder.build_diameter_command(configs)
    any_pump._send_burst_command(cmd)
    time.sleep(command_delay)

    # 2. Rates
    logger.info(f"  ⚡ Setting rates...")
    cmd = builder.build_rate_command(configs)
    any_pump._send_burst_command(cmd)
    time.sleep(command_delay)

    # 3. Volume units
    logger.info(f"  📐 Setting volume units...")
    cmd = builder.build_volume_unit_command(configs)
    any_pump._send_burst_command(cmd)
    time.sleep(command_delay)

    # 4. Directions
    logger.info(f"  ➡️ Setting directions...")
    cmd = builder.build_direction_command(configs)
    any_pump._send_burst_command(cmd)
    time.sleep(command_delay)

    # 5. Verify
    logger.info(f"  🔍 Verifying burst parameters...")
    verify_cmd = builder.build_verification_command(configs, "DIA")
    any_pump._send_burst_command(verify_cmd)
    time.sleep(command_delay)
    verify_cmd = builder.build_verification_command(configs, "RAT")
    any_pump._send_burst_command(verify_cmd)

    burst_init_sessions[session_id] = True
    logger.info(f"✅ Burst parameters initialized for session {session_id}")


def dispense_burst_mode(
    operation: Dict,
    recipe: Dict[str, float],
    pump_config: Dict,
    db_path: str,
    command_delay: float = 0.2
) -> Dict[str, float]:
    """
    Execute dispensing using burst mode (separated commands).

    Sends multi-pump burst commands: VOL values → verify → RUN.
    DIA/RAT/DIR/VOL-unit are set once per session via _burst_init_pumps().

    Returns:
        Dict of actual dispensed volumes {ingredient: volume_ul}
    """
    session_id = operation['session_id']
    dispensing_rate = pump_config.get('dispensing_rate_ul_min', 2000)

    # One-time init if needed
    _burst_init_pumps(session_id, pump_config)

    # Build per-cycle configs with actual volumes
    configs = _build_burst_configs(recipe, pump_config)

    if not configs:
        logger.warning("⚠️ All pump volumes are ~0, skipping burst dispensing")
        return {}

    any_pump = next(iter(pumps.values()))
    builder = SeparatedBurstCommandBuilder

    logger.info(f"⚡ Burst dispensing {len(configs)} pumps...")

    # 1. Set volumes
    vol_cmd = builder.build_volume_value_command(configs)
    logger.info(f"  💧 Setting volumes: {vol_cmd}")
    any_pump._send_burst_command(vol_cmd)
    time.sleep(command_delay)

    # 2. Verify volumes
    verify_cmd = builder.build_verification_command(configs, "VOL")
    logger.info(f"  🔍 Verifying volumes...")
    any_pump._send_burst_command(verify_cmd)
    time.sleep(command_delay)

    # 3. Run all pumps
    run_cmd = builder.build_run_command(configs)
    logger.info(f"  🚀 Starting all pumps: {run_cmd}")
    any_pump._send_burst_command(run_cmd)

    # 4. Wait for longest pump to finish
    max_time = max((c.volume_ul / dispensing_rate) * 60 * 1.1 for c in configs)
    logger.info(f"⏳ Dispensing in progress... ({max_time:.1f}s)")
    time.sleep(max_time)

    # 5. Stop all pumps (individual commands for safety)
    actual_volumes = {}
    for c in configs:
        pump = pumps.get(c.address)
        if pump:
            pump.stop()
            # Map address back to ingredient name
            for pump_cfg in pump_config.get('pumps', []):
                if pump_cfg.get('address') == c.address:
                    ingredient = pump_cfg.get('ingredient', f'Pump{c.address}')
                    actual_volumes[ingredient] = c.volume_ul
                    logger.debug(f"  ✅ {ingredient} complete: {c.volume_ul:.1f}µL")
                    break

    logger.info(f"✅ Burst dispensing complete: {actual_volumes}")
    return actual_volumes


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
    
    # Parse JSON with error handling to prevent service crashes
    try:
        recipe = json.loads(recipe_json)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid recipe JSON for operation {operation_id}: {e}"
        logger.error(error_msg)
        mark_operation_failed(operation_id, error_msg, db_path)
        raise ValueError(error_msg)

    logger.info(f"Starting operation {operation_id}: {recipe}")

    # Get pump configuration
    pump_config = protocol.get('pump_config', {})
    pump_configs = pump_config.get('pumps', [])
    pump_config_by_ingredient = {
        cfg.get('ingredient'): cfg
        for cfg in pump_configs
        if cfg.get('ingredient')
    }
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
    simultaneous = pump_config.get('simultaneous_dispensing', False)
    use_burst_mode = pump_config.get('use_burst_mode', False)
    pump_addresses = [cfg.get('address', 0) for cfg in pump_configs]
    burst_compatible = all(addr <= 9 for addr in pump_addresses)

    # Track actual dispensed volumes
    actual_volumes = {}
    errors = []

    logger.info(f"Dispensing mode: burst={use_burst_mode}, simultaneous={simultaneous}, burst_compatible={burst_compatible}")

    if use_burst_mode and burst_compatible and simultaneous:
        # Burst mode - send multi-pump commands via network burst protocol
        try:
            actual_volumes = dispense_burst_mode(operation, recipe, pump_config, db_path)
        except Exception as e:
            error_msg = f"Burst dispensing failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

    elif simultaneous:
        # Individual simultaneous dispensing - start all pumps, then wait
        if use_burst_mode and not burst_compatible:
            logger.warning(f"⚠️ Burst mode requires addresses 0-9, got {pump_addresses}. Falling back to simultaneous.")

        logger.info(f"Starting simultaneous dispensing of {len(recipe)} ingredients")

        # Prepare pump list
        pump_info = []

        for ingredient, volume_ul in recipe.items():
            pump = get_pump_for_ingredient(ingredient, pump_config)

            if not pump:
                error_msg = f"No pump configured for ingredient '{ingredient}'"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            if not pump.is_connected():
                error_msg = f"Pump for {ingredient} (address {pump.address}) is not connected"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            pump_info.append((ingredient, pump, volume_ul))

        if errors:
            error_summary = "; ".join(errors)
            raise Exception(f"Cannot start simultaneous dispensing: {error_summary}")

        # Start all pumps without waiting
        for ingredient, pump, volume_ul in pump_info:
            try:
                volume_unit = pump_config_by_ingredient.get(
                    ingredient, {}
                ).get('volume_unit', 'ML')
                if volume_unit not in ['ML', 'UL']:
                    raise ValueError(
                        f"Invalid volume_unit '{volume_unit}' for pump '{ingredient}'"
                    )

                pump.dispense_volume(
                    volume_ul=volume_ul,
                    rate_ul_min=dispensing_rate,
                    wait=False,  # Don't wait, start next pump
                    volume_unit=volume_unit,
                )
                logger.debug(f"Started pump {pump.address} ({ingredient}): {volume_ul:.3f}µL")

            except (PumpCommandError, PumpTimeoutError) as e:
                error_msg = f"Failed to start pump for {ingredient}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        if errors:
            # Stop all pumps if any failed to start
            for ingredient, pump, volume_ul in pump_info:
                try:
                    pump.stop()
                except Exception as e:
                    logger.warning(f"Failed to stop pump for {ingredient} during cleanup: {e}")
            error_summary = "; ".join(errors)
            raise Exception(f"Failed to start pumps: {error_summary}")

        # Calculate max wait time
        max_time = 0
        for ingredient, pump, volume_ul in pump_info:
            time_needed = (volume_ul / dispensing_rate) * 60 * 1.1  # 10% buffer
            max_time = max(max_time, time_needed)

        logger.info(f"Waiting {max_time:.2f}s for all pumps to complete")
        time.sleep(max_time)

        # Stop all pumps and record volumes
        for ingredient, pump, volume_ul in pump_info:
            try:
                pump.stop()
                actual_volumes[ingredient] = volume_ul
                logger.debug(f"Completed pump {pump.address} ({ingredient}): {volume_ul:.3f}µL")

            except Exception as e:
                error_msg = f"Error stopping pump for {ingredient}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

    else:
        # Sequential dispensing - one ingredient at a time
        logger.info(f"Starting sequential dispensing of {len(recipe)} ingredients")

        for ingredient, volume_ul in recipe.items():
            logger.debug(f"Dispensing {volume_ul:.3f} µL of {ingredient}")

            # Get pump for this ingredient
            pump = get_pump_for_ingredient(ingredient, pump_config)

            if not pump:
                error_msg = f"No pump configured for ingredient '{ingredient}'"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            if not pump.is_connected():
                error_msg = f"Pump for {ingredient} (address {pump.address}) is not connected"
                logger.error(error_msg)
                errors.append(error_msg)
                continue

            try:
                volume_unit = pump_config_by_ingredient.get(
                    ingredient, {}
                ).get('volume_unit', 'ML')
                if volume_unit not in ['ML', 'UL']:
                    raise ValueError(
                        f"Invalid volume_unit '{volume_unit}' for pump '{ingredient}'"
                    )

                # Dispense volume (this will block until complete)
                pump.dispense_volume(
                    volume_ul=volume_ul,
                    rate_ul_min=dispensing_rate,
                    wait=True,
                    volume_unit=volume_unit,
                )

                # Record actual volume (assuming successful dispense = requested volume)
                actual_volumes[ingredient] = volume_ul

                logger.debug(f"Successfully dispensed {volume_ul:.3f} µL of {ingredient}")

            except (PumpCommandError, PumpTimeoutError) as e:
                error_msg = f"Pump error dispensing {ingredient}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

                # Stop pump for safety
                try:
                    pump.stop()
                except Exception as e:
                    logger.warning(f"Failed to stop pump for {ingredient} during error recovery: {e}")

    # Check if any errors occurred
    if errors:
        error_summary = "; ".join(errors)
        mark_operation_failed(operation_id, error_summary, db_path)
        raise Exception(f"Dispensing failed: {error_summary}")
    else:
        mark_operation_completed(operation_id, actual_volumes, db_path)
        logger.info(f"Operation {operation_id} completed successfully")

        # Update volume tracking so moderator dashboard stays in sync
        try:
            update_volume_after_dispense(
                db_path=db_path,
                session_id=operation['session_id'],
                actual_volumes=actual_volumes,
                cycle_number=operation['cycle_number'],
            )
        except Exception as e:
            logger.warning(f"Volume tracking update failed (non-fatal): {e}")


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
        cleanup_pumps()
        sys.exit(1)


if __name__ == '__main__':
    main()
