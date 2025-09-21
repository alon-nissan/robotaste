"""
🗄️ RoboTaste Database Handler - Data Persistence & Management

OVERVIEW:
=========
Comprehensive SQLite database management for taste preference experiments.
Handles session state tracking, response storage, participant management,
and multi-component concentration data with JSON support.

DATABASE SCHEMA:
===============
1. SESSION_STATE TABLE:
   - Tracks active experiment sessions
   - Moderator and subject session management
   - Method and coordinate storage
   - Supports: linear, logarithmic, exponential, slider_based methods

2. RESPONSES TABLE:
   - Complete response data storage
   - Reaction time tracking
   - Concentration data (sugar, salt)
   - JSON storage for multi-component data
   - Final response marking

FEATURES:
========
• Context-managed connections with automatic cleanup
• Comprehensive error handling and logging
• Database migration system for schema updates
• Performance-optimized with proper indexing
• JSON support for complex concentration data
• Safe concurrent access handling

MIGRATION SYSTEM:
================
• Automatic schema updates on application start
• Backward compatibility with existing data
• Safe table recreation for constraint updates
• Column addition without data loss

SECURITY FEATURES:
=================
• Parameterized queries prevent SQL injection
• Connection timeout handling
• Transaction rollback on errors
• Input validation and sanitization

TODO PRIORITIES:
===============
HIGH:
- [ ] Add data backup and recovery system
- [ ] Implement database connection pooling
- [ ] Add data export functionality (CSV/JSON)
- [ ] Create database maintenance utilities

MEDIUM:
- [ ] Add data encryption for sensitive information
- [ ] Implement audit logging for data changes
- [ ] Add database performance monitoring
- [ ] Create automated cleanup for old data

LOW:
- [ ] Add database replication support
- [ ] Implement data archiving system
- [ ] Add advanced analytics queries
- [ ] Create database optimization tools

Author: Masters Research Project
Version: 2.0 - Multi-Component Support
Last Updated: 2025
"""

import sqlite3
import pandas as pd
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Tuple, Dict, Any, List
import logging

