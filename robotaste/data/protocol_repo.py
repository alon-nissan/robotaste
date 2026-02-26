"""
Protocol Repository - Database Operations for Protocols

This module handles all database CRUD operations for the protocol_library table.
This is the corrected version that properly uses the database connection
context manager.

Author: RoboTaste Team
Version: 1.1
Created: 2026-01-01
"""

import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

# Correctly import the database connection context manager
from robotaste.data.database import get_database_connection
from robotaste.config.protocols import (
    export_protocol_to_json_string,
    import_protocol_from_json_string,
    compute_protocol_hash,
    validate_protocol
)

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol CRUD Operations
# =============================================================================

def create_protocol_in_db(protocol: Dict[str, Any]) -> Optional[str]:
    """
    Save a new protocol to the database.

    Args:
        protocol: Protocol dictionary

    Returns:
        protocol_id if successful, None otherwise
    """
    try:
        # Validate protocol
        is_valid, errors = validate_protocol(protocol)
        if not is_valid:
            logger.error(f"Cannot save invalid protocol: {errors}")
            return None

        # Convert to JSON
        protocol_json = export_protocol_to_json_string(protocol)
        if not protocol_json:
            logger.error("Failed to convert protocol to JSON")
            return None

        # Extract metadata
        protocol_id = protocol.get("protocol_id")
        name = protocol.get("name")
        description = protocol.get("description", "")
        version = protocol.get("version", "1.0")
        created_by = protocol.get("created_by", "")
        tags = json.dumps(protocol.get("tags", []))
        protocol_hash = protocol.get("protocol_hash", compute_protocol_hash(protocol))

        # Insert into database using the connection context manager
        with get_database_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO protocol_library (
                        protocol_id, name, description, protocol_json,
                        protocol_hash, version, created_by, tags,
                        created_at, updated_at, is_archived
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    protocol_id, name, description, protocol_json,
                    protocol_hash, version, created_by, tags,
                    datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(), 0
                ))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        logger.info(f"Created protocol in database: {name} (ID: {protocol_id})")
        return protocol_id

    except sqlite3.IntegrityError as e:
        logger.error(f"Protocol ID already exists: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to create protocol in database: {e}")
        return None


