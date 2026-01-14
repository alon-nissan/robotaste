"""
Pump Integration for RoboTaste

Handles the integration between the experiment workflow and pump control system.
Creates pump operations when entering ROBOT_PREPARING phase.

Author: RoboTaste Team
Version: 1.0
"""

import json
import logging
from typing import Dict, Optional, Any
from robotaste.core.trials import prepare_cycle_sample
from robotaste.core.calculations import calculate_stock_volumes
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection
from robotaste.utils.pump_db import create_pump_operation, get_current_operation_for_session

logger = logging.getLogger(__name__)


def should_create_pump_operation(session_id: str, protocol: Dict[str, Any]) -> bool:
    """
    Check if pump operation should be created for the current cycle.

    Args:
        session_id: Session ID
        protocol: Protocol configuration

    Returns:
        True if pump operation should be created
    """
    # Check if pump control is enabled in protocol
    pump_config = protocol.get("pump_config", {})
    if not pump_config.get("enabled", False):
        logger.debug("Pump control is disabled in protocol")
        return False

    # Check if there's already a pending/in_progress operation for this session
    existing_operation = get_current_operation_for_session(session_id)
    if existing_operation:
        logger.debug(f"Pump operation already exists for session {session_id}: {existing_operation['id']}")
        return False

    return True


def create_pump_operation_for_cycle(
    session_id: str,
    cycle_number: int,
    trial_number: int = 1,
    db_path: Optional[str] = None
) -> Optional[int]:
    """
    Create a pump operation for the current cycle.

    This function is called when entering ROBOT_PREPARING phase.
    It calculates the required volumes and creates a database entry
    that the pump control service will pick up.

    Args:
        session_id: Session ID
        cycle_number: Current cycle number (1-indexed)
        trial_number: Trial number within cycle (default 1)
        db_path: Database path (optional)

    Returns:
        Operation ID if created, None otherwise
    """
    try:
        # Get protocol
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

        if not protocol:
            logger.error(f"Could not load protocol {protocol_id}")
            return None

        # Check if pump operation should be created
        if not should_create_pump_operation(session_id, protocol):
            return None

        logger.info(f"Creating pump operation for session {session_id}, cycle {cycle_number}")

        # Get sample concentrations for this cycle
        sample_data = prepare_cycle_sample(session_id, cycle_number)
        concentrations = sample_data.get("concentrations")

        if not concentrations:
            logger.error(f"No concentrations determined for cycle {cycle_number}")
            return None

        # Get pump configuration
        pump_config = protocol.get("pump_config", {})
        total_volume_ml = pump_config.get("total_volume_ml", 10.0)

        # Calculate required stock volumes
        ingredients = protocol.get("ingredients", [])
        volumes_result = calculate_stock_volumes(
            concentrations=concentrations,
            ingredient_configs=ingredients,
            final_volume_mL=total_volume_ml
        )

        stock_volumes = volumes_result.get("stock_volumes", {})

        if not stock_volumes:
            logger.warning(f"No stock volumes to dispense for cycle {cycle_number}")
            # Still create operation but with empty recipe
            # This might happen for a zero-concentration sample

        # Check if there's a water/diluent pump and calculate dilution volume
        pump_configs = pump_config.get("pumps", [])

        # Find water/diluent pump
        water_pump = None
        for pump_cfg in pump_configs:
            ingredient_name = pump_cfg.get("ingredient", "")
            # Check if this is water or a diluent
            if ingredient_name.lower() == "water":
                water_pump = ingredient_name
                break
            # Also check in ingredients list for is_diluent flag
            for ing in ingredients:
                if ing.get("name") == ingredient_name and ing.get("is_diluent", False):
                    water_pump = ingredient_name
                    break

        # If water pump exists, calculate dilution volume
        if water_pump:
            # Calculate total volume of stock solutions
            total_stock_volume_ul = sum(stock_volumes.values())

            # Calculate water volume needed to reach total volume
            total_volume_ul = total_volume_ml * 1000
            water_volume_ul = total_volume_ul - total_stock_volume_ul

            if water_volume_ul > 0:
                stock_volumes[water_pump] = water_volume_ul
                logger.info(f"Added {water_volume_ul:.1f} µL of {water_pump} for dilution")
            elif water_volume_ul < 0:
                logger.warning(f"Stock volumes exceed total volume by {-water_volume_ul:.1f} µL")

        # Create recipe JSON
        recipe_json = json.dumps(stock_volumes)

        # Create pump operation in database
        operation_id = create_pump_operation(
            session_id=session_id,
            cycle_number=cycle_number,
            trial_number=trial_number,
            recipe_json=recipe_json,
            db_path=db_path
        )

        logger.info(f"Created pump operation {operation_id}: {stock_volumes}")

        return operation_id

    except Exception as e:
        logger.error(f"Error creating pump operation for cycle {cycle_number}: {e}", exc_info=True)
        return None


