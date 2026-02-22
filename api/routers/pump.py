"""
Pump Endpoints — Monitor and manage pump/syringe status and operations.

=== WHAT THIS FILE DOES ===
Provides endpoints for:
1. Check pump volume levels per ingredient (moderator monitoring)
2. Record a refill (when moderator physically refills a syringe)
3. Check pump operation status (subject preparing page polls this)

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


class RefillRequest(BaseModel):
    """
    Request body for recording a pump refill.

    Example:
    {
        "session_id": "abc-123",
        "ingredient": "Sugar",
        "volume_ul": 50000
    }
    """
    session_id: str
    ingredient: str
    volume_ul: float


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
        return {"status": "none", "progress": 0, "error": str(e)}


# ─── GET PUMP STATUS ────────────────────────────────────────────────────────
@router.get("/status/{session_id}")
def get_pump_status(session_id: str):
    """
    Get current pump volume status for all ingredients in a session.

    Returns per-ingredient data:
    - current_ul: Current volume remaining (microliters)
    - max_capacity_ul: Maximum syringe capacity
    - percent_remaining: Percentage remaining (0-100)
    - alert_active: True if volume is critically low
    """
    try:
        # Import here to avoid errors if pump modules aren't available
        from robotaste.core.pump_volume_manager import get_volume_status
        from robotaste.data.database import DB_PATH

        volume_status = get_volume_status(DB_PATH, session_id)

        if not volume_status:
            logger.debug(f"🔧 Pump status for session {session_id}: not configured or no data")
            return {"pump_enabled": False, "ingredients": {}}

        logger.info(f"🔧 Pump status for session {session_id}: {len(volume_status)} ingredients tracked")
        return {
            "pump_enabled": True,
            "ingredients": volume_status,
        }

    except ImportError:
        # pump_volume_manager not available (no pump hardware)
        logger.warning(f"🔧 Pump volume manager not available for session {session_id}")
        return {"pump_enabled": False, "ingredients": {}}
    except Exception as e:
        logger.error(f"❌ Error getting pump status for session {session_id}: {e}")
        return {"pump_enabled": False, "ingredients": {}, "error": str(e)}


# ─── RECORD REFILL ─────────────────────────────────────────────────────────
@router.post("/refill")
def record_refill(request: RefillRequest):
    """
    Record that a syringe was physically refilled by the moderator.

    This updates the volume tracking in the database so the
    monitoring dashboard shows accurate levels.
    """
    try:
        from robotaste.core.pump_volume_manager import record_refill as do_refill
        from robotaste.data.database import DB_PATH

        do_refill(DB_PATH, request.session_id, request.ingredient, request.volume_ul)
        logger.info(
            f"🔧 Refill recorded: session={request.session_id}, "
            f"ingredient={request.ingredient}, volume={request.volume_ul}µL"
        )

        return {
            "message": f"Refill recorded for {request.ingredient}",
            "ingredient": request.ingredient,
            "new_volume_ul": request.volume_ul,
        }

    except ImportError:
        logger.error(f"❌ Pump volume manager not available for refill: {request.ingredient}")
        raise HTTPException(
            status_code=501,
            detail="Pump volume manager not available"
        )
    except Exception as e:
        logger.error(
            f"❌ Failed to record refill: session={request.session_id}, "
            f"ingredient={request.ingredient}, error={e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record refill: {str(e)}"
        )
