"""
Pump Volume Tracking Manager

Manages cross-session volume tracking for syringe pumps via the pump_global_state
table. Provides global volume initialization, dispense decrement, refill updates,
and status queries.

All volumes are in microliters (µL) to match database/UI conventions.
"""

import sqlite3
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ─── CROSS-SESSION (GLOBAL) VOLUME TRACKING ─────────────────────────────────


def get_or_create_global_state(
    db_path: str,
    protocol_id: str,
    protocol: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Ensure pump_global_state rows exist for every pump in a protocol.

    Creates rows for any pumps not yet tracked. Returns current state.

    Args:
        db_path: Path to SQLite database
        protocol_id: Protocol identifier
        protocol: Full protocol dict (must contain pump_config.pumps)

    Returns:
        Dict keyed by ingredient name with volume info
    """
    pump_config = protocol.get("pump_config", {})
    pump_defs = pump_config.get("pumps", [])

    if not pump_defs:
        return {}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for pump_def in pump_defs:
            address = pump_def.get("address")
            ingredient = pump_def.get("ingredient")
            capacity_ul = pump_def.get("syringe_capacity_ul", 60000.0)

            # Dual-syringe pumps have double the capacity
            if pump_def.get("dual_syringe", False):
                capacity_ul *= 2

            if address is None or not ingredient:
                continue

            # Insert if not already present, then ensure capacity is up to date
            cursor.execute("""
                INSERT OR IGNORE INTO pump_global_state (
                    protocol_id, pump_address, ingredient_name,
                    current_volume_ul, max_capacity_ul
                ) VALUES (?, ?, ?, 0, ?)
            """, (protocol_id, address, ingredient, capacity_ul))

            # Update capacity if protocol config changed (e.g. dual_syringe added)
            cursor.execute("""
                UPDATE pump_global_state SET max_capacity_ul = ?
                WHERE protocol_id = ? AND pump_address = ? AND max_capacity_ul != ?
            """, (capacity_ul, protocol_id, address, capacity_ul))

        conn.commit()

        # Return current state
        result = _fetch_global_status(cursor, protocol_id)
        conn.close()
        return result

    except Exception as e:
        logger.error(f"Failed to get/create global state: {e}")
        return {}


def get_global_volume_status(
    db_path: str,
    protocol_id: str
) -> Dict[str, Dict[str, Any]]:
    """
    Get cross-session volume status for all pumps of a protocol.

    Args:
        db_path: Path to SQLite database
        protocol_id: Protocol identifier

    Returns:
        Dict keyed by ingredient name:
        {
            "Sugar": {
                "pump_address": 0,
                "current_ul": 39000,
                "max_capacity_ul": 60000,
                "percent_remaining": 65.0,
                "alert_active": False,
                "alert_threshold_ul": 2000,
                "total_dispensed_ul": 11000,
                "last_session_id": "abc-123",
                "last_dispensed_at": "...",
                "last_refilled_at": "..."
            }
        }
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        result = _fetch_global_status(cursor, protocol_id)
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Failed to get global volume status: {e}")
        return {}


def _fetch_global_status(
    cursor: sqlite3.Cursor,
    protocol_id: str
) -> Dict[str, Dict[str, Any]]:
    """Internal helper to fetch global state rows for a protocol."""
    cursor.execute("""
        SELECT pump_address, ingredient_name, current_volume_ul,
               max_capacity_ul, alert_threshold_ul, total_dispensed_ul,
               last_session_id, last_dispensed_at, last_refilled_at
        FROM pump_global_state
        WHERE protocol_id = ?
        ORDER BY pump_address
    """, (protocol_id,))

    status = {}
    for row in cursor.fetchall():
        address, ingredient, current, capacity, threshold, dispensed, \
            last_session, last_disp, last_refill = row

        pct = (current / capacity * 100) if capacity > 0 else 0

        status[ingredient] = {
            "pump_address": address,
            "current_ul": current,
            "max_capacity_ul": capacity,
            "percent_remaining": pct,
            "alert_active": current < threshold,
            "alert_threshold_ul": threshold,
            "total_dispensed_ul": dispensed,
            "last_session_id": last_session,
            "last_dispensed_at": last_disp,
            "last_refilled_at": last_refill,
        }

    return status


def update_global_volume_after_dispense(
    db_path: str,
    protocol_id: str,
    pump_address: int,
    volume_dispensed_ul: float,
    session_id: Optional[str] = None
) -> None:
    """
    Decrement global volume after a dispense cycle.

    Args:
        db_path: Path to SQLite database
        protocol_id: Protocol identifier
        pump_address: Pump network address
        volume_dispensed_ul: Volume dispensed in µL
        session_id: Session that triggered the dispense (for tracking)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE pump_global_state
            SET current_volume_ul = MAX(0, current_volume_ul - ?),
                total_dispensed_ul = total_dispensed_ul + ?,
                last_dispensed_at = CURRENT_TIMESTAMP,
                last_session_id = COALESCE(?, last_session_id),
                updated_at = CURRENT_TIMESTAMP
            WHERE protocol_id = ? AND pump_address = ?
        """, (volume_dispensed_ul, volume_dispensed_ul, session_id,
              protocol_id, pump_address))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Failed to update global volume after dispense: {e}")


def update_global_volume_after_refill(
    db_path: str,
    protocol_id: str,
    pump_address: int,
    new_volume_ul: float,
) -> float:
    """
    Update global volume after refill. Sets volume to new_volume_ul.

    The moderator enters the volume AFTER the purge has already occurred,
    so the entered value is already the actual available volume — no deduction needed.

    Args:
        db_path: Path to SQLite database
        protocol_id: Protocol identifier
        pump_address: Pump network address
        new_volume_ul: Volume in syringe after purge (µL)

    Returns:
        Final tracked volume (µL)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE pump_global_state
            SET current_volume_ul = ?,
                last_refilled_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE protocol_id = ? AND pump_address = ?
        """, (new_volume_ul, protocol_id, pump_address))

        conn.commit()
        conn.close()

        logger.info(
            f"Global refill: protocol={protocol_id}, addr={pump_address}, "
            f"final={new_volume_ul}µL"
        )

    except Exception as e:
        logger.error(f"Failed to update global volume after refill: {e}")

    return new_volume_ul


def set_global_volume(
    db_path: str,
    protocol_id: str,
    pump_address: int,
    volume_ul: float
) -> None:
    """
    Set the global volume directly (used during session start initialization).

    Args:
        db_path: Path to SQLite database
        protocol_id: Protocol identifier
        pump_address: Pump network address
        volume_ul: Volume to set (µL)
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE pump_global_state
            SET current_volume_ul = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE protocol_id = ? AND pump_address = ?
        """, (volume_ul, protocol_id, pump_address))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Failed to set global volume: {e}")
