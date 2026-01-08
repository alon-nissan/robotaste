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
            desired_concentrations_mM=concentrations,
            ingredient_configs=ingredients,
            total_volume_ml=total_volume_ml
        )

        stock_volumes = volumes_result.get("stock_volumes", {})

        if not stock_volumes:
            logger.warning(f"No stock volumes to dispense for cycle {cycle_number}")
            # Still create operation but with empty recipe
            # This might happen for a zero-concentration sample

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