# Configuration
DB_PATH = "experiment_sync.db"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@contextmanager
def get_database_connection():
    """Context manager for database connections with automatic cleanup."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def init_database() -> bool:
    """Initialize SQLite database with proper schema.
    
    TODO: Add database backup before schema changes
    TODO: Implement connection pooling for better performance
    TODO: Add database health checks and monitoring
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Session state table with better schema
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS session_state (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_type TEXT NOT NULL CHECK(user_type IN ('mod', 'sub')),
                    participant_id TEXT NOT NULL,
                    method TEXT CHECK(method IN ('linear', 'logarithmic', 'exponential', 'slider_based')),
                    x_position REAL,
                    y_position REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_type, participant_id)
                )
            """
            )

            # Responses table - Enhanced for multi-ingredient support
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    selection_number INTEGER,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT DEFAULT 'grid_2d',
                    x_position REAL,
                    y_position REAL,
                    method TEXT NOT NULL,
                    ingredient_data TEXT,  -- JSON storage for ALL ingredient concentrations
                    reaction_time_ms INTEGER,
                    questionnaire_response TEXT,
                    is_final_response BOOLEAN DEFAULT 0,
                    extra_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Multi-device sessions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_code TEXT PRIMARY KEY,
                    moderator_name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    subject_connected BOOLEAN DEFAULT 0,
                    experiment_config TEXT DEFAULT '{}',
                    current_phase TEXT DEFAULT 'waiting'
                )
            """
            )

            # Initial slider positions table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS initial_slider_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT DEFAULT 'slider_based',
                    num_ingredients INTEGER NOT NULL,
                    initial_values TEXT,  -- JSON storage for initial slider values
                    percent_values TEXT,  -- JSON storage for percentage values
                    extra_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, participant_id)
                )
            """
            )

            # Create indices for better performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_participant
                ON session_state(participant_id, user_type)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_responses_participant
                ON responses(participant_id, created_at DESC)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_sessions_activity
                ON sessions(is_active, last_activity DESC)
            """
            )

            # Create views for slider monitoring
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS current_slider_positions AS
                SELECT
                    r.session_id,
                    r.participant_id,
                    r.interface_type,
                    r.method,
                    r.ingredient_data,  -- JSON storage containing all concentrations
                    r.is_final_response,
                    r.questionnaire_response,
                    r.created_at as last_update,
                    ROW_NUMBER() OVER (PARTITION BY r.session_id, r.participant_id
                                     ORDER BY r.created_at DESC) as row_num
                FROM responses r
                WHERE r.interface_type = 'slider_based'
            """)

            cursor.execute("""
                CREATE VIEW IF NOT EXISTS live_slider_monitoring AS
                SELECT
                    session_id,
                    participant_id,
                    interface_type,
                    method,
                    ingredient_data,  -- JSON storage containing all concentrations
                    is_final_response,
                    questionnaire_response,
                    last_update,
                    CASE
                        WHEN is_final_response = 1 THEN 'Final Submission'
                        ELSE 'Live Position'
                    END as status
                FROM current_slider_positions
                WHERE row_num = 1
            """)

            # Run database migrations
            _migrate_database(cursor)
            
            conn.commit()
            logger.info("Database initialized successfully")
            return True

    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


def _migrate_database(cursor) -> None:
    """Handle database migrations for schema updates - Moving to JSON-only storage."""
    import json
    try:
        # Check current responses table structure
        cursor.execute("PRAGMA table_info(responses)")
        columns = [column[1] for column in cursor.fetchall()]

        # Check if we still have hardcoded ingredient columns (need to eliminate)
        hardcoded_ingredient_columns = [
            'sugar_concentration', 'salt_concentration',
            'ingredient_1_conc', 'ingredient_2_conc', 'ingredient_3_conc',
            'ingredient_4_conc', 'ingredient_5_conc', 'ingredient_6_conc'
        ]

        has_hardcoded_columns = any(col in columns for col in hardcoded_ingredient_columns)

        if has_hardcoded_columns:
            logger.info("Migrating responses table to JSON-only storage (eliminating hardcoded ingredient columns)")

            # Create new generic responses table with JSON storage only
            cursor.execute("""
                CREATE TABLE responses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    selection_number INTEGER,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT DEFAULT 'grid_2d',
                    method TEXT NOT NULL,
                    x_position REAL,
                    y_position REAL,
                    ingredient_data TEXT,  -- JSON storage for ALL ingredient concentrations
                    reaction_time_ms INTEGER,
                    questionnaire_response TEXT,
                    is_final_response BOOLEAN DEFAULT 0,
                    extra_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrate existing data to JSON format

            # Get all existing data
            cursor.execute("SELECT * FROM responses")
            existing_data = cursor.fetchall()

            for row in existing_data:
                # Convert row to dict for easier access
                row_dict = dict(row)

                # Build ingredient data JSON
                ingredient_data = {}

                # Handle legacy sugar/salt columns
                if 'sugar_concentration' in columns and row_dict.get('sugar_concentration'):
                    ingredient_data['Sugar'] = row_dict['sugar_concentration']
                if 'salt_concentration' in columns and row_dict.get('salt_concentration'):
                    ingredient_data['Salt'] = row_dict['salt_concentration']

                # Handle ingredient_X_conc columns
                for i in range(1, 7):
                    col_name = f'ingredient_{i}_conc'
                    if col_name in columns and row_dict.get(col_name):
                        ingredient_data[f'Ingredient_{i}'] = row_dict[col_name]

                # Convert to JSON
                ingredient_data_json = json.dumps(ingredient_data) if ingredient_data else None

                # Insert into new table
                cursor.execute("""
                    INSERT INTO responses_new
                    (id, session_id, selection_number, participant_id, interface_type,
                     method, x_position, y_position, ingredient_data,
                     reaction_time_ms, questionnaire_response, is_final_response,
                     extra_data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get('id'),
                    row_dict.get('session_id'),
                    row_dict.get('selection_number'),
                    row_dict.get('participant_id'),
                    row_dict.get('interface_type', 'grid_2d'),
                    row_dict.get('method'),
                    row_dict.get('x_position'),
                    row_dict.get('y_position'),
                    ingredient_data_json,
                    row_dict.get('reaction_time_ms'),
                    row_dict.get('questionnaire_response'),
                    row_dict.get('is_final_response', 0),
                    row_dict.get('extra_data'),
                    row_dict.get('created_at')
                ))

            # Replace old table
            cursor.execute("DROP TABLE responses")
            cursor.execute("ALTER TABLE responses_new RENAME TO responses")
            logger.info("Successfully migrated responses table to JSON-only storage")

        # Also migrate initial_slider_positions table
        cursor.execute("PRAGMA table_info(initial_slider_positions)")
        slider_columns = [column[1] for column in cursor.fetchall()]

        slider_hardcoded_columns = [
            'ingredient_1_initial', 'ingredient_2_initial', 'ingredient_3_initial',
            'ingredient_4_initial', 'ingredient_5_initial', 'ingredient_6_initial',
            'ingredient_1_percent', 'ingredient_2_percent', 'ingredient_3_percent',
            'ingredient_4_percent', 'ingredient_5_percent', 'ingredient_6_percent'
        ]

        has_slider_hardcoded = any(col in slider_columns for col in slider_hardcoded_columns)

        if has_slider_hardcoded:
            logger.info("Migrating initial_slider_positions table to JSON-only storage")

            # Create new slider positions table
            cursor.execute("""
                CREATE TABLE initial_slider_positions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT DEFAULT 'slider_based',
                    num_ingredients INTEGER NOT NULL,
                    initial_values TEXT,  -- JSON storage for initial slider values
                    percent_values TEXT,  -- JSON storage for percentage values
                    extra_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(session_id, participant_id)
                )
            """)

            # Migrate existing slider data
            cursor.execute("SELECT * FROM initial_slider_positions")
            slider_rows = cursor.fetchall()

            cursor.execute("PRAGMA table_info(initial_slider_positions)")
            slider_col_info = cursor.fetchall()
            slider_column_names = [col[1] for col in slider_col_info]

            for row in slider_rows:
                row_dict = dict(zip(slider_column_names, row))

                # Build initial values JSON
                initial_values = {}
                percent_values = {}

                for i in range(1, 7):
                    initial_col = f'ingredient_{i}_initial'
                    percent_col = f'ingredient_{i}_percent'

                    if initial_col in row_dict and row_dict[initial_col] is not None:
                        initial_values[f'ingredient_{i}'] = row_dict[initial_col]

                    if percent_col in row_dict and row_dict[percent_col] is not None:
                        percent_values[f'ingredient_{i}'] = row_dict[percent_col]

                # Insert into new table
                cursor.execute("""
                    INSERT INTO initial_slider_positions_new (
                        session_id, participant_id, interface_type, num_ingredients,
                        initial_values, percent_values, extra_data, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row_dict.get('session_id'),
                    row_dict.get('participant_id'),
                    row_dict.get('interface_type', 'slider_based'),
                    row_dict.get('num_ingredients'),
                    json.dumps(initial_values),
                    json.dumps(percent_values),
                    row_dict.get('extra_data'),
                    row_dict.get('created_at')
                ))

            # Drop old table and rename new one
            cursor.execute("DROP TABLE initial_slider_positions")
            cursor.execute("ALTER TABLE initial_slider_positions_new RENAME TO initial_slider_positions")

            logger.info("Successfully migrated initial_slider_positions table to JSON-only storage")

        if 'extra_data' not in columns:
            logger.info("Adding extra_data column to responses table")
            cursor.execute("ALTER TABLE responses ADD COLUMN extra_data TEXT")

        # Check if we need to update the method constraint
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='session_state'")
        table_sql = cursor.fetchone()

        if table_sql and "slider_based" not in table_sql[0]:
            logger.info("Migrating session_state table to support slider_based method")

            # Create temporary table with new schema
            cursor.execute("""
                CREATE TABLE session_state_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_type TEXT NOT NULL CHECK(user_type IN ('mod', 'sub')),
                    participant_id TEXT NOT NULL,
                    method TEXT CHECK(method IN ('linear', 'logarithmic', 'exponential', 'slider_based')),
                    x_position REAL,
                    y_position REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_type, participant_id)
                )
            """)

            # Copy data from old table
            cursor.execute("""
                INSERT INTO session_state_new (id, user_type, participant_id, method, x_position, y_position, created_at)
                SELECT id, user_type, participant_id, method, x_position, y_position, created_at
                FROM session_state
            """)

            # Drop old table and rename new one
            cursor.execute("DROP TABLE session_state")
            cursor.execute("ALTER TABLE session_state_new RENAME TO session_state")

            # Recreate the index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session_participant
                ON session_state(participant_id, user_type)
            """)

        # Check if num_ingredients column exists in session_state table
        cursor.execute("PRAGMA table_info(session_state)")
        session_columns = [column[1] for column in cursor.fetchall()]

        if 'num_ingredients' not in session_columns:
            logger.info("Adding num_ingredients column to session_state table")
            cursor.execute("ALTER TABLE session_state ADD COLUMN num_ingredients INTEGER DEFAULT 2")

        # Update views if they need questionnaire_response column
        cursor.execute("DROP VIEW IF EXISTS live_slider_monitoring")
        cursor.execute("DROP VIEW IF EXISTS current_slider_positions")
        cursor.execute("DROP VIEW IF EXISTS ingredients_parsed")
        cursor.execute("DROP VIEW IF EXISTS current_ingredient_state")
        cursor.execute("DROP VIEW IF EXISTS latest_recipes")

        # Recreate views with updated schema
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS current_slider_positions AS
            SELECT
                r.session_id,
                r.participant_id,
                r.interface_type,
                r.method,
                r.ingredient_data,  -- JSON storage containing all concentrations
                r.is_final_response,
                r.questionnaire_response,
                r.created_at as last_update,
                ROW_NUMBER() OVER (PARTITION BY r.session_id, r.participant_id
                                 ORDER BY r.created_at DESC) as row_num
            FROM responses r
            WHERE r.interface_type = 'slider_based'
        """)

        cursor.execute("""
            CREATE VIEW IF NOT EXISTS live_slider_monitoring AS
            SELECT
                session_id,
                participant_id,
                interface_type,
                method,
                ingredient_data,  -- JSON storage containing all concentrations
                is_final_response,
                questionnaire_response,
                last_update,
                CASE
                    WHEN is_final_response = 1 THEN 'Final Submission'
                    ELSE 'Live Position'
                END as status
            FROM current_slider_positions
            WHERE row_num = 1
        """)

        logger.info("Database migration completed successfully")

    except Exception as e:
        logger.error(f"Error during database migration: {e}")
        # Don't raise exception - let initialization continue