def get_protocol_by_id(protocol_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a protocol by ID.

    Args:
        protocol_id: Protocol ID

    Returns:
        Protocol dictionary if found, None otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT protocol_json FROM protocol_library
                WHERE protocol_id = ? AND deleted_at IS NULL
            """, (protocol_id,))
            row = cursor.fetchone()

        if not row:
            logger.warning(f"Protocol not found: {protocol_id}")
            return None

        protocol_json = row[0]
        protocol = import_protocol_from_json_string(protocol_json)

        return protocol

    except Exception as e:
        logger.error(f"Failed to retrieve protocol {protocol_id}: {e}")
        return None


def list_protocols(
    search: Optional[str] = None,
    tags: Optional[List[str]] = None,
    created_by: Optional[str] = None,
    include_archived: bool = False
) -> List[Dict[str, Any]]:
    """
    List all protocols with optional filtering.

    Args:
        search: Search term for name/description
        tags: Filter by tags (OR logic)
        created_by: Filter by creator
        include_archived: Include archived protocols

    Returns:
        List of protocol metadata dictionaries
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Build query
            query = """
                SELECT protocol_id, name, description, version, created_by,
                       created_at, updated_at, is_archived, tags
                FROM protocol_library
                WHERE deleted_at IS NULL
            """
            params = []

            # Filter archived
            if not include_archived:
                query += " AND is_archived = 0"

            # Search filter
            if search:
                query += " AND (name LIKE ? OR description LIKE ?)"
                search_pattern = f"%{search}%"
                params.extend([search_pattern, search_pattern])

            # Created by filter
            if created_by:
                query += " AND created_by = ?"
                params.append(created_by)

            # Order by most recent
            query += " ORDER BY created_at DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

        protocols = []
        for row in rows:
            protocol_meta = {
                "protocol_id": row[0],
                "name": row[1],
                "description": row[2],
                "version": row[3],
                "created_by": row[4],
                "created_at": row[5],
                "updated_at": row[6],
                "is_archived": bool(row[7]),
                "tags": json.loads(row[8]) if row[8] else []
            }

            # Tag filter (post-query since tags are JSON)
            if tags:
                protocol_tags = set(protocol_meta["tags"])
                if not any(tag in protocol_tags for tag in tags):
                    continue

            protocols.append(protocol_meta)

        logger.info(f"Retrieved {len(protocols)} protocols")
        return protocols

    except Exception as e:
        logger.error(f"Failed to list protocols: {e}")
        return []


def update_protocol(protocol: Dict[str, Any]) -> bool:
    """
    Update an existing protocol in the database.

    Args:
        protocol: Protocol dictionary with updated data

    Returns:
        True if successful, False otherwise
    """
    try:
        # Validate protocol
        is_valid, errors = validate_protocol(protocol)
        if not is_valid:
            logger.error(f"Cannot update with invalid protocol: {errors}")
            return False

        # Convert to JSON
        protocol_json = export_protocol_to_json_string(protocol)
        if not protocol_json:
            logger.error("Failed to convert protocol to JSON")
            return False

        # Extract metadata
        protocol_id = protocol.get("protocol_id")
        name = protocol.get("name")
        description = protocol.get("description", "")
        version = protocol.get("version", "1.0")
        tags = json.dumps(protocol.get("tags", []))
        protocol_hash = protocol.get("protocol_hash", compute_protocol_hash(protocol))

        with get_database_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    UPDATE protocol_library
                    SET name = ?, description = ?, protocol_json = ?,
                        protocol_hash = ?, version = ?, tags = ?,
                        updated_at = ?
                    WHERE protocol_id = ? AND deleted_at IS NULL
                """, (
                    name, description, protocol_json,
                    protocol_hash, version, tags,
                    datetime.now(timezone.utc).isoformat(),
                    protocol_id
                ))
                rows_affected = cursor.rowcount
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        if rows_affected == 0:
            logger.warning(f"Protocol not found for update: {protocol_id}")
            return False

        logger.info(f"Updated protocol: {name} (ID: {protocol_id})")
        return True

    except Exception as e:
        logger.error(f"Failed to update protocol: {e}")
        return False


def delete_protocol(protocol_id: str, hard_delete: bool = False) -> bool:
    """
    Delete a protocol from the database.

    Args:
        protocol_id: Protocol ID
        hard_delete: If True, permanently delete. If False, soft delete (set deleted_at)

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            try:
                if hard_delete:
                    # Permanent deletion
                    cursor.execute("""
                        DELETE FROM protocol_library
                        WHERE protocol_id = ?
                    """, (protocol_id,))
                else:
                    # Soft deletion
                    cursor.execute("""
                        UPDATE protocol_library
                        SET deleted_at = ?
                        WHERE protocol_id = ? AND deleted_at IS NULL
                    """, (datetime.now(timezone.utc).isoformat(), protocol_id))

                rows_affected = cursor.rowcount
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        if rows_affected == 0:
            logger.warning(f"Protocol not found for deletion: {protocol_id}")
            return False

        delete_type = "permanently deleted" if hard_delete else "soft deleted"
        logger.info(f"Protocol {delete_type}: {protocol_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to delete protocol: {e}")
        return False


def archive_protocol(protocol_id: str, archived: bool = True) -> bool:
    """
    Archive or unarchive a protocol.

    Args:
        protocol_id: Protocol ID
        archived: True to archive, False to unarchive

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE protocol_library
                SET is_archived = ?, updated_at = ?
                WHERE protocol_id = ? AND deleted_at IS NULL
            """, (1 if archived else 0, datetime.now(timezone.utc).isoformat(), protocol_id))
            rows_affected = cursor.rowcount
            conn.commit()

        if rows_affected == 0:
            logger.warning(f"Protocol not found for archiving: {protocol_id}")
            return False

        action = "archived" if archived else "unarchived"
        logger.info(f"Protocol {action}: {protocol_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to archive protocol: {e}")
        return False


# =============================================================================
# Protocol Statistics & Queries
# =============================================================================

