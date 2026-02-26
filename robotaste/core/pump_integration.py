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