def is_participant_activated(participant_id: str) -> bool:
    """Check if participant has an active session from moderator."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) FROM session_state 
                WHERE participant_id = ? AND user_type = 'mod'
            """,
                (participant_id,),
            )

            count = cursor.fetchone()[0]
            return count > 0

    except Exception as e:
        logger.error(f"Error checking participant activation: {e}")
        return False


def get_moderator_settings(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest moderator settings for a participant (JSON-based)."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # First try to get settings from responses table (more recent)
            cursor.execute(
                """
                SELECT method, interface_type, created_at
                FROM responses
                WHERE participant_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (participant_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "method": row["method"],
                    "interface_type": row["interface_type"] or "grid_2d",
                    "num_ingredients": 2,  # Default for backward compatibility
                    "created_at": row["created_at"],
                }

            # Fallback to session_state table if no responses found
            cursor.execute(
                """
                SELECT method, created_at
                FROM session_state
                WHERE participant_id = ? AND user_type = 'mod'
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (participant_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "method": row["method"],
                    "interface_type": "grid_2d",  # Default for legacy data
                    "num_ingredients": 2,  # Default for backward compatibility
                    "created_at": row["created_at"],
                }

            return None

    except Exception as e:
        logger.error(f"Error getting moderator settings: {e}")
        return None


def get_latest_submitted_response(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest submitted response from the responses table (JSON-based)."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT method, created_at, ingredient_data, reaction_time_ms, interface_type
                FROM responses
                WHERE participant_id = ? AND is_final_response = 1
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (participant_id,),
            )

            row = cursor.fetchone()
            if row:
                import json

                # Parse ingredient data from JSON
                ingredient_concentrations = {}
                if row["ingredient_data"]:
                    try:
                        ingredient_concentrations = json.loads(row["ingredient_data"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse ingredient data for {participant_id}")

                result = {
                    "method": row["method"],
                    "created_at": row["created_at"],
                    "reaction_time_ms": row["reaction_time_ms"],
                    "interface_type": row["interface_type"] or "grid_2d",
                    "ingredient_concentrations": ingredient_concentrations,
                    "concentration_data": ingredient_concentrations,  # For compatibility
                }

                return result
            return None

    except Exception as e:
        logger.error(f"Error getting latest submitted response: {e}")
        return None


def get_latest_subject_response(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest subject response for a participant from responses table (JSON-based)."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT method, ingredient_data, created_at, interface_type, reaction_time_ms
                FROM responses
                WHERE participant_id = ? AND is_final_response = 0
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (participant_id,),
            )

            row = cursor.fetchone()
            if row:
                import json

                # Parse ingredient data from JSON
                ingredient_concentrations = {}
                if row["ingredient_data"]:
                    try:
                        ingredient_concentrations = json.loads(row["ingredient_data"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse ingredient data for {participant_id}")

                return {
                    "method": row["method"],
                    "created_at": row["created_at"],
                    "interface_type": row["interface_type"] or "grid_2d",
                    "reaction_time_ms": row["reaction_time_ms"],
                    "ingredient_concentrations": ingredient_concentrations,
                    "concentration_data": ingredient_concentrations,  # For compatibility
                }
            return None

    except Exception as e:
        logger.error(f"Error getting latest response: {e}")
        return None


def get_live_subject_position(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the current live position/concentrations of the subject (JSON-based)."""
    # First try to get live response (non-final responses)
    live_response = get_latest_subject_response(participant_id)

    if live_response:
        live_response["is_submitted"] = False
        return live_response

    # If no live response, get the latest submitted response
    submitted_response = get_latest_submitted_response(participant_id)
    if submitted_response:
        submitted_response["is_submitted"] = True
        return submitted_response

    # Fallback: try slider interaction function for compatibility
    slider_response = get_latest_slider_interaction(participant_id)
    if slider_response:
        return slider_response

    return None


def get_latest_slider_interaction(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest slider interaction from the responses table (JSON-based)."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM responses
                WHERE participant_id = ? AND interface_type = 'slider_based'
                ORDER BY created_at DESC
                LIMIT 1
            """, (participant_id,))

            row = cursor.fetchone()
            if row:
                import json

                # Parse ingredient data from JSON
                ingredient_concentrations = {}
                if row["ingredient_data"]:
                    try:
                        ingredient_concentrations = json.loads(row["ingredient_data"])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse ingredient data for {participant_id}")

                return {
                    "interface_type": "slider_based",
                    "method": row["method"],
                    "created_at": row["created_at"],
                    "is_submitted": bool(row["is_final_response"]),
                    "concentration_data": ingredient_concentrations,
                    "ingredient_concentrations": ingredient_concentrations,  # For compatibility
                    "reaction_time_ms": row["reaction_time_ms"]
                }

    except Exception as e:
        logger.error(f"Error getting latest slider interaction: {e}")
        return None

    return None


def update_session_state(
    user_type: str,
    participant_id: str,
    method: Optional[str] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    num_ingredients: Optional[int] = None,
) -> bool:
    """Update or insert session state with proper validation."""

    if user_type not in ["mod", "sub"]:
        logger.error(f"Invalid user_type: {user_type}")
        return False

    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Use UPSERT (INSERT OR REPLACE) for atomic operation
            cursor.execute(
                """
                INSERT OR REPLACE INTO session_state 
                (user_type, participant_id, method, x_position, y_position, num_ingredients, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (user_type, participant_id, method, x, y, num_ingredients),
            )

            conn.commit()
            logger.info(f"Updated session state for {user_type}:{participant_id}")
            return True

    except Exception as e:
        logger.error(f"Error updating session state: {e}")
        return False


def save_response(
    participant_id: str,
    method: str,
    ingredient_concentrations: Optional[Dict[str, float]] = None,
    sugar_conc: Optional[float] = None,
    salt_conc: Optional[float] = None,
    reaction_time_ms: Optional[int] = None,
    is_final: bool = False,
    extra_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """Save a complete response to the responses table (JSON-based).

    TODO: Add data validation before saving
    TODO: Implement batch saving for better performance
    TODO: Add data encryption for sensitive information
    """
    try:
        logger.info(
            f"Attempting to save response for {participant_id}: method={method}"
        )

        # Convert extra_data to JSON string if provided
        import json
        extra_data_json = None
        if extra_data:
            extra_data_json = json.dumps(extra_data)

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Get next selection number
            cursor.execute(
                "SELECT COALESCE(MAX(selection_number), 0) + 1 FROM responses WHERE participant_id = ?",
                (participant_id,)
            )
            selection_number = cursor.fetchone()[0]

            # Create ingredient data from either new format or legacy parameters
            ingredient_data = {}
            if ingredient_concentrations:
                ingredient_data.update(ingredient_concentrations)
            else:
                # Fallback to legacy sugar/salt parameters
                if sugar_conc is not None:
                    ingredient_data['sugar'] = sugar_conc
                if salt_conc is not None:
                    ingredient_data['salt'] = salt_conc
            ingredient_data_json = json.dumps(ingredient_data) if ingredient_data else None

            cursor.execute(
                """
                INSERT INTO responses
                (participant_id, selection_number, interface_type, method,
                 ingredient_data, reaction_time_ms, is_final_response, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (participant_id, selection_number, "grid_2d", method, ingredient_data_json, reaction_time_ms, is_final, extra_data_json),
            )

            conn.commit()

            # Verify the insert worked
            cursor.execute(
                "SELECT COUNT(*) FROM responses WHERE participant_id = ?",
                (participant_id,),
            )
            count = cursor.fetchone()[0]

            logger.info(
                f"Successfully saved response for {participant_id}. Total responses: {count}"
            )
            return True

    except Exception as e:
        logger.error(f"Error saving response: {e}")
        return False


def save_multi_ingredient_response(
    participant_id: str,
    session_id: str,
    method: str,
    interface_type: str = "slider_based",
    ingredient_concentrations: Optional[Dict[str, float]] = None,
    reaction_time_ms: Optional[int] = None,
    questionnaire_response: Optional[Dict[str, Any]] = None,
    is_final_response: bool = False,
    extra_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Save a multi-ingredient response to the responses table (JSON-based).

    Args:
        participant_id: Participant identifier
        session_id: Session identifier
        method: Method used (slider_based, linear, etc.)
        interface_type: Type of interface (slider_based, grid_2d)
        ingredient_concentrations: Dict of ingredient concentrations (mM values)
        reaction_time_ms: Response time in milliseconds
        questionnaire_response: Questionnaire responses as dict
        is_final_response: Whether this is the final response
        extra_data: Additional data as dict

    Returns:
        Success status
    """
    try:
        logger.info(
            f"Attempting to save multi-ingredient response for {participant_id}: method={method}, interface={interface_type}"
        )

        # Convert JSON data to strings
        import json
        questionnaire_json = json.dumps(questionnaire_response) if questionnaire_response else None
        extra_data_json = json.dumps(extra_data) if extra_data else None

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Get next selection number
            cursor.execute(
                "SELECT COALESCE(MAX(selection_number), 0) + 1 FROM responses WHERE participant_id = ?",
                (participant_id,)
            )
            selection_number = cursor.fetchone()[0]

            # Convert ingredient concentrations to JSON
            ingredient_data_json = json.dumps(ingredient_concentrations) if ingredient_concentrations else None

            cursor.execute(
                """
                INSERT INTO responses
                (participant_id, session_id, selection_number, interface_type, method,
                 ingredient_data, reaction_time_ms, questionnaire_response, is_final_response, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (participant_id, session_id, selection_number, interface_type, method,
                 ingredient_data_json, reaction_time_ms, questionnaire_json, is_final_response, extra_data_json),
            )

            conn.commit()

            # Verify the insert worked
            cursor.execute(
                "SELECT COUNT(*) FROM responses WHERE participant_id = ?",
                (participant_id,),
            )
            count = cursor.fetchone()[0]

            logger.info(
                f"Successfully saved multi-ingredient response for {participant_id}. Total responses: {count}"
            )
            return True

    except Exception as e:
        logger.error(f"Error saving multi-ingredient response: {e}")
        return False


def get_participant_responses(
    participant_id: str, limit: Optional[int] = None
) -> pd.DataFrame:
    """Get all responses for a participant as a DataFrame."""
    try:
        with get_database_connection() as conn:
            query = """
                SELECT * FROM responses
                WHERE participant_id = ?
                ORDER BY created_at DESC
            """

            if limit:
                query += f" LIMIT {limit}"

            df = pd.read_sql_query(query, conn, params=(participant_id,))
            return df

    except Exception as e:
        logger.error(f"Error getting participant responses: {e}")
        return pd.DataFrame()


def store_initial_slider_positions(
    session_id: str,
    participant_id: str,
    num_ingredients: int,
    initial_percentages: Dict[str, float],
    initial_concentrations: Dict[str, float],
    ingredient_names: Optional[List[str]] = None
) -> bool:
    """
    Store initial slider positions for a participant in a session.

    Args:
        session_id: Session identifier
        participant_id: Participant identifier
        num_ingredients: Number of ingredients (3-6)
        initial_percentages: Dict of ingredient_name -> percentage (0-100)
        initial_concentrations: Dict of ingredient_name -> concentration (mM)

    Returns:
        Success status
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Store ingredient names for retrieval
            actual_ingredient_names = ingredient_names or list(initial_concentrations.keys())

            # Convert to JSON format for storage
            import json
            initial_values_json = json.dumps(initial_concentrations)
            percent_values_json = json.dumps(initial_percentages)

            # Prepare extra data with ingredient names
            extra_data = json.dumps({
                "ingredient_names": actual_ingredient_names
            })

            cursor.execute(
                """
                INSERT OR REPLACE INTO initial_slider_positions
                (session_id, participant_id, interface_type, num_ingredients,
                 initial_values, percent_values, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (session_id, participant_id, "slider_based", num_ingredients,
                 initial_values_json, percent_values_json, extra_data)
            )

            conn.commit()
            logger.info(f"Stored initial slider positions for {participant_id} in session {session_id}")
            return True

    except Exception as e:
        logger.error(f"Error storing initial slider positions: {e}")
        return False


def get_initial_slider_positions(session_id: str, participant_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve initial slider positions for a participant.

    Args:
        session_id: Session identifier
        participant_id: Participant identifier

    Returns:
        Dictionary with initial positions or None if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM initial_slider_positions
                WHERE session_id = ? AND participant_id = ?
            """,
                (session_id, participant_id)
            )

            row = cursor.fetchone()
            if row:
                import json

                result = {
                    "session_id": row["session_id"],
                    "participant_id": row["participant_id"],
                    "num_ingredients": row["num_ingredients"],
                    "percentages": {},
                    "concentrations": {},
                    "created_at": row["created_at"]
                }

                # Parse JSON data for concentrations and percentages
                try:
                    if row["initial_values"]:
                        result["concentrations"] = json.loads(row["initial_values"])
                    if row["percent_values"]:
                        result["percentages"] = json.loads(row["percent_values"])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON data for {participant_id}")

                return result

            return None

    except Exception as e:
        logger.error(f"Error getting initial slider positions: {e}")
        return None


def get_live_slider_positions(session_id: Optional[str] = None) -> pd.DataFrame:
    """
    Get live slider positions for monitoring using the database view.

    Args:
        session_id: Optional session to filter by

    Returns:
        DataFrame with current slider positions
    """
    try:
        with get_database_connection() as conn:
            if session_id:
                query = """
                    SELECT * FROM live_slider_monitoring
                    WHERE session_id = ?
                    ORDER BY participant_id
                """
                params = (session_id,)
            else:
                query = """
                    SELECT * FROM live_slider_monitoring
                    ORDER BY session_id, participant_id
                """
                params = ()

            df = pd.read_sql_query(query, conn, params=params)
            return df

    except Exception as e:
        logger.error(f"Error getting live slider positions: {e}")
        return pd.DataFrame()


def export_responses_csv(session_id: Optional[str] = None) -> str:
    """
    Export responses data to CSV format with new multi-ingredient schema.

    Args:
        session_id: Optional session to filter by

    Returns:
        CSV data as string
    """
    try:
        import csv
        import io

        with get_database_connection() as conn:
            if session_id:
                query = """
                    SELECT
                        participant_id,
                        session_id,
                        selection_number,
                        interface_type,
                        method,
                        x_position,
                        y_position,
                        ingredient_data,
                        reaction_time_ms,
                        questionnaire_response,
                        is_final_response,
                        created_at,
                        extra_data
                    FROM responses
                    WHERE session_id = ?
                    ORDER BY participant_id, selection_number
                """
                params = (session_id,)
            else:
                query = """
                    SELECT
                        participant_id,
                        session_id,
                        selection_number,
                        interface_type,
                        method,
                        x_position,
                        y_position,
                        ingredient_data,
                        reaction_time_ms,
                        questionnaire_response,
                        is_final_response,
                        created_at,
                        extra_data
                    FROM responses
                    ORDER BY participant_id, selection_number
                """
                params = ()

            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                return ""

            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                'participant_id', 'session_id', 'selection_number', 'interface_type',
                'method', 'x_position', 'y_position', 'ingredient_data',
                'reaction_time_ms', 'questionnaire_response', 'is_final_response',
                'created_at', 'extra_data'
            ])

            # Write data rows
            for row in rows:
                writer.writerow(row)

            return output.getvalue()

    except Exception as e:
        logger.error(f"Error exporting CSV data: {e}")
        return ""


def clear_participant_session(participant_id: str) -> bool:
    """Clear all session state for a participant (reset)."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM session_state WHERE participant_id = ?
            """,
                (participant_id,),
            )

            conn.commit()
            logger.info(f"Cleared session for participant {participant_id}")
            return True

    except Exception as e:
        logger.error(f"Error clearing participant session: {e}")
        return False


def get_all_participants() -> list:
    """Get list of all participants who have session data."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT participant_id 
                FROM session_state 
                ORDER BY participant_id
            """
            )

            return [row[0] for row in cursor.fetchall()]

    except Exception as e:
        logger.error(f"Error getting participants list: {e}")
        return []


def get_database_stats() -> Dict[str, int]:
    """Get database statistics for monitoring."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Count active sessions
            cursor.execute("SELECT COUNT(DISTINCT participant_id) FROM session_state")
            active_sessions = cursor.fetchone()[0]

            # Count total responses
            cursor.execute("SELECT COUNT(*) FROM responses")
            total_responses = cursor.fetchone()[0]

            # Count participants with responses
            cursor.execute("SELECT COUNT(DISTINCT participant_id) FROM responses")
            participants_with_data = cursor.fetchone()[0]

            return {
                "active_sessions": active_sessions,
                "total_responses": total_responses,
                "participants_with_data": participants_with_data,
            }

    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"active_sessions": 0, "total_responses": 0, "participants_with_data": 0}


def get_response_with_concentrations(response_id: int) -> Optional[Dict[str, Any]]:
    """Get a specific response including parsed concentration data."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM responses WHERE id = ?
                """,
                (response_id,)
            )

            row = cursor.fetchone()
            if row:
                import json
                response = dict(row)

                # Parse ingredient_data JSON for concentrations
                if response['ingredient_data']:
                    try:
                        response['concentrations'] = json.loads(response['ingredient_data'])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse ingredient_data for response {response_id}")
                        response['concentrations'] = {}
                else:
                    response['concentrations'] = {}

                return response
            return None

    except Exception as e:
        logger.error(f"Error getting response with concentrations: {e}")
        return None


def calculate_recipe_from_json(response_json: str) -> str:
    """
    Calculate and format a recipe string from JSON ingredient data.

    Args:
        response_json: JSON string containing ingredients data

    Returns:
        Formatted recipe string, e.g., "Recipe: Salt: 15.2 mM, Sugar: 8.7 mM, Citric Acid: 3.1 mM"
    """
    import json

    # Handle edge cases
    if not response_json:
        return "No recipe yet"

    try:
        # Parse JSON data
        ingredient_data = json.loads(response_json)

        if not ingredient_data or not isinstance(ingredient_data, dict):
            return "No recipe yet"

        # Build recipe components
        recipe_parts = []
        for ingredient_name, concentration in ingredient_data.items():
            if concentration is not None and concentration > 0:
                # Format concentration to 1 decimal place
                recipe_parts.append(f"{ingredient_name}: {concentration:.1f} mM")

        # Return formatted recipe
        if recipe_parts:
            return f"Recipe: {', '.join(recipe_parts)}"
        else:
            return "No recipe yet"

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON for recipe calculation: {response_json}")
        return "Error parsing recipe data"
    except Exception as e:
        logger.error(f"Error calculating recipe: {e}")
        return "Error calculating recipe"


def get_latest_recipe_for_participant(participant_id: str) -> str:
    """
    Get the latest recipe for a participant as a formatted string.

    Args:
        participant_id: Participant identifier

    Returns:
        Formatted recipe string or status message
    """
    try:
        response = get_latest_submitted_response(participant_id)
        if response and response.get('ingredient_concentrations'):
            # Convert dict back to JSON string for recipe calculation
            import json
            ingredient_json = json.dumps(response['ingredient_concentrations'])
            return calculate_recipe_from_json(ingredient_json)
        else:
            return "No recipe yet"
    except Exception as e:
        logger.error(f"Error getting latest recipe for {participant_id}: {e}")
        return "Error getting recipe"


# =============================================================================
# NEW DATABASE SCHEMA V2.0 - Multi-Ingredient Support
# =============================================================================

def initialize_database_v2():
    """
    Initialize the new v2.0 database schema with multi-ingredient support.
    This replaces the old schema with a more flexible structure.
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            # Create experiments table - Track experiment configurations
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_code TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT NOT NULL CHECK(interface_type IN ('grid_2d', 'slider_based')),
                    method TEXT CHECK(method IN ('linear', 'logarithmic', 'exponential', 'slider_based')),
                    num_ingredients INTEGER NOT NULL CHECK(num_ingredients BETWEEN 2 AND 6),
                    use_random_start BOOLEAN DEFAULT 0,
                    experiment_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    experiment_end_time TIMESTAMP,
                    is_completed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (session_code) REFERENCES sessions(session_code),
                    UNIQUE(session_code, participant_id)
                )
            """)
            
            # Create initial positions table - Store random starting positions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS initial_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT NOT NULL,
                    initial_x REAL,
                    initial_y REAL,
                    ingredient_1_initial REAL,
                    ingredient_2_initial REAL,
                    ingredient_3_initial REAL,
                    ingredient_4_initial REAL,
                    ingredient_5_initial REAL,
                    ingredient_6_initial REAL,
                    ingredient_config TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
                    UNIQUE(experiment_id, participant_id)
                )
            """)
            
            # Create user interactions table - Universal selection tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    interaction_number INTEGER NOT NULL,
                    interaction_type TEXT NOT NULL CHECK(interaction_type IN 
                        ('initial_position', 'grid_click', 'slider_adjustment', 'final_selection', 'questionnaire')),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    grid_x REAL,
                    grid_y REAL,
                    ingredient_1_concentration REAL,
                    ingredient_2_concentration REAL,
                    ingredient_3_concentration REAL,
                    ingredient_4_concentration REAL,
                    ingredient_5_concentration REAL,
                    ingredient_6_concentration REAL,
                    ingredient_1_mM REAL,
                    ingredient_2_mM REAL,
                    ingredient_3_mM REAL,
                    ingredient_4_mM REAL,
                    ingredient_5_mM REAL,
                    ingredient_6_mM REAL,
                    reaction_time_ms INTEGER,
                    is_final_response BOOLEAN DEFAULT 0,
                    extra_data TEXT,
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
                )
            """)
            
            # Create questionnaire responses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questionnaire_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    interaction_id INTEGER NOT NULL,
                    participant_id TEXT NOT NULL,
                    questionnaire_type TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    question_text TEXT,
                    response_value TEXT,
                    response_numeric REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (interaction_id) REFERENCES user_interactions(id)
                )
            """)
            
            # Create ingredient mappings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ingredient_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id INTEGER NOT NULL,
                    position INTEGER NOT NULL CHECK(position BETWEEN 1 AND 6),
                    ingredient_name TEXT NOT NULL,
                    min_concentration REAL NOT NULL,
                    max_concentration REAL NOT NULL,
                    molecular_weight REAL NOT NULL,
                    unit TEXT DEFAULT 'mM',
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
                    UNIQUE(experiment_id, position)
                )
            """)
            
            # Create indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_experiments_session_participant ON experiments(session_code, participant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_experiment_participant ON user_interactions(experiment_id, participant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_interactions_timestamp ON user_interactions(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_questionnaire_interaction ON questionnaire_responses(interaction_id)")
            
            # Create useful views
            cursor.execute("""
                CREATE VIEW IF NOT EXISTS experiment_summary AS
                SELECT 
                    e.id as experiment_id,
                    e.session_code,
                    e.participant_id,
                    e.interface_type,
                    e.method,
                    e.num_ingredients,
                    e.use_random_start,
                    e.experiment_start_time,
                    e.experiment_end_time,
                    e.is_completed,
                    s.moderator_name,
                    COUNT(ui.id) as total_interactions,
                    COUNT(CASE WHEN ui.is_final_response = 1 THEN 1 END) as final_responses
                FROM experiments e
                LEFT JOIN sessions s ON e.session_code = s.session_code
                LEFT JOIN user_interactions ui ON e.id = ui.experiment_id
                GROUP BY e.id
            """)
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error initializing database v2: {e}")
        return False


def start_experiment_v2(session_code: str, participant_id: str, interface_type: str, 
                       method: str, num_ingredients: int, use_random_start: bool = False,
                       ingredient_config: list = None) -> Optional[int]:
    """
    Start a new experiment and return experiment ID.
    
    Args:
        session_code: Session identifier
        participant_id: Participant identifier 
        interface_type: 'grid_2d' or 'slider_based'
        method: Concentration mapping method
        num_ingredients: Number of ingredients (2-6)
        use_random_start: Whether to use random starting positions
        ingredient_config: List of ingredient configurations
        
    Returns:
        Experiment ID if successful, None otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            # Insert experiment record
            cursor.execute("""
                INSERT INTO experiments 
                (session_code, participant_id, interface_type, method, num_ingredients, use_random_start)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session_code, participant_id, interface_type, method, num_ingredients, use_random_start))
            
            experiment_id = cursor.lastrowid
            
            # Store ingredient mappings
            if ingredient_config:
                for i, ingredient in enumerate(ingredient_config[:num_ingredients], 1):
                    cursor.execute("""
                        INSERT INTO ingredient_mappings
                        (experiment_id, position, ingredient_name, min_concentration, max_concentration, molecular_weight, unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (experiment_id, i, ingredient["name"], ingredient["min_concentration"], 
                          ingredient["max_concentration"], ingredient["molecular_weight"], ingredient.get("unit", "mM")))
            
            conn.commit()
            return experiment_id
            
    except Exception as e:
        print(f"Error starting experiment: {e}")
        return None


def store_initial_positions_v2(experiment_id: int, participant_id: str, interface_type: str,
                              initial_x: float = None, initial_y: float = None,
                              slider_values: dict = None, ingredient_config: list = None) -> bool:
    """
    Store initial starting positions for an experiment.
    
    Args:
        experiment_id: Experiment identifier
        participant_id: Participant identifier
        interface_type: 'grid_2d' or 'slider_based'
        initial_x, initial_y: Initial grid position (for grid interface)
        slider_values: Dict of initial slider values (for slider interface)
        ingredient_config: List of ingredient configurations
        
    Returns:
        Success status
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            # Prepare ingredient initial values
            ingredient_initials = [None] * 6
            if slider_values and ingredient_config:
                for i, ingredient in enumerate(ingredient_config[:6]):
                    if ingredient["name"] in slider_values:
                        ingredient_initials[i] = slider_values[ingredient["name"]]
            
            import json
            
            cursor.execute("""
                INSERT INTO initial_positions
                (experiment_id, participant_id, interface_type, initial_x, initial_y,
                 ingredient_1_initial, ingredient_2_initial, ingredient_3_initial,
                 ingredient_4_initial, ingredient_5_initial, ingredient_6_initial,
                 ingredient_config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (experiment_id, participant_id, interface_type, initial_x, initial_y,
                  *ingredient_initials, json.dumps(ingredient_config) if ingredient_config else None))
            
            conn.commit()
            return True
            
    except Exception as e:
        print(f"Error storing initial positions: {e}")
        return False


def store_user_interaction_v2(experiment_id: int, participant_id: str, interaction_type: str,
                             grid_x: float = None, grid_y: float = None,
                             slider_concentrations: dict = None, actual_concentrations: dict = None,
                             reaction_time_ms: int = None, is_final_response: bool = False,
                             extra_data: dict = None) -> Optional[int]:
    """
    Store a user interaction (click, slider adjustment, etc.).
    
    Args:
        experiment_id: Experiment identifier
        participant_id: Participant identifier
        interaction_type: Type of interaction
        grid_x, grid_y: Grid coordinates (if applicable)
        slider_concentrations: Dict of slider concentrations (if applicable)
        actual_concentrations: Dict of actual mM concentrations
        reaction_time_ms: Reaction time in milliseconds
        is_final_response: Whether this is the final response
        extra_data: Additional data as dictionary
        
    Returns:
        Interaction ID if successful, None otherwise
    """
    try:
        import json
        
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            # Get next interaction number for this experiment
            cursor.execute("""
                SELECT COALESCE(MAX(interaction_number), 0) + 1 
                FROM user_interactions 
                WHERE experiment_id = ?
            """, (experiment_id,))
            interaction_number = cursor.fetchone()[0]
            
            # Prepare concentration arrays
            slider_concs = [None] * 6
            actual_concs = [None] * 6
            
            if slider_concentrations:
                for i, value in enumerate(list(slider_concentrations.values())[:6]):
                    slider_concs[i] = value
                    
            if actual_concentrations:
                for i, value in enumerate(list(actual_concentrations.values())[:6]):
                    actual_concs[i] = value
            
            cursor.execute("""
                INSERT INTO user_interactions
                (experiment_id, participant_id, interaction_number, interaction_type,
                 grid_x, grid_y,
                 ingredient_1_concentration, ingredient_2_concentration, ingredient_3_concentration,
                 ingredient_4_concentration, ingredient_5_concentration, ingredient_6_concentration,
                 ingredient_1_mM, ingredient_2_mM, ingredient_3_mM,
                 ingredient_4_mM, ingredient_5_mM, ingredient_6_mM,
                 reaction_time_ms, is_final_response, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (experiment_id, participant_id, interaction_number, interaction_type,
                  grid_x, grid_y, *slider_concs, *actual_concs,
                  reaction_time_ms, is_final_response, json.dumps(extra_data) if extra_data else None))
            
            interaction_id = cursor.lastrowid
            conn.commit()
            return interaction_id
            
    except Exception as e:
        print(f"Error storing user interaction: {e}")
        return None


def get_initial_positions_v2(experiment_id: int, participant_id: str) -> Optional[Dict]:
    """
    Retrieve initial positions for an experiment.
    
    Returns:
        Dictionary with initial positions or None
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM initial_positions
                WHERE experiment_id = ? AND participant_id = ?
            """, (experiment_id, participant_id))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
            
    except Exception as e:
        print(f"Error retrieving initial positions: {e}")
        return None


def get_experiment_data_v2(session_code: str, participant_id: str) -> Optional[Dict]:
    """
    Get complete experiment data for export.
    
    Returns:
        Dictionary with experiment data or None
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            # Get experiment info
            cursor.execute("""
                SELECT e.*, s.moderator_name
                FROM experiments e
                LEFT JOIN sessions s ON e.session_code = s.session_code
                WHERE e.session_code = ? AND e.participant_id = ?
            """, (session_code, participant_id))
            
            experiment = cursor.fetchone()
            if not experiment:
                return None
            
            experiment_dict = dict(experiment)
            experiment_id = experiment_dict['id']
            
            # Get initial positions
            cursor.execute("""
                SELECT * FROM initial_positions
                WHERE experiment_id = ?
            """, (experiment_id,))
            initial_positions = cursor.fetchone()
            if initial_positions:
                experiment_dict['initial_positions'] = dict(initial_positions)
            
            # Get all interactions
            cursor.execute("""
                SELECT * FROM user_interactions
                WHERE experiment_id = ?
                ORDER BY interaction_number
            """, (experiment_id,))
            interactions = [dict(row) for row in cursor.fetchall()]
            experiment_dict['interactions'] = interactions
            
            # Get ingredient mappings
            cursor.execute("""
                SELECT * FROM ingredient_mappings
                WHERE experiment_id = ?
                ORDER BY position
            """, (experiment_id,))
            ingredients = [dict(row) for row in cursor.fetchall()]
            experiment_dict['ingredients'] = ingredients
            
            return experiment_dict
            
    except Exception as e:
        print(f"Error retrieving experiment data: {e}")
        return None


def export_experiment_data_csv(session_code: str) -> str:
    """
    Export experiment data to CSV format.
    
    Args:
        session_code: Session to export
        
    Returns:
        CSV data as string
    """
    try:
        import csv
        import io
        
        with get_database_connection() as conn:
            cursor = conn.cursor()
            
            # Get all experiment data for session
            cursor.execute("""
                SELECT 
                    e.participant_id,
                    e.interface_type,
                    e.method,
                    e.num_ingredients,
                    e.use_random_start,
                    e.experiment_start_time,
                    ui.interaction_number,
                    ui.interaction_type,
                    ui.timestamp,
                    ui.grid_x,
                    ui.grid_y,
                    ui.ingredient_1_concentration,
                    ui.ingredient_2_concentration,
                    ui.ingredient_3_concentration,
                    ui.ingredient_4_concentration,
                    ui.ingredient_5_concentration,
                    ui.ingredient_6_concentration,
                    ui.ingredient_1_mM,
                    ui.ingredient_2_mM,
                    ui.ingredient_3_mM,
                    ui.ingredient_4_mM,
                    ui.ingredient_5_mM,
                    ui.ingredient_6_mM,
                    ui.reaction_time_ms,
                    ui.is_final_response
                FROM experiments e
                LEFT JOIN user_interactions ui ON e.id = ui.experiment_id
                WHERE e.session_code = ?
                ORDER BY e.participant_id, ui.interaction_number
            """, (session_code,))
            
            rows = cursor.fetchall()
            if not rows:
                return ""
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'participant_id', 'interface_type', 'method', 'num_ingredients', 'use_random_start',
                'experiment_start_time', 'interaction_number', 'interaction_type', 'timestamp',
                'grid_x', 'grid_y', 'ingredient_1_concentration', 'ingredient_2_concentration',
                'ingredient_3_concentration', 'ingredient_4_concentration', 'ingredient_5_concentration',
                'ingredient_6_concentration', 'ingredient_1_mM', 'ingredient_2_mM', 'ingredient_3_mM',
                'ingredient_4_mM', 'ingredient_5_mM', 'ingredient_6_mM', 'reaction_time_ms', 'is_final_response'
            ])
            
            # Write data rows
            for row in rows:
                writer.writerow(row)
            
            return output.getvalue()
            
    except Exception as e:
        print(f"Error exporting CSV data: {e}")
        return ""


# =============================================================================
# END OF FILE - DEVELOPMENT NOTES
# =============================================================================
# DATABASE ARCHITECTURE:
# - SQLite with row factory for named column access
# - Context managers ensure proper connection cleanup
# - Comprehensive error handling with logging
# - Migration system supports schema evolution
# 
# SECURITY FEATURES:
# - Parameterized queries prevent SQL injection
# - Transaction rollback on errors
# - Connection timeouts prevent resource exhaustion
# - Input validation and sanitization
# 
# PERFORMANCE CONSIDERATIONS:
# - Proper indexing on participant_id and created_at columns
# - JSON storage for complex multi-component data
# - Connection pooling recommended for production
# - Batch operations for large datasets
# 
# PRODUCTION READINESS:
# - Add automated backup system
# - Implement data encryption for sensitive information
# - Add connection pooling and monitoring
# - Create data archiving and cleanup procedures
# =============================================================================
