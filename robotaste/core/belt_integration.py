"""
Belt Integration for RoboTaste

Handles the integration between the experiment workflow and belt control system.
Creates belt operations when entering ROBOT_PREPARING phase.

Operations sequence per cycle:
1. position_spout - Move cup to spout position
2. (pump dispenses sample)
3. mix - Perform oscillation mixing
4. position_display - Move cup to display area

Author: RoboTaste Team
Version: 1.0
"""

import logging
from typing import Dict, Optional, Any, List

from robotaste.core.belt_manager import (
    get_or_create_belt,
    is_belt_enabled,
    get_belt_config,
)
from robotaste.hardware.belt_controller import (
    ConveyorBelt,
    BeltConnectionError,
    BeltCommandError,
    BeltTimeoutError,
    BeltPosition,
)
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection
from robotaste.utils.belt_db import (
    create_belt_operation,
    get_pending_belt_operations_for_cycle,
    get_current_belt_operation_for_session,
    mark_belt_operation_in_progress,
    mark_belt_operation_completed,
    mark_belt_operation_failed,
    mark_belt_operation_skipped,
    are_all_belt_operations_complete_for_cycle,
)

logger = logging.getLogger(__name__)


def should_create_belt_operations(session_id: str, protocol: Dict[str, Any]) -> bool:
    """
    Check if belt operations should be created for the current cycle.

    Args:
        session_id: Session ID
        protocol: Protocol configuration

    Returns:
        True if belt operations should be created
    """
    if not is_belt_enabled(protocol):
        logger.debug("Belt control is disabled in protocol")
        return False

    # Check if there's already pending operations for this session
    existing_operation = get_current_belt_operation_for_session(session_id)
    if existing_operation:
        logger.debug(f"Belt operation already exists for session {session_id}: {existing_operation['id']}")
        return False

    return True


def create_belt_operations_for_cycle(
    session_id: str,
    cycle_number: int,
    db_path: Optional[str] = None
) -> List[int]:
    """
    Create belt operations for a cycle.

    Creates three operations in sequence:
    1. position_spout - Move cup to spout
    2. mix - Oscillate for mixing
    3. position_display - Move to display area

    Args:
        session_id: Session ID
        cycle_number: Current cycle number
        db_path: Database path (optional)

    Returns:
        List of operation IDs created
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
            return []

        protocol_id = row[0]
        protocol = get_protocol_by_id(protocol_id)

        if not protocol:
            logger.error(f"Could not load protocol {protocol_id}")
            return []

        # Check if belt should be used
        if not should_create_belt_operations(session_id, protocol):
            return []

        belt_config = get_belt_config(protocol)
        if not belt_config:
            return []

        logger.info(f"Creating belt operations for session {session_id}, cycle {cycle_number}")

        operation_ids = []

        # 1. Create position_spout operation
        op_id = create_belt_operation(
            session_id=session_id,
            cycle_number=cycle_number,
            operation_type="position_spout",
            target_position="spout",
            db_path=db_path
        )
        operation_ids.append(op_id)
        logger.debug(f"Created belt operation {op_id}: position_spout")

        # 2. Create mix operation (if enabled)
        mixing_config = belt_config.get("mixing", {})
        if mixing_config.get("enabled", True):
            oscillations = mixing_config.get("oscillations", 5)
            op_id = create_belt_operation(
                session_id=session_id,
                cycle_number=cycle_number,
                operation_type="mix",
                mix_count=oscillations,
                db_path=db_path
            )
            operation_ids.append(op_id)
            logger.debug(f"Created belt operation {op_id}: mix ({oscillations} oscillations)")

        # 3. Create position_display operation
        op_id = create_belt_operation(
            session_id=session_id,
            cycle_number=cycle_number,
            operation_type="position_display",
            target_position="display",
            db_path=db_path
        )
        operation_ids.append(op_id)
        logger.debug(f"Created belt operation {op_id}: position_display")

        logger.info(f"Created {len(operation_ids)} belt operations for cycle {cycle_number}")

        return operation_ids

    except Exception as e:
        logger.error(f"Error creating belt operations for cycle {cycle_number}: {e}", exc_info=True)
        return []


def check_belt_operation_status(
    session_id: str,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Check the status of the current belt operation for a session.

    Args:
        session_id: Session ID
        db_path: Database path (optional)

    Returns:
        Operation status dictionary or None
    """
    operation = get_current_belt_operation_for_session(session_id, db_path)

    if not operation:
        return None

    return {
        "operation_id": operation["id"],
        "operation_type": operation["operation_type"],
        "status": operation["status"],
        "cycle_number": operation["cycle_number"],
        "target_position": operation.get("target_position"),
        "mix_count": operation.get("mix_count"),
        "created_at": operation["created_at"],
        "started_at": operation.get("started_at"),
        "completed_at": operation.get("completed_at"),
        "error_message": operation.get("error_message"),
    }


