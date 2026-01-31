"""
Robot Orchestrator for RoboTaste

Coordinates pump and belt operations during the ROBOT_PREPARING phase.
Ensures proper sequencing: position cup → dispense → mix → deliver.

This module handles the full automation workflow when both pumps and
conveyor belt are enabled in the protocol.

Operation Sequence:
1. Belt positions cup at spout
2. Pumps dispense sample into cup
3. Belt performs mixing oscillation
4. Belt delivers cup to display area
5. Phase transitions to QUESTIONNAIRE

Error Handling:
- Belt fails to position at spout: Abort entire operation
- Pump fails during dispense: Abort, skip mixing/delivery
- Belt fails during mixing: Log warning, skip mixing, deliver anyway
- Belt fails to deliver: Retry once, then abort

Author: RoboTaste Team
Version: 1.0
"""

import logging
import time
from typing import Dict, Optional, Any

from robotaste.core.belt_manager import (
    get_or_create_belt,
    is_belt_enabled,
    get_belt_config,
    cleanup_belt,
)
from robotaste.core.belt_integration import (
    position_cup_at_spout,
    position_cup_at_display,
    perform_mixing,
)
from robotaste.core.pump_integration import execute_pumps_synchronously
from robotaste.hardware.belt_controller import (
    BeltConnectionError,
    BeltCommandError,
    BeltTimeoutError,
)
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.data.database import get_database_connection

logger = logging.getLogger(__name__)


class RobotOrchestrationError(Exception):
    """Raised when orchestration fails."""
    pass


def is_robot_mode_enabled(protocol: Dict[str, Any]) -> bool:
    """
    Check if full robot mode is enabled (both pumps and belt).

    Args:
        protocol: Protocol configuration

    Returns:
        True if both pump and belt are enabled
    """
    pump_config = protocol.get("pump_config", {})
    belt_config = protocol.get("belt_config", {})
    
    pump_enabled = pump_config.get("enabled", False)
    belt_enabled = belt_config.get("enabled", False)
    
    return pump_enabled and belt_enabled


def is_pump_only_mode(protocol: Dict[str, Any]) -> bool:
    """
    Check if only pumps are enabled (no belt).

    Args:
        protocol: Protocol configuration

    Returns:
        True if only pumps are enabled
    """
    pump_config = protocol.get("pump_config", {})
    belt_config = protocol.get("belt_config", {})
    
    pump_enabled = pump_config.get("enabled", False)
    belt_enabled = belt_config.get("enabled", False)
    
    return pump_enabled and not belt_enabled


