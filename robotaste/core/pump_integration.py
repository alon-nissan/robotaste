"""
Pump Integration for RoboTaste

Handles the integration between the experiment workflow and pump control system.
Creates pump operations when entering ROBOT_PREPARING phase.

Author: RoboTaste Team
Version: 1.1 (Separated burst commands)
"""

import json
import logging
from typing import Dict, Optional, Any, List
from robotaste.core.trials import prepare_cycle_sample
from robotaste.core.calculations import calculate_stock_volumes
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection
from robotaste.utils.pump_db import create_pump_operation, get_current_operation_for_session

logger = logging.getLogger(__name__)


def _merge_pump_config_into_ingredients(ingredients: List[Dict[str, Any]], pump_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Merge pump configuration into ingredient configurations.
    
    This overrides the default stock concentration in the ingredient list with 
    the actual stock concentration loaded in the pumps, which is essential 
    for correct volume calculations.
    
    Args:
        ingredients: List of ingredient configuration dictionaries
        pump_config: Pump configuration dictionary
        
    Returns:
        List of ingredient configs with updated stock concentrations
    """
    # Create a deep copy of ingredients to avoid modifying the original list
    effective_ingredients = [ing.copy() for ing in ingredients]
    
    pump_definitions = pump_config.get("pumps", [])
    
    for pump_def in pump_definitions:
        ing_name = pump_def.get("ingredient")
        pump_stock = pump_def.get("stock_concentration_mM")
        
        if ing_name and pump_stock is not None:
            # Find matching ingredient
            found = False
            for ing in effective_ingredients:
                if ing["name"] == ing_name:
                    ing["stock_concentration_mM"] = pump_stock
                    found = True
                    break
            
            # If not found in ingredients list but exists in pump config,
            # we might want to log a warning, but usually ingredients list is the source of truth
            if not found:
                logger.warning(f"Pump configured for '{ing_name}' but not found in ingredient list")

    return effective_ingredients


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
    db_path: Optional[str] = None,
    concentrations: Optional[Dict[str, float]] = None
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
        # Use passed concentrations first (from API endpoint), fall back to prepare_cycle_sample()
        if concentrations is None:
            sample_data = prepare_cycle_sample(session_id, cycle_number)
            concentrations = sample_data.get("concentrations")

        if not concentrations:
            logger.error(f"No concentrations determined for cycle {cycle_number}")
            return None

        # Get pump configuration
        pump_config = protocol.get("pump_config") or {}
        total_volume_ml = pump_config.get("total_volume_ml", 10.0)

        # Calculate required stock volumes
        ingredients = protocol.get("ingredients", [])
        
        # Merge pump configuration into ingredients to ensure correct stock concentrations
        effective_ingredients = _merge_pump_config_into_ingredients(ingredients, pump_config)
        
        volumes_result = calculate_stock_volumes(
            concentrations=concentrations,
            ingredient_configs=effective_ingredients,
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


def get_pump_operation_for_cycle(session_id: str, cycle_number: int) -> Optional[Dict[str, Any]]:
    """
    Get existing pump operation for a specific cycle.

    Args:
        session_id: Session UUID
        cycle_number: Cycle number to check

    Returns:
        Operation dict if exists, None otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, status, created_at, completed_at, recipe_json, error_message
                FROM pump_operations
                WHERE session_id = ? AND cycle_number = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (session_id, cycle_number))

            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "status": row[1],
                    "created_at": row[2],
                    "completed_at": row[3],
                    "recipe": json.loads(row[4]) if row[4] else {},
                    "error_message": row[5]
                }
            return None
    except Exception as e:
        logger.error(f"Error fetching pump operation for cycle {cycle_number}: {e}")
        return None


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

    # Build ingredient→pump_cfg lookup for dual syringe
    pump_cfg_by_ingredient = {
        cfg.get("ingredient"): cfg
        for cfg in pump_config.get("pumps", [])
        if cfg.get("ingredient")
    }

    def commanded_volume(ingredient: str, volume_ul: float) -> float:
        """Get actual pump command volume (halved for dual syringe)."""
        cfg = pump_cfg_by_ingredient.get(ingredient, {})
        return volume_ul / 2 if cfg.get("dual_syringe", False) else volume_ul

    if simultaneous:
        # All pumps run in parallel - use max time
        max_time = 0
        for ingredient, volume_ul in recipe_volumes.items():
            if volume_ul > 0:
                time_seconds = (commanded_volume(ingredient, volume_ul) / dispensing_rate) * 60
                max_time = max(max_time, time_seconds)

        total_time = max_time
    else:
        # Sequential dispensing - sum all times
        total_time = 0
        for ingredient, volume_ul in recipe_volumes.items():
            if volume_ul > 0:
                time_seconds = (commanded_volume(ingredient, volume_ul) / dispensing_rate) * 60
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
        """Log to file only (Streamlit UI logging disabled)."""
        if level == "info":
            logger.info(message)
        elif level == "success":
            logger.info(message)
        elif level == "error":
            logger.error(message)
        elif level == "warning":
            logger.warning(message)

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
        if not protocol:
            raise ValueError(f"Could not load protocol {row[0]}")
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
        
        # Merge pump configuration into ingredients to ensure correct stock concentrations
        effective_ingredients = _merge_pump_config_into_ingredients(ingredients, pump_config)

        volumes_result = calculate_stock_volumes(
            concentrations=concentrations,
            ingredient_configs=effective_ingredients,
            final_volume_mL=total_volume_ml
        )

        stock_volumes = volumes_result.get("stock_volumes", {})

        # Add water dilution if needed
        pump_configs = pump_config.get("pumps", [])
        pump_config_by_ingredient = {
            cfg.get("ingredient"): cfg
            for cfg in pump_configs
            if cfg.get("ingredient")
        }
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

        # 3. Initialize pumps (using session-persistent cache)
        ui_log("🔌 Connecting to pumps...")

        # Import pump manager for session-persistent connections
        from robotaste.core.pump_manager import get_or_create_pumps

        dispensing_rate = pump_config.get("dispensing_rate_ul_min", 2000)
        simultaneous = pump_config.get("simultaneous_dispensing", True)

        # Get or reuse pumps from cache
        pumps = get_or_create_pumps(session_id, pump_config)
        ui_log(f"✅ Pumps ready ({len(pumps)} pump(s) configured)")

        # 4. Execute dispensing
        if simultaneous:
            # Check if burst mode is enabled and possible
            use_burst_mode = pump_config.get("use_burst_mode", False)
            pump_addresses = [p.address for p in pumps.values()]
            burst_compatible = all(addr <= 9 for addr in pump_addresses)

            # Debug logging for burst mode decision
            logger.info(f"Burst mode check: use_burst_mode={use_burst_mode}, addresses={pump_addresses}, burst_compatible={burst_compatible}")

            if use_burst_mode and burst_compatible:
                ui_log("⚡ Executing burst mode dispensing (separated commands)...")

                # Import separated burst command builder and manager functions
                from robotaste.hardware.pump_controller import (
                    SeparatedBurstCommandBuilder,
                    PumpBurstConfig
                )
                from robotaste.core.pump_manager import (
                    is_pump_initialized,
                    initialize_pump_parameters,
                    send_volume_and_run
                )

                # Check if pump parameters are initialized
                if not is_pump_initialized(session_id):
                    ui_log("  🔧 Initializing pump parameters (first cycle)...")
                    initialize_pump_parameters(session_id, pump_config)

                # Build pump configurations (filter out 0 volume pumps)
                burst_configs = []
                for ingredient, volume_ul in stock_volumes.items():
                    if ingredient in pumps and volume_ul > 0.001:  # Skip ~0 volumes
                        pump = pumps[ingredient]
                        pump_cfg = pump_config_by_ingredient.get(ingredient, {})
                        diameter_mm = pump_cfg.get("syringe_diameter_mm")
                        if diameter_mm is None:
                            raise ValueError(
                                f"Missing syringe_diameter_mm for pump '{ingredient}'"
                            )
                        volume_unit = pump_cfg.get("volume_unit", "ML")
                        if volume_unit not in ["ML", "UL"]:
                            raise ValueError(
                                f"Invalid volume_unit '{volume_unit}' for pump '{ingredient}'"
                            )
                        burst_configs.append(PumpBurstConfig(
                            address=pump.address,
                            rate_ul_min=dispensing_rate,
                            volume_ul=volume_ul / 2 if pump_cfg.get("dual_syringe", False) else volume_ul,
                            diameter_mm=diameter_mm,
                            volume_unit=volume_unit,
                            direction="INF"
                        ))

                # Check if we have any pumps to run
                if not burst_configs:
                    ui_log("⚠️ All pump volumes are ~0, skipping dispensing", "warning")
                    logger.info("Skipping burst mode: all volumes are ~0")
                    result["success"] = True
                    return result

                # Use separated commands: only send volume + run (DIA/RAT/DIR already set)
                any_pump = next(iter(pumps.values()))
                builder = SeparatedBurstCommandBuilder

                ui_log(f"  💧 Setting volumes for {len(burst_configs)} pumps...")
                vol_cmd = builder.build_volume_value_command(burst_configs)
                any_pump._send_burst_command(vol_cmd)
                time.sleep(0.2)

                ui_log(f"  🔍 Verifying volumes...")
                verify_cmd = builder.build_verification_command(burst_configs, "VOL")
                any_pump._send_burst_command(verify_cmd)
                time.sleep(0.2)

                ui_log(f"  🚀 Starting all pumps simultaneously...")
                run_cmd = builder.build_run_command(burst_configs)
                any_pump._send_burst_command(run_cmd)

                # Calculate max wait time (only for pumps actually dispensing)
                max_time = max((config.volume_ul / dispensing_rate) * 60 * 1.1 for config in burst_configs)
                ui_log(f"⏳ Dispensing in progress... ({max_time:.1f}s)")
                time.sleep(max_time)

                # Stop all pumps (use individual commands for safety)
                for ingredient, pump in pumps.items():
                    pump.stop()
                    ui_log(f"  ✅ {ingredient} complete", "success")

            else:
                # Fall back to original individual command mode
                if use_burst_mode and not burst_compatible:
                    ui_log("⚠️ Burst mode requires pump addresses 0-9. Using individual mode.", "warning")

                ui_log("⚡ Executing simultaneous dispensing...")

                # Start all pumps (must be done sequentially due to shared serial port)
                for ingredient, volume_ul in stock_volumes.items():
                    if ingredient in pumps:
                        pump = pumps[ingredient]
                        pump_cfg = pump_config_by_ingredient.get(ingredient, {})
                        volume_unit = pump_cfg.get("volume_unit", "ML")
                        if volume_unit not in ["ML", "UL"]:
                            raise ValueError(
                                f"Invalid volume_unit '{volume_unit}' for pump '{ingredient}'"
                            )
                        # Dual syringe: halve commanded volume
                        is_dual = pump_cfg.get("dual_syringe", False)
                        commanded_volume = volume_ul / 2 if is_dual else volume_ul
                        ui_log(f"  Starting {ingredient}: {volume_ul:.1f} µL...")
                        pump.dispense_volume(
                            commanded_volume,
                            dispensing_rate,
                            wait=False,
                            volume_unit=volume_unit,
                        )

                # Calculate max time (use commanded volumes for time estimate)
                max_time = 0
                for ingredient, vol in stock_volumes.items():
                    if vol > 0.001:
                        pump_cfg = pump_config_by_ingredient.get(ingredient, {})
                        cmd_vol = vol / 2 if pump_cfg.get("dual_syringe", False) else vol
                        t = (cmd_vol / dispensing_rate) * 60 * 1.1
                        max_time = max(max_time, t)

                ui_log(f"⏳ Dispensing in progress... ({max_time:.1f}s)")

                # Wait for dispensing to complete (no UI progress bar)
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
                    pump_cfg = pump_config_by_ingredient.get(ingredient, {})
                    volume_unit = pump_cfg.get("volume_unit", "ML")
                    if volume_unit not in ["ML", "UL"]:
                        raise ValueError(
                            f"Invalid volume_unit '{volume_unit}' for pump '{ingredient}'"
                        )
                    # Dual syringe: halve commanded volume
                    is_dual = pump_cfg.get("dual_syringe", False)
                    commanded_volume = volume_ul / 2 if is_dual else volume_ul
                    ui_log(f"  Dispensing {ingredient}: {volume_ul:.1f} µL...")
                    pump.dispense_volume(
                        commanded_volume,
                        dispensing_rate,
                        wait=True,
                        volume_unit=volume_unit,
                    )
                    ui_log(f"  ✅ {ingredient} complete", "success")

        # 5. Success
        result["success"] = True
        result["duration"] = time.time() - start_time

        # 6. Update volume tracking
        try:
            from robotaste.core.pump_volume_manager import update_volume_after_dispense
            from robotaste.data.database import DB_PATH

            update_volume_after_dispense(
                db_path=DB_PATH,
                session_id=session_id,
                actual_volumes=stock_volumes,  # Dict[str, float] in µL
                cycle_number=cycle_number
            )
        except Exception as e:
            logger.warning(f"Volume tracking update failed: {e}")

        # 7. Update global (cross-session) volume tracking
        try:
            from robotaste.core.pump_volume_manager import update_global_volume_after_dispense
            from robotaste.data.database import DB_PATH, get_database_connection

            with get_database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT protocol_id FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()

            if row and row[0]:
                proto_id = row[0]
                for pump_cfg in pump_configs:
                    ing_name = pump_cfg.get("ingredient")
                    addr = pump_cfg.get("address")
                    if ing_name and addr is not None and ing_name in stock_volumes:
                        update_global_volume_after_dispense(
                            db_path=DB_PATH,
                            protocol_id=proto_id,
                            pump_address=addr,
                            volume_dispensed_ul=stock_volumes[ing_name],
                            session_id=session_id,
                        )
        except Exception as e:
            logger.warning(f"Global volume tracking update failed: {e}")

        ui_log(f"🎉 All pumps completed successfully in {result['duration']:.1f}s", "success")

        return result

    except Exception as e:
        result["error"] = str(e)
        ui_log(f"❌ Pump operation failed: {e}", "error")
        logger.exception("Pump execution error")
        return result

    # NOTE: Pumps are NOT disconnected here - they are kept alive in the
    # session cache for reuse in subsequent cycles. They will be cleaned up
    # when the session completes (see robotaste/views/subject.py)
