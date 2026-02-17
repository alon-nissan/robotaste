"""
Pump Endpoints — Monitor and manage pump/syringe status.

=== WHAT THIS FILE DOES ===
Provides endpoints for the moderator monitoring page to:
1. Check pump volume levels per ingredient
2. Record a refill (when moderator physically refills a syringe)

These wrap the existing pump_volume_manager.py functions.

=== NOTE ===
These endpoints only work when pump_config.enabled is True in the protocol.
If pumps are not configured, they return empty/default data gracefully.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
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
            # Pumps not configured or no data yet — return empty
            return {"pump_enabled": False, "ingredients": {}}

        return {
            "pump_enabled": True,
            "ingredients": volume_status,
        }

    except ImportError:
        # pump_volume_manager not available (no pump hardware)
        logger.warning("Pump volume manager not available")
        return {"pump_enabled": False, "ingredients": {}}
    except Exception as e:
        logger.error(f"Error getting pump status: {e}")
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

        return {
            "message": f"Refill recorded for {request.ingredient}",
            "ingredient": request.ingredient,
            "new_volume_ul": request.volume_ul,
        }

    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Pump volume manager not available"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record refill: {str(e)}"
        )
