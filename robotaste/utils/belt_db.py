"""
Database helper functions for belt operations.

Provides CRUD operations for belt_operations and belt_logs tables,
used by the belt control service to manage conveyor belt tasks.
"""

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
        # Default to robotaste.db in root directory (same as main app)
        db_path = Path(__file__).parent.parent.parent / "robotaste.db"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn


def create_belt_operation(
    session_id: str,
    cycle_number: int,
    operation_type: str,
    target_position: Optional[str] = None,
    mix_count: Optional[int] = None,
    db_path: Optional[str] = None
) -> int:
    """
    Create a new belt operation entry.

    Args:
        session_id: Session ID
        cycle_number: Cycle number
        operation_type: Type of operation ('position_spout', 'position_display', 'mix')
        target_position: Target position for position operations ('spout' or 'display')
        mix_count: Number of oscillations for mix operations
        db_path: Database path (optional)

    Returns:
        Operation ID
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO belt_operations 
        (session_id, cycle_number, operation_type, target_position, mix_count, status)
        VALUES (?, ?, ?, ?, ?, 'pending')
        """,
        (session_id, cycle_number, operation_type, target_position, mix_count)
    )

    operation_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return operation_id


def get_pending_belt_operations(
    limit: int = 10,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get pending belt operations ordered by creation time.

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
        FROM belt_operations
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_belt_operation_by_id(
    operation_id: int,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get belt operation by ID.

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
        FROM belt_operations
        WHERE id = ?
        """,
        (operation_id,)
    )

    row = cursor.fetchone()
    conn.close()

    return dict(row) if row else None


def get_current_belt_operation_for_session(
    session_id: str,
    db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Get the current in-progress or most recent belt operation for a session.

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
        FROM belt_operations
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
            FROM belt_operations
            WHERE session_id = ? AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (session_id,)
        )
        row = cursor.fetchone()

    conn.close()

    return dict(row) if row else None


def get_pending_belt_operations_for_cycle(
    session_id: str,
    cycle_number: int,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all pending belt operations for a specific cycle.

    Args:
        session_id: Session ID
        cycle_number: Cycle number
        db_path: Database path (optional)

    Returns:
        List of pending operation dictionaries for the cycle
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM belt_operations
        WHERE session_id = ? AND cycle_number = ? AND status = 'pending'
        ORDER BY created_at ASC
        """,
        (session_id, cycle_number)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_belt_operation_status(
    operation_id: int,
    status: str,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None,
    error_message: Optional[str] = None,
    db_path: Optional[str] = None
) -> None:
    """
    Update belt operation status and related fields.

    Args:
        operation_id: Operation ID
        status: New status ('pending', 'in_progress', 'completed', 'failed', 'skipped')
        started_at: Start timestamp (ISO format)
        completed_at: Completion timestamp (ISO format)
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

    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)

    params.append(operation_id)

    query = f"""
        UPDATE belt_operations
        SET {', '.join(updates)}
        WHERE id = ?
    """

    cursor.execute(query, params)
    conn.commit()
    conn.close()


def mark_belt_operation_in_progress(
    operation_id: int,
    db_path: Optional[str] = None
) -> None:
    """
    Mark belt operation as in_progress with current timestamp.

    Args:
        operation_id: Operation ID
        db_path: Database path (optional)
    """
    update_belt_operation_status(
        operation_id,
        status='in_progress',
        started_at=datetime.now().isoformat(),
        db_path=db_path
    )


def mark_belt_operation_completed(
    operation_id: int,
    db_path: Optional[str] = None
) -> None:
    """
    Mark belt operation as completed with current timestamp.

    Args:
        operation_id: Operation ID
        db_path: Database path (optional)
    """
    update_belt_operation_status(
        operation_id,
        status='completed',
        completed_at=datetime.now().isoformat(),
        db_path=db_path
    )


def mark_belt_operation_failed(
    operation_id: int,
    error_message: str,
    db_path: Optional[str] = None
) -> None:
    """
    Mark belt operation as failed with error message.

    Args:
        operation_id: Operation ID
        error_message: Error description
        db_path: Database path (optional)
    """
    update_belt_operation_status(
        operation_id,
        status='failed',
        completed_at=datetime.now().isoformat(),
        error_message=error_message,
        db_path=db_path
    )


def mark_belt_operation_skipped(
    operation_id: int,
    reason: str,
    db_path: Optional[str] = None
) -> None:
    """
    Mark belt operation as skipped (e.g., mixing skipped due to error).

    Args:
        operation_id: Operation ID
        reason: Reason for skipping
        db_path: Database path (optional)
    """
    update_belt_operation_status(
        operation_id,
        status='skipped',
        completed_at=datetime.now().isoformat(),
        error_message=reason,
        db_path=db_path
    )


def log_belt_command(
    operation_id: int,
    command: str,
    response: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    db_path: Optional[str] = None
) -> int:
    """
    Log a belt command for debugging and audit trail.

    Args:
        operation_id: Operation ID
        command: Command sent to belt controller
        response: Response from belt controller (optional)
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
        INSERT INTO belt_logs (operation_id, command, response, success, error_message)
        VALUES (?, ?, ?, ?, ?)
        """,
        (operation_id, command, response, 1 if success else 0, error_message)
    )

    log_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return log_id


def get_belt_operation_logs(
    operation_id: int,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all logs for a specific belt operation.

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
        FROM belt_logs
        WHERE operation_id = ?
        ORDER BY timestamp ASC
        """,
        (operation_id,)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_recent_belt_operations(
    session_id: Optional[str] = None,
    limit: int = 10,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get recent belt operations, optionally filtered by session.

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
            FROM belt_operations
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
            FROM belt_operations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_belt_operation_stats(
    session_id: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, int]:
    """
    Get statistics about belt operations.

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
            FROM belt_operations
            WHERE session_id = ?
            GROUP BY status
            """,
            (session_id,)
        )
    else:
        cursor.execute(
            """
            SELECT status, COUNT(*) as count
            FROM belt_operations
            GROUP BY status
            """
        )

    rows = cursor.fetchall()
    conn.close()

    stats = {
        'pending': 0,
        'in_progress': 0,
        'completed': 0,
        'failed': 0,
        'skipped': 0
    }

    for row in rows:
        stats[row['status']] = row['count']

    return stats


def are_all_belt_operations_complete_for_cycle(
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
        True if all operations are completed or skipped, False otherwise
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) as count
        FROM belt_operations
        WHERE session_id = ? AND cycle_number = ? 
        AND status NOT IN ('completed', 'skipped')
        """,
        (session_id, cycle_number)
    )

    row = cursor.fetchone()
    conn.close()

    return row['count'] == 0
