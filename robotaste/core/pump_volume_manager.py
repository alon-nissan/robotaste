"""
Pump Volume Tracking Manager

Manages real-time volume tracking for syringe pumps to prevent running empty
during experiments. Provides volume initialization, decrement tracking, refill
recording, and alert notifications.

All volumes are in microliters (µL) to match database/UI conventions.
"""

import sqlite3
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def initialize_volume_tracking(
    db_path: str,
    session_id: str,
    ingredient_volumes: Dict[str, Dict[str, float]]
) -> bool:
    """
    Initialize volume tracking at session start.

    Args:
        db_path: Path to SQLite database
        session_id: Session UUID
        ingredient_volumes: {
            "Sugar": {
                "max_capacity_ul": 60000,
                "initial_volume_ul": 50000,
                "alert_threshold_ul": 2000
            }
        }

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for ingredient, config in ingredient_volumes.items():
            max_capacity = config["max_capacity_ul"]
            initial_volume = config["initial_volume_ul"]
            alert_threshold = config.get("alert_threshold_ul", 2000.0)

            # Validation
            if initial_volume > max_capacity:
                logger.warning(
                    f"Initial volume ({initial_volume}) exceeds max capacity ({max_capacity}) "
                    f"for {ingredient}. Capping at max capacity."
                )
                initial_volume = max_capacity

            # Insert or replace volume state
            cursor.execute("""
                INSERT OR REPLACE INTO pump_volume_state (
                    session_id, ingredient_name, max_capacity_ul,
                    initial_volume_ul, current_volume_ul,
                    alert_threshold_ul, total_dispensed_ul
                ) VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (
                session_id, ingredient, max_capacity,
                initial_volume, initial_volume, alert_threshold
            ))

            # Log initialization event
            cursor.execute("""
                INSERT INTO pump_volume_history (
                    session_id, ingredient_name, event_type,
                    volume_change_ul, volume_before_ul, volume_after_ul,
                    notes
                ) VALUES (?, ?, 'init', ?, 0, ?, 'Initial volume set')
            """, (session_id, ingredient, initial_volume, initial_volume))

        conn.commit()
        conn.close()

        logger.info(f"Volume tracking initialized for session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize volume tracking: {e}")
        return False


def update_volume_after_dispense(
    db_path: str,
    session_id: str,
    actual_volumes: Dict[str, float],
    cycle_number: int
) -> None:
    """
    Decrement volumes after pump operation completes.

    Args:
        db_path: Path to SQLite database
        session_id: Session UUID
        actual_volumes: {"Sugar": 125.0, "Salt": 40.0} in µL
        cycle_number: Current cycle number
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for ingredient, volume_dispensed in actual_volumes.items():
            # Get current state
            cursor.execute("""
                SELECT current_volume_ul, total_dispensed_ul
                FROM pump_volume_state
                WHERE session_id = ? AND ingredient_name = ?
            """, (session_id, ingredient))

            row = cursor.fetchone()
            if not row:
                logger.warning(
                    f"No volume tracking found for {ingredient} in session {session_id}. "
                    "Skipping volume update."
                )
                continue

            volume_before = row[0]
            total_dispensed = row[1]

            # Calculate new volume
            volume_after = max(0, volume_before - volume_dispensed)

            if volume_after == 0 and volume_before > 0:
                logger.warning(
                    f"Pump {ingredient} has run empty! "
                    f"Dispensed {volume_dispensed}µL from {volume_before}µL remaining."
                )

            # Update state
            cursor.execute("""
                UPDATE pump_volume_state
                SET current_volume_ul = ?,
                    total_dispensed_ul = ?,
                    last_dispensed_at = CURRENT_TIMESTAMP
                WHERE session_id = ? AND ingredient_name = ?
            """, (volume_after, total_dispensed + volume_dispensed, session_id, ingredient))

            # Log dispense event
            cursor.execute("""
                INSERT INTO pump_volume_history (
                    session_id, ingredient_name, event_type,
                    volume_change_ul, volume_before_ul, volume_after_ul,
                    cycle_number
                ) VALUES (?, ?, 'dispense', ?, ?, ?, ?)
            """, (
                session_id, ingredient, -volume_dispensed,
                volume_before, volume_after, cycle_number
            ))

        conn.commit()
        conn.close()

    except Exception as e:
        logger.error(f"Failed to update volumes after dispense: {e}")


def get_volume_status(db_path: str, session_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Get current volume status for all pumps in session.

    Args:
        db_path: Path to SQLite database
        session_id: Session UUID

    Returns:
        {
            "Sugar": {
                "current_ul": 39000,
                "max_capacity_ul": 60000,
                "percent_remaining": 65.0,
                "alert_active": False,
                "alert_threshold_ul": 2000,
                "total_dispensed_ul": 11000,
                "last_dispensed_at": "2026-01-29 14:30:00"
            }
        }
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                ingredient_name, current_volume_ul, max_capacity_ul,
                alert_threshold_ul, total_dispensed_ul,
                last_dispensed_at, last_refilled_at
            FROM pump_volume_state
            WHERE session_id = ?
            ORDER BY ingredient_name
        """, (session_id,))

        status = {}
        for row in cursor.fetchall():
            ingredient = row[0]
            current_ul = row[1]
            max_capacity_ul = row[2]
            alert_threshold_ul = row[3]
            total_dispensed_ul = row[4]
            last_dispensed_at = row[5]
            last_refilled_at = row[6]

            percent_remaining = (current_ul / max_capacity_ul * 100) if max_capacity_ul > 0 else 0
            alert_active = current_ul < alert_threshold_ul

            status[ingredient] = {
                "current_ul": current_ul,
                "max_capacity_ul": max_capacity_ul,
                "percent_remaining": percent_remaining,
                "alert_active": alert_active,
                "alert_threshold_ul": alert_threshold_ul,
                "total_dispensed_ul": total_dispensed_ul,
                "last_dispensed_at": last_dispensed_at,
                "last_refilled_at": last_refilled_at
            }

        conn.close()
        return status

    except Exception as e:
        logger.error(f"Failed to get volume status: {e}")
        return {}