def execute_belt_operation(
    operation: Dict[str, Any],
    belt: ConveyorBelt,
    db_path: Optional[str] = None
) -> bool:
    """
    Execute a single belt operation.

    Args:
        operation: Operation dictionary from database
        belt: ConveyorBelt instance
        db_path: Database path (optional)

    Returns:
        True if operation succeeded, False otherwise
    """
    operation_id = operation["id"]
    operation_type = operation["operation_type"]

    logger.info(f"Executing belt operation {operation_id}: {operation_type}")

    # Mark as in progress
    mark_belt_operation_in_progress(operation_id, db_path)

    try:
        if operation_type == "position_spout":
            belt.move_to_spout(wait=True)
            
        elif operation_type == "position_display":
            belt.move_to_display(wait=True)
            
        elif operation_type == "mix":
            mix_count = operation.get("mix_count", 5)
            belt.mix(oscillations=mix_count, wait=True)
            
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

        # Mark as completed
        mark_belt_operation_completed(operation_id, db_path)
        logger.info(f"Belt operation {operation_id} completed successfully")
        return True

    except (BeltCommandError, BeltTimeoutError) as e:
        error_msg = str(e)
        logger.error(f"Belt operation {operation_id} failed: {error_msg}")

        # For mixing, skip and continue; for positioning, mark as failed
        if operation_type == "mix":
            mark_belt_operation_skipped(operation_id, f"Mixing skipped: {error_msg}", db_path)
            logger.warning(f"Mixing skipped for operation {operation_id}, continuing")
            return True  # Continue with next operation
        else:
            mark_belt_operation_failed(operation_id, error_msg, db_path)
            return False

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Belt operation {operation_id} error: {error_msg}", exc_info=True)
        mark_belt_operation_failed(operation_id, error_msg, db_path)
        return False


def position_cup_at_spout(
    session_id: str,
    belt_config: Dict[str, Any]
) -> bool:
    """
    Position cup at spout for dispensing (synchronous).

    Args:
        session_id: Session ID
        belt_config: Belt configuration

    Returns:
        True if successful
    """
    try:
        belt = get_or_create_belt(session_id, belt_config)
        belt.move_to_spout(wait=True)
        logger.info(f"Cup positioned at spout for session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to position cup at spout: {e}")
        raise


def position_cup_at_display(
    session_id: str,
    belt_config: Dict[str, Any]
) -> bool:
    """
    Position cup at display area for pickup (synchronous).

    Args:
        session_id: Session ID
        belt_config: Belt configuration

    Returns:
        True if successful
    """
    try:
        belt = get_or_create_belt(session_id, belt_config)
        belt.move_to_display(wait=True)
        logger.info(f"Cup positioned at display for session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to position cup at display: {e}")
        raise


def perform_mixing(
    session_id: str,
    belt_config: Dict[str, Any],
    oscillations: Optional[int] = None
) -> bool:
    """
    Perform mixing oscillation (synchronous).

    Args:
        session_id: Session ID
        belt_config: Belt configuration
        oscillations: Number of oscillations (optional, uses config default)

    Returns:
        True if successful
    """
    try:
        belt = get_or_create_belt(session_id, belt_config)
        
        mixing_config = belt_config.get("mixing", {})
        if oscillations is None:
            oscillations = mixing_config.get("oscillations", 5)
        
        belt.mix(oscillations=oscillations, wait=True)
        logger.info(f"Mixing complete for session {session_id}: {oscillations} oscillations")
        return True
    except Exception as e:
        logger.error(f"Mixing failed: {e}")
        raise


def execute_full_belt_cycle(
    session_id: str,
    cycle_number: int,
    belt_config: Dict[str, Any],
    skip_position_spout: bool = False
) -> Dict[str, Any]:
    """
    Execute complete belt cycle synchronously.

    Sequence: position_spout → (wait for dispense) → mix → position_display

    Args:
        session_id: Session ID
        cycle_number: Current cycle
        belt_config: Belt configuration
        skip_position_spout: If True, skip initial positioning (cup already at spout)

    Returns:
        Dict with:
            - success: bool
            - error: Optional error message
            - skipped_mixing: bool if mixing was skipped
    """
    result = {
        "success": False,
        "error": None,
        "skipped_mixing": False
    }

    try:
        belt = get_or_create_belt(session_id, belt_config)

        # 1. Position at spout
        if not skip_position_spout:
            logger.info(f"[Belt Cycle {cycle_number}] Positioning cup at spout...")
            belt.move_to_spout(wait=True)
            logger.info(f"[Belt Cycle {cycle_number}] Cup at spout")

        # 2. NOTE: Pump dispense happens here (called separately by orchestrator)
        # This function is called in parts or the orchestrator handles the full flow

        # 3. Mix
        mixing_config = belt_config.get("mixing", {})
        if mixing_config.get("enabled", True):
            oscillations = mixing_config.get("oscillations", 5)
            logger.info(f"[Belt Cycle {cycle_number}] Mixing ({oscillations} oscillations)...")
            try:
                belt.mix(oscillations=oscillations, wait=True)
                logger.info(f"[Belt Cycle {cycle_number}] Mixing complete")
            except (BeltCommandError, BeltTimeoutError) as e:
                logger.warning(f"[Belt Cycle {cycle_number}] Mixing failed, skipping: {e}")
                result["skipped_mixing"] = True
                # Continue to delivery despite mixing failure

        # 4. Position at display
        logger.info(f"[Belt Cycle {cycle_number}] Moving cup to display...")
        belt.move_to_display(wait=True)
        logger.info(f"[Belt Cycle {cycle_number}] Cup at display - ready for pickup")

        result["success"] = True
        return result

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[Belt Cycle {cycle_number}] Belt cycle failed: {e}", exc_info=True)
        return result


def are_belt_operations_complete(
    session_id: str,
    cycle_number: int,
    db_path: Optional[str] = None
) -> bool:
    """
    Check if all belt operations for a cycle are complete.

    Args:
        session_id: Session ID
        cycle_number: Cycle number
        db_path: Database path (optional)

    Returns:
        True if all complete
    """
    return are_all_belt_operations_complete_for_cycle(session_id, cycle_number, db_path)