def execute_robot_cycle(
    session_id: str,
    cycle_number: int,
    protocol: Optional[Dict[str, Any]] = None,
    streamlit_container=None
) -> Dict[str, Any]:
    """
    Execute a complete robot preparation cycle.

    Coordinates belt and pump operations in the correct sequence.
    This is the main entry point for ROBOT_PREPARING phase automation.

    Args:
        session_id: Session identifier
        cycle_number: Current cycle number
        protocol: Protocol config (optional, will load from DB if not provided)
        streamlit_container: Streamlit container for UI updates (optional)

    Returns:
        Dict with:
            - success: bool
            - pump_result: Dict with pump operation details
            - belt_used: bool
            - mixing_skipped: bool
            - error: Optional error message
            - duration: Total time in seconds
    """
    start_time = time.time()
    
    result = {
        "success": False,
        "pump_result": None,
        "belt_used": False,
        "mixing_skipped": False,
        "error": None,
        "duration": 0
    }

    # Helper for logging
    def log_step(message: str, level: str = "info"):
        if level == "info":
            logger.info(f"[Cycle {cycle_number}] {message}")
        elif level == "warning":
            logger.warning(f"[Cycle {cycle_number}] {message}")
        elif level == "error":
            logger.error(f"[Cycle {cycle_number}] {message}")

    try:
        # Load protocol if not provided
        if protocol is None:
            with get_database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT protocol_id FROM sessions WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()

            if not row or not row[0]:
                raise RobotOrchestrationError(f"No protocol found for session {session_id}")

            protocol = get_protocol_by_id(row[0])
            if not protocol:
                raise RobotOrchestrationError(f"Could not load protocol {row[0]}")

        pump_config = protocol.get("pump_config", {})
        belt_config = protocol.get("belt_config", {})
        
        pump_enabled = pump_config.get("enabled", False)
        belt_enabled = belt_config.get("enabled", False)

        if not pump_enabled:
            raise RobotOrchestrationError("Pump control is not enabled in protocol")

        # ========================================
        # STEP 1: Position cup at spout (if belt enabled)
        # ========================================
        if belt_enabled:
            result["belt_used"] = True
            log_step("🚂 Positioning cup at spout...")
            
            try:
                position_cup_at_spout(session_id, belt_config)
                log_step("✓ Cup positioned at spout")
            except (BeltConnectionError, BeltCommandError, BeltTimeoutError) as e:
                error_msg = f"Belt failed to position cup at spout: {e}"
                log_step(error_msg, "error")
                result["error"] = error_msg
                raise RobotOrchestrationError(error_msg)

        # ========================================
        # STEP 2: Dispense sample (pumps)
        # ========================================
        log_step("💧 Dispensing sample...")
        
        pump_result = execute_pumps_synchronously(
            session_id=session_id,
            cycle_number=cycle_number,
            streamlit_container=streamlit_container
        )
        
        result["pump_result"] = pump_result
        
        if not pump_result.get("success", False):
            error_msg = pump_result.get("error", "Pump dispense failed")
            log_step(f"Pump error: {error_msg}", "error")
            result["error"] = error_msg
            
            # If belt was used but pump failed, try to deliver cup anyway
            if belt_enabled:
                log_step("Attempting to deliver cup despite pump failure...", "warning")
                try:
                    position_cup_at_display(session_id, belt_config)
                    log_step("Cup delivered to display (empty/partial)")
                except Exception as e:
                    log_step(f"Failed to deliver cup: {e}", "error")
            
            raise RobotOrchestrationError(error_msg)
        
        log_step(f"✓ Dispensing complete: {pump_result.get('recipe', {})}")

        # ========================================
        # STEP 3: Mix sample (if belt enabled)
        # ========================================
        if belt_enabled:
            mixing_config = belt_config.get("mixing", {})
            
            if mixing_config.get("enabled", True):
                oscillations = mixing_config.get("oscillations", 5)
                log_step(f"🔄 Mixing sample ({oscillations} oscillations)...")
                
                try:
                    perform_mixing(session_id, belt_config, oscillations)
                    log_step("✓ Mixing complete")
                except (BeltCommandError, BeltTimeoutError) as e:
                    log_step(f"Mixing failed, skipping: {e}", "warning")
                    result["mixing_skipped"] = True
                    # Continue to delivery despite mixing failure
            else:
                log_step("Mixing disabled in protocol")

        # ========================================
        # STEP 4: Deliver cup to display (if belt enabled)
        # ========================================
        if belt_enabled:
            log_step("📦 Delivering cup to display...")
            
            try:
                position_cup_at_display(session_id, belt_config)
                log_step("✓ Cup delivered to display - ready for pickup")
            except (BeltConnectionError, BeltCommandError, BeltTimeoutError) as e:
                # Retry once
                log_step(f"Delivery failed, retrying: {e}", "warning")
                time.sleep(1.0)
                
                try:
                    position_cup_at_display(session_id, belt_config)
                    log_step("✓ Cup delivered on retry")
                except Exception as retry_e:
                    error_msg = f"Belt failed to deliver cup after retry: {retry_e}"
                    log_step(error_msg, "error")
                    result["error"] = error_msg
                    raise RobotOrchestrationError(error_msg)

        # ========================================
        # SUCCESS
        # ========================================
        result["success"] = True
        result["duration"] = time.time() - start_time
        
        log_step(f"🎉 Robot cycle complete in {result['duration']:.1f}s")
        
        return result

    except RobotOrchestrationError:
        # Re-raise orchestration errors (already logged)
        result["duration"] = time.time() - start_time
        raise

    except Exception as e:
        result["error"] = str(e)
        result["duration"] = time.time() - start_time
        log_step(f"Unexpected error: {e}", "error")
        raise RobotOrchestrationError(str(e))


def execute_pump_only_cycle(
    session_id: str,
    cycle_number: int,
    streamlit_container=None
) -> Dict[str, Any]:
    """
    Execute pump-only cycle (legacy behavior, no belt).

    This is a wrapper around execute_pumps_synchronously for cases
    where belt is not enabled.

    Args:
        session_id: Session identifier
        cycle_number: Current cycle number
        streamlit_container: Streamlit container for UI updates

    Returns:
        Dict with pump operation results
    """
    logger.info(f"[Cycle {cycle_number}] Executing pump-only cycle (no belt)")
    
    return execute_pumps_synchronously(
        session_id=session_id,
        cycle_number=cycle_number,
        streamlit_container=streamlit_container
    )


def get_robot_status(session_id: str, protocol: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get current status of robot systems for a session.

    Args:
        session_id: Session identifier
        protocol: Protocol configuration

    Returns:
        Dict with status of each system
    """
    from robotaste.core.pump_manager import get_session_pump_info
    from robotaste.core.belt_manager import get_session_belt_info
    
    pump_config = protocol.get("pump_config", {})
    belt_config = protocol.get("belt_config", {})
    
    status = {
        "pump_enabled": pump_config.get("enabled", False),
        "belt_enabled": belt_config.get("enabled", False),
        "pump_info": None,
        "belt_info": None,
        "robot_mode": False
    }
    
    if status["pump_enabled"]:
        status["pump_info"] = get_session_pump_info(session_id)
    
    if status["belt_enabled"]:
        status["belt_info"] = get_session_belt_info(session_id)
    
    status["robot_mode"] = status["pump_enabled"] and status["belt_enabled"]
    
    return status


def cleanup_robot_systems(session_id: str) -> None:
    """
    Cleanup all robot systems for a session.

    Should be called when session completes.

    Args:
        session_id: Session identifier
    """
    from robotaste.core.pump_manager import cleanup_pumps
    from robotaste.core.belt_manager import cleanup_belt
    
    logger.info(f"Cleaning up robot systems for session {session_id}")
    
    try:
        cleanup_pumps(session_id)
    except Exception as e:
        logger.warning(f"Error cleaning up pumps: {e}")
    
    try:
        cleanup_belt(session_id)
    except Exception as e:
        logger.warning(f"Error cleaning up belt: {e}")
    
    logger.info(f"Robot systems cleanup complete for session {session_id}")