def record_refill(
    db_path: str,
    session_id: str,
    ingredient: str,
    new_total_volume_ul: float,
    notes: str = ""
) -> bool:
    """
    Record manual refill event.

    Args:
        db_path: Path to SQLite database
        session_id: Session UUID
        ingredient: Ingredient name
        new_total_volume_ul: New total volume after refill
        notes: Optional notes about refill

    Returns:
        True if successful, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get current state
        cursor.execute("""
            SELECT current_volume_ul, max_capacity_ul
            FROM pump_volume_state
            WHERE session_id = ? AND ingredient_name = ?
        """, (session_id, ingredient))

        row = cursor.fetchone()
        if not row:
            logger.error(f"No volume tracking found for {ingredient} in session {session_id}")
            conn.close()
            return False

        volume_before = row[0]
        max_capacity = row[1]

        # Validate refill
        if new_total_volume_ul > max_capacity:
            logger.error(
                f"Refill volume ({new_total_volume_ul}µL) exceeds max capacity ({max_capacity}µL)"
            )
            conn.close()
            return False

        if new_total_volume_ul < 0:
            logger.error("Refill volume cannot be negative")
            conn.close()
            return False

        volume_change = new_total_volume_ul - volume_before

        # Update state
        cursor.execute("""
            UPDATE pump_volume_state
            SET current_volume_ul = ?,
                last_refilled_at = CURRENT_TIMESTAMP
            WHERE session_id = ? AND ingredient_name = ?
        """, (new_total_volume_ul, session_id, ingredient))

        # Log refill event
        cursor.execute("""
            INSERT INTO pump_volume_history (
                session_id, ingredient_name, event_type,
                volume_change_ul, volume_before_ul, volume_after_ul,
                notes
            ) VALUES (?, ?, 'refill', ?, ?, ?, ?)
        """, (
            session_id, ingredient, volume_change,
            volume_before, new_total_volume_ul, notes
        ))

        conn.commit()
        conn.close()

        logger.info(
            f"Refill recorded: {ingredient} {volume_before}µL → {new_total_volume_ul}µL "
            f"(+{volume_change}µL)"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to record refill: {e}")
        return False


def get_volume_history(
    db_path: str,
    session_id: str,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get volume history for session (newest first).

    Args:
        db_path: Path to SQLite database
        session_id: Session UUID
        limit: Maximum number of records to return

    Returns:
        List of history events with fields:
        - id, session_id, ingredient_name, event_type, volume_change_ul,
          volume_before_ul, volume_after_ul, cycle_number, notes, created_at
    """
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM pump_volume_history
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (session_id, limit))

        history = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return history

    except Exception as e:
        logger.error(f"Failed to get volume history: {e}")
        return []
