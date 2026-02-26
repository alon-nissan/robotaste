"""
Pump Endpoints — Monitor and manage pump/syringe status and operations.

=== WHAT THIS FILE DOES ===
Provides endpoints for:
1. Check pump operation status (subject preparing page polls this)
2. Cross-session global volume tracking
3. Multi-step refill protocol (withdraw → swap → purge → enter volume)

These wrap the existing pump_volume_manager.py and pump_db.py functions.

=== NOTE ===
These endpoints only work when pump_config.enabled is True in the protocol.
If pumps are not configured, they return empty/default data gracefully.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

# ─── CREATE ROUTER ──────────────────────────────────────────────────────────
router = APIRouter()


class RefillWithdrawRequest(BaseModel):
    """Start the refill withdraw step."""
    protocol_id: str
    pump_address: int
    ingredient: str


class RefillPurgeRequest(BaseModel):
    """Start the refill purge step (after syringe swap)."""
    protocol_id: str
    pump_address: int
    ingredient: str


class RefillCompleteRequest(BaseModel):
    """Complete the refill with the new syringe volume."""
    protocol_id: str
    pump_address: int
    ingredient: str
    new_volume_ml: float


# ─── GET PUMP OPERATION STATUS ─────────────────────────────────────────────
@router.get("/operation/{session_id}")
def get_pump_operation(session_id: str):
    """
    Get current pump operation status for a session.

    The RobotPreparingPage polls this to know when dispensing is done.
    The pump_control_service.py daemon picks up pending operations,
    executes them, and marks them completed/failed in the DB.

    Returns:
        status: "pending" | "in_progress" | "completed" | "failed" | "none"
        progress: 0 (pending), 50 (in_progress), 100 (completed/failed)
        recipe: Dict of ingredient volumes (µL)
        error: Error message if failed
        started_at / completed_at: Timestamps
    """
    try:
        from robotaste.utils.pump_db import get_db_connection
        from robotaste.data.database import DB_PATH

        conn = get_db_connection(DB_PATH)
        cursor = conn.cursor()

        # Get most recent operation for this session (any status)
        cursor.execute(
            """
            SELECT *
            FROM pump_operations
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.debug(f"🔧 No pump operations found for session {session_id}")
            return {"status": "none", "progress": 0}

        op = dict(row)
        status = op.get("status", "pending")

        progress_map = {"pending": 0, "in_progress": 50, "completed": 100, "failed": 100}
        progress = progress_map.get(status, 0)

        # Parse recipe JSON
        recipe = {}
        recipe_json = op.get("recipe_json")
        if recipe_json:
            try:
                recipe = json.loads(recipe_json)
            except (json.JSONDecodeError, TypeError):
                pass

        result = {
            "status": status,
            "progress": progress,
            "cycle_number": op.get("cycle_number"),
            "recipe": recipe,
            "started_at": op.get("started_at"),
            "completed_at": op.get("completed_at"),
        }

        if status == "failed":
            result["error"] = op.get("error_message", "Unknown error")
            logger.error(f"❌ Pump operation failed for session {session_id}: {result['error']}")

        if status == "completed":
            logger.info(f"✅ Pump operation completed for session {session_id}, cycle {op.get('cycle_number')}")

        return result

    except ImportError:
        logger.warning(f"🔧 pump_db not available for session {session_id}")
        return {"status": "none", "progress": 0}
    except Exception as e:
        logger.error(f"❌ Error checking pump operation for session {session_id}: {e}")
        return {"status": "none", "progress": 0}


