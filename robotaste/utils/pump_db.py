"""
Database helper functions for pump operations.

Provides CRUD operations for pump_operations and pump_logs tables,
used by the pump control service to manage dispensing tasks.
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Get database connection.

    Args:
        db_path: Path to database file (optional, defaults to robotaste.db)

    Returns:
        SQLite connection
    """
    if db_path is None:
        # Default to robotaste.db in data directory
        db_path = Path(__file__).parent.parent / "data" / "robotaste.db"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def create_pump_operation(
    session_id: str,
    cycle_number: int,
    recipe_json: str,
    trial_number: int = 1,
    db_path: Optional[str] = None
) -> int:
    """
    Create a new pump operation entry.

    Args:
        session_id: Session ID
        cycle_number: Cycle number
        recipe_json: JSON string with ingredient volumes {"ingredient": volume_ul, ...}
        trial_number: Trial number (default 1)
        db_path: Database path (optional)

    Returns:
        Operation ID
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO pump_operations (session_id, cycle_number, trial_number, recipe_json, status)
        VALUES (?, ?, ?, ?, 'pending')
        """,
        (session_id, cycle_number, trial_number, recipe_json)
    )

    operation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return operation_id


def get_pending_operations(
    limit: int = 10,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get pending pump operations ordered by creation time.

    Args:
        limit: Maximum number of operations to return
        db_path: Database path (optional)

    Returns:
        List of operation dictionaries
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM pump_operations
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_operation_by_id(
    operation_id: int,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get pump operation by ID.

    Args:
        operation_id: Operation ID
        db_path: Database path (optional)

    Returns:
        Operation dictionary or None if not found
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM pump_operations
        WHERE id = ?
        """,
        (operation_id,)
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_current_operation_for_session(
    session_id: str,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the current in-progress or most recent operation for a session.

    Args:
        session_id: Session ID
        db_path: Database path (optional)

    Returns:
        Operation dictionary or None if not found
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # First try to get in_progress operation
    cursor.execute(
        """
        SELECT *
        FROM pump_operations
        WHERE session_id = ? AND status = 'in_progress'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (session_id,)
    )

    row = cursor.fetchone()

    # If no in_progress, get most recent pending
    if not row:
        cursor.execute(
            """
            SELECT *
            FROM pump_operations
            WHERE session_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,)
        )
        row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None


def update_operation_status(
    operation_id: int,
    status: str,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    actual_volumes_json: Optional[str] = None,
    error_message: Optional[str] = None,
    db_path: Optional[str] = None
) -> None:
    """
    Update pump operation status and related fields.

    Args:
        operation_id: Operation ID
        status: New status ('pending', 'in_progress', 'completed', 'failed')
        started_at: Start timestamp (ISO format)
        completed_at: Completion timestamp (ISO format)
        actual_volumes_json: JSON string with actual dispensed volumes
        error_message: Error message if failed
        db_path: Database path (optional)
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Build update query dynamically
    updates = ["status = ?"]
    params = [status]

    if started_at is not None:
        updates.append("started_at = ?")
        params.append(started_at)

    if completed_at is not None:
        updates.append("completed_at = ?")
        params.append(completed_at)

    if actual_volumes_json is not None:
        updates.append("actual_volumes_json = ?")
        params.append(actual_volumes_json)

    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)

    params.append(operation_id)

    query = f"""
        UPDATE pump_operations
        SET {', '.join(updates)}
        WHERE id = ?
    """

    cursor.execute(query, params)
    conn.commit()
    conn.close()


def mark_operation_in_progress(
    operation_id: int,
    db_path: Optional[str] = None
) -> None:
    """
    Mark operation as in_progress with current timestamp.

    Args:
        operation_id: Operation ID
        db_path: Database path (optional)
    """
    update_operation_status(
        operation_id,
        status='in_progress',
        started_at=datetime.now().isoformat(),
        db_path=db_path
    )


def mark_operation_completed(
    operation_id: int,
    actual_volumes: Optional[Dict[str, float]] = None,
    db_path: Optional[str] = None
) -> None:
    """
    Mark operation as completed with current timestamp.

    Args:
        operation_id: Operation ID
        actual_volumes: Dictionary of actual dispensed volumes (optional)
        db_path: Database path (optional)
    """
    actual_volumes_json = json.dumps(actual_volumes) if actual_volumes else None

    update_operation_status(
        operation_id,
        status='completed',
        completed_at=datetime.now().isoformat(),
        actual_volumes_json=actual_volumes_json,
        db_path=db_path
    )


def mark_operation_failed(
    operation_id: int,
    error_message: str,
    db_path: Optional[str] = None
) -> None:
    """
    Mark operation as failed with error message.

    Args:
        operation_id: Operation ID
        error_message: Error description
        db_path: Database path (optional)
    """
    update_operation_status(
        operation_id,
        status='failed',
        completed_at=datetime.now().isoformat(),
        error_message=error_message,
        db_path=db_path
    )


def log_pump_command(
    operation_id: int,
    pump_address: int,
    command: str,
    response: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    db_path: Optional[str] = None
) -> int:
    """
    Log a pump command for debugging and audit trail.

    Args:
        operation_id: Operation ID
        pump_address: Pump network address
        command: Command sent to pump
        response: Response from pump (optional)
        success: Whether command succeeded
        error_message: Error message if failed
        db_path: Database path (optional)

    Returns:
        Log entry ID
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO pump_logs (operation_id, pump_address, command, response, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (operation_id, pump_address, command, response, 1 if success else 0, error_message)
    )

    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return log_id


def get_operation_logs(
    operation_id: int,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all logs for a specific operation.

    Args:
        operation_id: Operation ID
        db_path: Database path (optional)

    Returns:
        List of log entry dictionaries
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM pump_logs
        WHERE operation_id = ?
        ORDER BY timestamp ASC
        """,
        (operation_id,)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_recent_operations(
    session_id: Optional[str] = None,
    limit: int = 10,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get recent pump operations, optionally filtered by session.

    Args:
        session_id: Session ID to filter by (optional)
        limit: Maximum number of operations to return
        db_path: Database path (optional)

    Returns:
        List of operation dictionaries
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if session_id:
        cursor.execute(
            """
            SELECT *
            FROM pump_operations
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit)
        )
    else:
        cursor.execute(
            """
            SELECT *
            FROM pump_operations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_operation_stats(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, int]:
    """
    Get statistics about pump operations.

    Args:
        session_id: Session ID to filter by (optional)
        db_path: Database path (optional)

    Returns:
        Dictionary with counts by status
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if session_id:
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM pump_operations
            WHERE session_id = ?
            GROUP BY status
            """,
            (session_id,)
        )
    else:
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM pump_operations
            GROUP BY status
            """
        )

    rows = cursor.fetchall()
    conn.close()

    stats = {
        'pending': 0,
        'in_progress': 0,
        'completed': 0,
        'failed': 0
    }

    for row in rows:
        stats[row['status']] = row['count']

    return stats


def delete_old_operations(
    days_old: int = 30,
    keep_failed: bool = True,
    db_path: Optional[str] = None
) -> int:
    """
    Delete old completed pump operations (maintenance function).

    Args:
        days_old: Delete operations older than this many days
        keep_failed: If True, don't delete failed operations
        db_path: Database path (optional)

    Returns:
        Number of operations deleted
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    if keep_failed:
        cursor.execute(
            """
            DELETE FROM pump_operations
            WHERE status = 'completed'
            AND datetime(completed_at) < datetime('now', ? || ' days')
            """,
            (-days_old,)
        )
    else:
        cursor.execute(
            """
            DELETE FROM pump_operations
            WHERE status IN ('completed', 'failed')
            AND datetime(completed_at) < datetime('now', ? || ' days')
            """,
            (-days_old,)
        )

    deleted_count = cursor.rowcount
    conn.commit()
    conn.close()

    return deleted_count