def check_pump_operation_status(session_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Check the status of the current pump operation for a session.

    Args:
        session_id: Session ID
        db_path: Database path (optional)

    Returns:
        Operation status dictionary or None
    """
    operation = get_current_operation_for_session(session_id, db_path)

    if not operation:
        return None

    return {
        "operation_id": operation["id"],
        "status": operation["status"],
        "cycle_number": operation["cycle_number"],
        "trial_number": operation["trial_number"],
        "recipe": json.loads(operation["recipe_json"]),
        "created_at": operation["created_at"],
        "started_at": operation.get("started_at"),
        "completed_at": operation.get("completed_at"),
        "error_message": operation.get("error_message"),
    }


def wait_for_pump_completion(session_id: str, timeout_seconds: int = 300) -> bool:
    """
    Wait for pump operation to complete (for synchronous workflows).

    Args:
        session_id: Session ID
        timeout_seconds: Maximum time to wait

    Returns:
        True if completed successfully, False if failed or timeout
    """
    import time

    start_time = time.time()
    last_status = None

    while time.time() - start_time < timeout_seconds:
        status = check_pump_operation_status(session_id)

        if not status:
            # No operation found
            return False

        current_status = status["status"]

        # Log status changes
        if current_status != last_status:
            logger.info(f"Pump operation status: {current_status}")
            last_status = current_status

        if current_status == "completed":
            logger.info("Pump operation completed successfully")
            return True
        elif current_status == "failed":
            logger.error(f"Pump operation failed: {status.get('error_message')}")
            return False

        # Sleep briefly before checking again
        time.sleep(0.5)

    logger.error(f"Pump operation timeout after {timeout_seconds} seconds")
    return False


def calculate_total_pump_time(
    recipe_volumes: Dict[str, float],
    pump_config: Dict[str, Any],
    buffer_percent: float = 10.0
) -> float:
    """
    Calculate total time needed for pump operation.

    Args:
        recipe_volumes: {"Sugar": 125.0, "Salt": 40.0} in µL
        pump_config: Pump configuration from protocol
        buffer_percent: Safety buffer (default 10%)

    Returns:
        Total time in seconds needed for dispensing
    """
    dispensing_rate = pump_config.get("dispensing_rate_ul_min", 2000)
    simultaneous = pump_config.get("simultaneous_dispensing", True)

    if simultaneous:
        # All pumps run in parallel - use max time
        max_time = 0
        for volume_ul in recipe_volumes.values():
            if volume_ul > 0:
                time_seconds = (volume_ul / dispensing_rate) * 60
                max_time = max(max_time, time_seconds)

        total_time = max_time
    else:
        # Sequential dispensing - sum all times
        total_time = 0
        for volume_ul in recipe_volumes.values():
            if volume_ul > 0:
                time_seconds = (volume_ul / dispensing_rate) * 60
                total_time += time_seconds

    # Add buffer
    total_time_with_buffer = total_time * (1 + buffer_percent / 100)

    logger.debug(
        f"Calculated pump time: {total_time:.2f}s "
        f"(with {buffer_percent}% buffer: {total_time_with_buffer:.2f}s)"
    )

    return total_time_with_buffer


def get_pump_operation_duration(
    session_id: str,
    cycle_number: int,
    db_path: Optional[str] = None
) -> Optional[float]:
    """
    Get estimated duration for a pump operation.

    Args:
        session_id: Session identifier
        cycle_number: Cycle number
        db_path: Database path (optional)

    Returns:
        Duration in seconds, or None if no operation or pump disabled
    """
    try:
        # Get protocol
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

        if not protocol:
            logger.error(f"Could not load protocol {protocol_id}")
            return None

        pump_config = protocol.get("pump_config", {})

        if not pump_config.get("enabled", False):
            return None

        # Get current operation for session
        operation = get_current_operation_for_session(session_id, db_path)

        if not operation:
            logger.warning(f"No pump operation found for session {session_id}")
            return None

        # Parse recipe
        recipe = json.loads(operation["recipe_json"])

        # Calculate time
        duration = calculate_total_pump_time(recipe, pump_config)
        logger.info(f"Pump operation duration for cycle {cycle_number}: {duration:.2f}s")

        return duration

    except Exception as e:
        logger.error(f"Error calculating pump operation duration: {e}", exc_info=True)
        return None


def execute_pumps_synchronously(
    session_id: str,
    cycle_number: int,
    streamlit_container=None
) -> Dict[str, Any]:
    """
    Execute pump dispensing synchronously with live UI updates.

    Args:
        session_id: Session identifier
        cycle_number: Current cycle number
        streamlit_container: Streamlit container for UI updates (optional)

    Returns:
        Dict with:
            - success: bool
            - recipe: Dict of actual dispensed volumes
            - duration: Total time taken
            - error: Error message if failed
    """
    import time

    start_time = time.time()
    result = {
        "success": False,
        "recipe": {},
        "duration": 0,
        "error": None
    }

    # Helper for UI logging
    def ui_log(message, level="info"):
        """Log to both terminal and Streamlit UI."""
        if level == "info":
            logger.info(message)
            if streamlit_container:
                streamlit_container.info(message)
        elif level == "success":
            logger.info(message)
            if streamlit_container:
                streamlit_container.success(message)
        elif level == "error":
            logger.error(message)
            if streamlit_container:
                streamlit_container.error(message)
        elif level == "warning":
            logger.warning(message)
            if streamlit_container:
                streamlit_container.warning(message)

    try:
        # Import pump controller (lazy import to avoid circular dependencies)
        from robotaste.hardware.pump_controller import (
            NE4000Pump,
            PumpConnectionError,
            PumpCommandError,
            PumpTimeoutError
        )

        # 1. Get protocol and pump config
        ui_log("📋 Loading protocol and pump configuration...")

        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT protocol_id FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

        if not row or not row[0]:
            raise ValueError(f"No protocol found for session {session_id}")

        protocol = get_protocol_by_id(row[0])
        pump_config = protocol.get("pump_config", {})

        if not pump_config.get("enabled", False):
            raise ValueError("Pump config not enabled in protocol")

        ui_log(f"✅ Protocol loaded: {protocol.get('name', 'Unknown')}")

        # 2. Calculate recipe
        ui_log(f"🧮 Calculating recipe for cycle {cycle_number}...")

        sample_data = prepare_cycle_sample(session_id, cycle_number)
        concentrations = sample_data.get("concentrations")

        if not concentrations:
            raise ValueError(f"No concentrations determined for cycle {cycle_number}")

        ui_log(f"Target concentrations: {', '.join(f'{k}={v:.1f}mM' for k, v in concentrations.items())}")

        # Calculate volumes
        total_volume_ml = pump_config.get("total_volume_ml", 10.0)
        ingredients = protocol.get("ingredients", [])

        volumes_result = calculate_stock_volumes(
            concentrations=concentrations,
            ingredient_configs=ingredients,
            final_volume_mL=total_volume_ml
        )

        stock_volumes = volumes_result.get("stock_volumes", {})

        # Add water dilution if needed
        pump_configs = pump_config.get("pumps", [])
        for pump_cfg in pump_configs:
            ingredient_name = pump_cfg.get("ingredient", "")
            if ingredient_name.lower() == "water":
                total_stock = sum(stock_volumes.values())
                water_volume = (total_volume_ml * 1000) - total_stock
                if water_volume > 0:
                    stock_volumes[ingredient_name] = water_volume
                break

        result["recipe"] = stock_volumes

        ui_log("✅ Recipe calculated:")
        for ingredient, volume in stock_volumes.items():
            ui_log(f"  • {ingredient}: {volume:.1f} µL")

        # 3. Initialize pumps
        ui_log("🔌 Connecting to pumps...")

        serial_port = pump_config.get("serial_port")
        baud_rate = pump_config.get("baud_rate", 19200)
        dispensing_rate = pump_config.get("dispensing_rate_ul_min", 2000)
        simultaneous = pump_config.get("simultaneous_dispensing", True)

        pumps = {}
        for pump_cfg in pump_configs:
            address = pump_cfg.get("address")
            ingredient = pump_cfg.get("ingredient")
            diameter = pump_cfg.get("syringe_diameter_mm", 14.5)

            ui_log(f"  Initializing Pump {address} ({ingredient})...")

            pump = NE4000Pump(port=serial_port, address=address, baud=baud_rate, timeout=5.0)
            pump.connect()
            pump.set_diameter(diameter)

            pumps[ingredient] = pump
            ui_log(f"  ✅ Pump {address} connected and configured")

        # 4. Execute dispensing
        if simultaneous:
            ui_log("⚡ Executing simultaneous dispensing...")

            # Start all pumps
            for ingredient, volume_ul in stock_volumes.items():
                if ingredient in pumps:
                    pump = pumps[ingredient]
                    ui_log(f"  Starting {ingredient}: {volume_ul:.1f} µL...")
                    pump.dispense_volume(volume_ul, dispensing_rate, wait=False)

            # Calculate max time
            max_time = max((vol / dispensing_rate) * 60 * 1.1 for vol in stock_volumes.values())

            ui_log(f"⏳ Dispensing in progress... ({max_time:.1f}s)")

            # Wait with progress updates
            if streamlit_container:
                progress_bar = streamlit_container.progress(0)
                for i in range(int(max_time)):
                    time.sleep(1)
                    progress_bar.progress(min((i + 1) / max_time, 1.0))
            else:
                time.sleep(max_time)

            # Stop all pumps
            for ingredient, pump in pumps.items():
                pump.stop()
                ui_log(f"  ✅ {ingredient} complete", "success")

        else:
            ui_log("🔄 Executing sequential dispensing...")

            for ingredient, volume_ul in stock_volumes.items():
                if ingredient in pumps:
                    pump = pumps[ingredient]
                    ui_log(f"  Dispensing {ingredient}: {volume_ul:.1f} µL...")
                    pump.dispense_volume(volume_ul, dispensing_rate, wait=True)
                    ui_log(f"  ✅ {ingredient} complete", "success")

        # 5. Success
        result["success"] = True
        result["duration"] = time.time() - start_time

        ui_log(f"🎉 All pumps completed successfully in {result['duration']:.1f}s", "success")

        return result

    except Exception as e:
        result["error"] = str(e)
        ui_log(f"❌ Pump operation failed: {e}", "error")
        logger.exception("Pump execution error")
        return result

    finally:
        # Cleanup: disconnect all pumps
        if 'pumps' in locals():
            for ingredient, pump in pumps.items():
                try:
                    pump.disconnect()
                except:
                    pass