# ─── GLOBAL (CROSS-SESSION) VOLUME STATUS ──────────────────────────────────
@router.get("/global-status/{protocol_id}")
def get_global_pump_status(protocol_id: str):
    """
    Get cross-session volume status for all pumps in a protocol.

    Used by ModeratorSetupPage to show pump volumes before starting a session.
    Volumes persist across sessions and are decremented after each dispense.
    """
    try:
        from robotaste.core.pump_volume_manager import (
            get_global_volume_status,
            get_or_create_global_state,
        )
        from robotaste.data.protocol_repo import get_protocol_by_id
        from robotaste.data.database import DB_PATH

        protocol = get_protocol_by_id(protocol_id)
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")

        pump_config = protocol.get("pump_config", {})
        if not pump_config.get("enabled", False):
            return {"pump_enabled": False, "ingredients": {}}

        # Ensure global state rows exist
        status = get_or_create_global_state(DB_PATH, protocol_id, protocol)

        return {
            "pump_enabled": True,
            "protocol_id": protocol_id,
            "ingredients": status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting global pump status: {e}")
        return {"pump_enabled": False, "ingredients": {}}


# ─── REFILL WORKFLOW: STEP 1 — WITHDRAW ────────────────────────────────────
@router.post("/refill/withdraw")
def start_refill_withdraw(request: RefillWithdrawRequest):
    """
    Start the refill withdraw step.

    Creates a withdraw operation in the DB queue. The pump_control_service
    will pick it up and execute it (pull liquid back from tubes).
    """
    try:
        from robotaste.data.protocol_repo import get_protocol_by_id
        from robotaste.utils.pump_db import create_refill_operation

        protocol = get_protocol_by_id(request.protocol_id)
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")

        pump_config = protocol.get("pump_config", {})
        pump_cfg = _find_pump_config(pump_config, request.pump_address)

        if not pump_cfg:
            raise HTTPException(
                status_code=404,
                detail=f"No pump config for address {request.pump_address}"
            )

        tube_volume_ul = pump_cfg.get("tube_volume_ul", 500.0)

        operation_id = create_refill_operation(
            protocol_id=request.protocol_id,
            pump_address=request.pump_address,
            ingredient_name=request.ingredient,
            operation_type="withdraw",
            volume_ul=tube_volume_ul,
            direction="WDR",
        )

        logger.info(
            f"🔧 Refill withdraw created: op={operation_id}, "
            f"pump={request.pump_address} ({request.ingredient}), "
            f"volume={tube_volume_ul}µL"
        )

        return {
            "operation_id": operation_id,
            "operation_type": "withdraw",
            "volume_ul": tube_volume_ul,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create withdraw operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── REFILL WORKFLOW: POLL STATUS ──────────────────────────────────────────
@router.get("/refill/status/{operation_id}")
def get_refill_status(operation_id: int):
    """
    Poll the status of a refill operation (withdraw or purge).

    Frontend polls this during withdraw and purge steps.
    """
    try:
        from robotaste.utils.pump_db import get_refill_operation_by_id

        operation = get_refill_operation_by_id(operation_id)
        if not operation:
            raise HTTPException(status_code=404, detail="Refill operation not found")

        return {
            "operation_id": operation["id"],
            "status": operation["status"],
            "operation_type": operation["operation_type"],
            "ingredient": operation["ingredient_name"],
            "volume_ul": operation["volume_ul"],
            "started_at": operation.get("started_at"),
            "completed_at": operation.get("completed_at"),
            "error_message": operation.get("error_message"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error checking refill status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── REFILL WORKFLOW: STEP 2 — PURGE ──────────────────────────────────────
@router.post("/refill/purge")
def start_refill_purge(request: RefillPurgeRequest):
    """
    Start the refill purge step (after syringe has been swapped).

    Creates a purge operation in the DB queue. The pump_control_service
    will pick it up and execute it (push liquid through tubes to expel air).
    """
    try:
        from robotaste.data.protocol_repo import get_protocol_by_id
        from robotaste.utils.pump_db import create_refill_operation

        protocol = get_protocol_by_id(request.protocol_id)
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")

        pump_config = protocol.get("pump_config", {})
        pump_cfg = _find_pump_config(pump_config, request.pump_address)

        if not pump_cfg:
            raise HTTPException(
                status_code=404,
                detail=f"No pump config for address {request.pump_address}"
            )

        purge_volume_ul = pump_cfg.get("purge_volume_ul", 700.0)

        operation_id = create_refill_operation(
            protocol_id=request.protocol_id,
            pump_address=request.pump_address,
            ingredient_name=request.ingredient,
            operation_type="purge",
            volume_ul=purge_volume_ul,
            direction="INF",
        )

        logger.info(
            f"🔧 Refill purge created: op={operation_id}, "
            f"pump={request.pump_address} ({request.ingredient}), "
            f"volume={purge_volume_ul}µL"
        )

        return {
            "operation_id": operation_id,
            "operation_type": "purge",
            "volume_ul": purge_volume_ul,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to create purge operation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── REFILL WORKFLOW: STEP 3 — COMPLETE ───────────────────────────────────
@router.post("/refill/complete")
def complete_refill(request: RefillCompleteRequest):
    """
    Complete the refill: update global volume tracking.

    Moderator enters the new syringe volume in mL. System converts to µL
    and subtracts the purge volume to get the actual available volume.
    """
    try:
        from robotaste.core.pump_volume_manager import update_global_volume_after_refill
        from robotaste.data.protocol_repo import get_protocol_by_id
        from robotaste.data.database import DB_PATH

        protocol = get_protocol_by_id(request.protocol_id)
        if not protocol:
            raise HTTPException(status_code=404, detail="Protocol not found")

        pump_config = protocol.get("pump_config", {})
        pump_cfg = _find_pump_config(pump_config, request.pump_address)

        if not pump_cfg:
            raise HTTPException(
                status_code=404,
                detail=f"No pump config for address {request.pump_address}"
            )

        purge_volume_ul = pump_cfg.get("purge_volume_ul", 700.0)
        new_volume_ul = request.new_volume_ml * 1000.0

        final_volume_ul = update_global_volume_after_refill(
            db_path=DB_PATH,
            protocol_id=request.protocol_id,
            pump_address=request.pump_address,
            new_volume_ul=new_volume_ul,
        )

        logger.info(
            f"🔧 Refill complete: {request.ingredient}, "
            f"entered={request.new_volume_ml}mL, final={final_volume_ul}µL"
        )

        return {
            "message": f"Refill complete for {request.ingredient}",
            "ingredient": request.ingredient,
            "loaded_volume_ml": request.new_volume_ml,
            "purge_volume_ul": purge_volume_ul,
            "final_volume_ul": final_volume_ul,
            "final_volume_ml": final_volume_ul / 1000.0,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to complete refill: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── HELPERS ───────────────────────────────────────────────────────────────
def _find_pump_config(pump_config: dict, pump_address: int) -> Optional[dict]:
    """Find pump configuration by address."""
    for cfg in pump_config.get("pumps", []):
        if cfg.get("address") == pump_address:
            return cfg
    return None