def get_protocol_count(include_archived: bool = False) -> int:
    """
    Get total count of protocols in the library.

    Args:
        include_archived: Include archived protocols in count

    Returns:
        Number of protocols
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM protocol_library WHERE deleted_at IS NULL"
            if not include_archived:
                query += " AND is_archived = 0"
            cursor.execute(query)
            count = cursor.fetchone()[0]
        return count

    except Exception as e:
        logger.error(f"Failed to get protocol count: {e}")
        return 0


def search_protocols_by_ingredients(ingredient_names: List[str]) -> List[Dict[str, Any]]:
    """
    Find protocols that use specific ingredients.

    Args:
        ingredient_names: List of ingredient names to search for

    Returns:
        List of matching protocol metadata
    """
    try:
        # Get all protocols
        all_protocols_meta = list_protocols()

        matching = []
        for proto_meta in all_protocols_meta:
            # Load full protocol to check ingredients
            protocol = get_protocol_by_id(proto_meta["protocol_id"])
            if not protocol:
                continue

            # Check if any of the search ingredients are in this protocol
            protocol_ingredients = {ing["name"] for ing in protocol.get("ingredients", [])}
            if any(name in protocol_ingredients for name in ingredient_names):
                matching.append(proto_meta)

        logger.info(f"Found {len(matching)} protocols with ingredients {ingredient_names}")
        return matching

    except Exception as e:
        logger.error(f"Failed to search protocols by ingredients: {e}")
        return []


def get_all_tags() -> List[str]:
    """
    Get all unique tags used across all protocols.

    Returns:
        Sorted list of unique tags
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT tags FROM protocol_library
                WHERE deleted_at IS NULL AND is_archived = 0
            """)
            rows = cursor.fetchall()

        all_tags = set()
        for row in rows:
            if row[0]:
                tags = json.loads(row[0])
                all_tags.update(tags)

        return sorted(all_tags)

    except Exception as e:
        logger.error(f"Failed to get all tags: {e}")
        return []


# Export key functions
__all__ = [
    'create_protocol_in_db',
    'get_protocol_by_id',
    'list_protocols',
    'update_protocol',
    'delete_protocol',
    'archive_protocol',
    'get_protocol_count',
    'search_protocols_by_ingredients',
    'get_all_tags',
    'get_protocol_usage_stats'
]


def get_protocol_usage_stats(protocol_id: str) -> Dict[str, Any]:
    """
    Get statistics on protocol usage across sessions.

    Args:
        protocol_id: Protocol UUID

    Returns:
        Dictionary with usage statistics:
        {
            "total_sessions": int,
            "active_sessions": int,
            "completed_sessions": int,
            "total_samples": int,
            "first_used": str (ISO datetime) or None,
            "last_used": str (ISO datetime) or None
        }

    Example:
        >>> stats = get_protocol_usage_stats("protocol-123")
        >>> print(f"Used in {stats['total_sessions']} sessions")
        >>> print(f"Total samples collected: {stats['total_samples']}")
    """
    try:
        from robotaste.data.database import get_sessions_by_protocol, get_database_connection

        # Get all sessions using this protocol
        sessions = get_sessions_by_protocol(protocol_id)

        if not sessions:
            return {
                "total_sessions": 0,
                "active_sessions": 0,
                "completed_sessions": 0,
                "total_samples": 0,
                "first_used": None,
                "last_used": None
            }

        # Count active vs completed sessions
        active = sum(1 for s in sessions if s.get('current_phase') != 'completion')
        completed = len(sessions) - active

        # Get total sample count across all sessions
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Count samples from sessions using this protocol
            cursor.execute("""
                SELECT COUNT(*) as total_samples
                FROM samples
                WHERE session_id IN (
                    SELECT session_id FROM sessions WHERE protocol_id = ?
                )
            """, (protocol_id,))

            total_samples = cursor.fetchone()['total_samples']

        # Get first and last usage dates
        first_used = sessions[-1]['created_at'] if sessions else None
        last_used = sessions[0]['created_at'] if sessions else None

        return {
            "total_sessions": len(sessions),
            "active_sessions": active,
            "completed_sessions": completed,
            "total_samples": total_samples,
            "first_used": first_used,
            "last_used": last_used
        }

    except Exception as e:
        logger.error(f"Failed to get protocol usage stats: {e}")
        return {
            "total_sessions": 0,
            "active_sessions": 0,
            "completed_sessions": 0,
            "total_samples": 0,
            "first_used": None,
            "last_used": None,
            "error": str(e)
        }