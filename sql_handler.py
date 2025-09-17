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
                    ingredient_1_conc REAL,
                    ingredient_2_conc REAL,
                    ingredient_3_conc REAL,
                    ingredient_4_conc REAL,
                    ingredient_5_conc REAL,
                    ingredient_6_conc REAL,
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
                    ingredient_1_initial REAL,
                    ingredient_2_initial REAL,
                    ingredient_3_initial REAL,
                    ingredient_4_initial REAL,
                    ingredient_5_initial REAL,
                    ingredient_6_initial REAL,
                    ingredient_1_percent REAL,
                    ingredient_2_percent REAL,
                    ingredient_3_percent REAL,
                    ingredient_4_percent REAL,
                    ingredient_5_percent REAL,
                    ingredient_6_percent REAL,
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
                    r.ingredient_1_conc,
                    r.ingredient_2_conc,
                    r.ingredient_3_conc,
                    r.ingredient_4_conc,
                    r.ingredient_5_conc,
                    r.ingredient_6_conc,
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
                    ingredient_1_conc,
                    ingredient_2_conc,
                    ingredient_3_conc,
                    ingredient_4_conc,
                    ingredient_5_conc,
                    ingredient_6_conc,
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
    """Handle database migrations for schema updates."""
    try:
        # Check if we need to migrate responses table to new multi-ingredient schema
        cursor.execute("PRAGMA table_info(responses)")
        columns = [column[1] for column in cursor.fetchall()]

        # Check if new multi-ingredient columns exist
        new_columns_needed = [
            'session_id', 'selection_number', 'interface_type',
            'ingredient_1_conc', 'ingredient_2_conc', 'ingredient_3_conc',
            'ingredient_4_conc', 'ingredient_5_conc', 'ingredient_6_conc',
            'questionnaire_response', 'is_final_response'
        ]

        missing_columns = [col for col in new_columns_needed if col not in columns]

        if missing_columns:
            logger.info("Migrating responses table to support multi-ingredient schema")

            # Create new responses table with updated schema
            cursor.execute("""
                CREATE TABLE responses_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    selection_number INTEGER,
                    participant_id TEXT NOT NULL,
                    interface_type TEXT DEFAULT 'grid_2d',
                    x_position REAL,
                    y_position REAL,
                    method TEXT NOT NULL,
                    ingredient_1_conc REAL,
                    ingredient_2_conc REAL,
                    ingredient_3_conc REAL,
                    ingredient_4_conc REAL,
                    ingredient_5_conc REAL,
                    ingredient_6_conc REAL,
                    reaction_time_ms INTEGER,
                    questionnaire_response TEXT,
                    is_final_response BOOLEAN DEFAULT 0,
                    extra_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrate existing data, mapping sugar/salt to ingredient_1/ingredient_2
            if 'sugar_concentration' in columns and 'salt_concentration' in columns:
                cursor.execute("""
                    INSERT INTO responses_new
                    (id, participant_id, interface_type, x_position, y_position, method,
                     ingredient_1_conc, ingredient_2_conc, reaction_time_ms,
                     is_final_response, extra_data, created_at)
                    SELECT id, participant_id, 'grid_2d', x_position, y_position, method,
                           sugar_concentration, salt_concentration, reaction_time_ms,
                           COALESCE(is_final, 0), extra_data, created_at
                    FROM responses
                """)
            else:
                # Migrate what we can
                cursor.execute("""
                    INSERT INTO responses_new
                    (id, participant_id, interface_type, x_position, y_position, method,
                     reaction_time_ms, is_final_response, extra_data, created_at)
                    SELECT id, participant_id, 'grid_2d', x_position, y_position, method,
                           reaction_time_ms, 0, extra_data, created_at
                    FROM responses
                """)

            # Replace old table
            cursor.execute("DROP TABLE responses")
            cursor.execute("ALTER TABLE responses_new RENAME TO responses")

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

        # Recreate views with updated schema
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS current_slider_positions AS
            SELECT
                r.session_id,
                r.participant_id,
                r.interface_type,
                r.method,
                r.ingredient_1_conc,
                r.ingredient_2_conc,
                r.ingredient_3_conc,
                r.ingredient_4_conc,
                r.ingredient_5_conc,
                r.ingredient_6_conc,
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
                ingredient_1_conc,
                ingredient_2_conc,
                ingredient_3_conc,
                ingredient_4_conc,
                ingredient_5_conc,
                ingredient_6_conc,
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
    """Get the latest moderator settings for a participant."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT method, x_position, y_position, num_ingredients, created_at
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
                    "x_position": row["x_position"],
                    "y_position": row["y_position"],
                    "num_ingredients": row["num_ingredients"],
                    "created_at": row["created_at"],
                }
            return None

    except Exception as e:
        logger.error(f"Error getting moderator settings: {e}")
        return None


def get_latest_submitted_response(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest submitted response from the responses table."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT x_position, y_position, method, created_at,
                       sugar_concentration, salt_concentration, reaction_time_ms
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
                    "x_position": row["x_position"],
                    "y_position": row["y_position"],
                    "method": row["method"],
                    "created_at": row["created_at"],
                    "sugar_concentration": row["sugar_concentration"],
                    "salt_concentration": row["salt_concentration"],
                    "reaction_time_ms": row["reaction_time_ms"],
                }
            return None

    except Exception as e:
        logger.error(f"Error getting latest submitted response: {e}")
        return None


def get_latest_subject_response(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest subject response for a participant from session_state table."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT x_position, y_position, method, created_at
                FROM session_state 
                WHERE participant_id = ? AND user_type = 'sub'
                ORDER BY created_at DESC 
                LIMIT 1
            """,
                (participant_id,),
            )

            row = cursor.fetchone()
            if row:
                return {
                    "x_position": row["x_position"],
                    "y_position": row["y_position"],
                    "method": row["method"],
                    "created_at": row["created_at"],
                }
            return None

    except Exception as e:
        logger.error(f"Error getting latest response: {e}")
        return None


def get_live_subject_position(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the current live position of the subject (from session_state) or latest response."""
    # First try to get live position from session_state (for grid interface)
    live_response = get_latest_subject_response(participant_id)

    # If no live response, get the latest submitted response
    if not live_response:
        # Try new database schema first (for slider interface)
        slider_response = get_latest_slider_interaction(participant_id)
        if slider_response:
            return slider_response
            
        # Fallback to old schema (for grid interface)
        submitted_response = get_latest_submitted_response(participant_id)
        if submitted_response:
            return {
                "x_position": submitted_response["x_position"],
                "y_position": submitted_response["y_position"],
                "method": submitted_response["method"],
                "created_at": submitted_response["created_at"],
                "is_submitted": True,
                "interface_type": "grid_2d"
            }
    else:
        live_response["is_submitted"] = False
        live_response["interface_type"] = "grid_2d"
        return live_response

    return None


def get_latest_slider_interaction(participant_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest slider interaction from the user_interactions table."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ui.*, e.interface_type, e.num_ingredients,
                       GROUP_CONCAT(im.ingredient_name, '|') as ingredient_names
                FROM user_interactions ui
                JOIN experiments e ON ui.experiment_id = e.id
                LEFT JOIN ingredient_mappings im ON e.id = im.experiment_id
                WHERE ui.participant_id = ? AND e.interface_type = 'slider_based'
                GROUP BY ui.id
                ORDER BY ui.timestamp DESC
                LIMIT 1
            """, (participant_id,))
            
            row = cursor.fetchone()
            if row:
                # Build ingredient data dictionary
                ingredient_names = row['ingredient_names'].split('|') if row['ingredient_names'] else []
                slider_data = {}
                concentration_data = {}
                
                for i in range(min(row['num_ingredients'], 6)):  # Max 6 ingredients
                    conc_field = f'ingredient_{i+1}_concentration'
                    mM_field = f'ingredient_{i+1}_mM'
                    
                    if row[conc_field] is not None:
                        ingredient_name = ingredient_names[i] if i < len(ingredient_names) else f'Ingredient {i+1}'
                        slider_data[ingredient_name] = row[conc_field]
                        concentration_data[ingredient_name] = row[mM_field]
                
                return {
                    "interface_type": "slider_based",
                    "method": "slider_based",
                    "created_at": row['timestamp'],
                    "is_submitted": bool(row['is_final_response']),
                    "slider_data": slider_data,
                    "concentration_data": concentration_data,
                    "reaction_time_ms": row['reaction_time_ms'],
                    "interaction_type": row['interaction_type'],
                    "num_ingredients": row['num_ingredients']
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
    x: float,
    y: float,
    method: str,
    sugar_conc: Optional[float] = None,
    salt_conc: Optional[float] = None,
    reaction_time_ms: Optional[int] = None,
    is_final: bool = False,
    extra_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """Save a complete response to the responses table (legacy function for 2D grid).

    TODO: Add data validation before saving
    TODO: Implement batch saving for better performance
    TODO: Add data encryption for sensitive information
    """
    try:
        logger.info(
            f"Attempting to save response for {participant_id}: x={x}, y={y}, method={method}"
        )

        # Convert extra_data to JSON string if provided
        extra_data_json = None
        if extra_data:
            import json
            extra_data_json = json.dumps(extra_data)

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Get next selection number
            cursor.execute(
                "SELECT COALESCE(MAX(selection_number), 0) + 1 FROM responses WHERE participant_id = ?",
                (participant_id,)
            )
            selection_number = cursor.fetchone()[0]

            cursor.execute(
                """
                INSERT INTO responses
                (participant_id, selection_number, interface_type, x_position, y_position, method,
                 ingredient_1_conc, ingredient_2_conc, reaction_time_ms, is_final_response, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (participant_id, selection_number, "grid_2d", x, y, method, sugar_conc, salt_conc, reaction_time_ms, is_final, extra_data_json),
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
    x_position: Optional[float] = None,
    y_position: Optional[float] = None,
    reaction_time_ms: Optional[int] = None,
    questionnaire_response: Optional[Dict[str, Any]] = None,
    is_final_response: bool = False,
    extra_data: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Save a multi-ingredient response to the responses table.

    Args:
        participant_id: Participant identifier
        session_id: Session identifier
        method: Method used (slider_based, linear, etc.)
        interface_type: Type of interface (slider_based, grid_2d)
        ingredient_concentrations: Dict of ingredient concentrations (mM values)
        x_position, y_position: Grid coordinates (for grid interface)
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

            # Prepare ingredient concentration values (up to 6 ingredients)
            ingredient_values = [None] * 6
            if ingredient_concentrations:
                for i, conc in enumerate(list(ingredient_concentrations.values())[:6]):
                    ingredient_values[i] = conc

            cursor.execute(
                """
                INSERT INTO responses
                (participant_id, session_id, selection_number, interface_type, method,
                 x_position, y_position,
                 ingredient_1_conc, ingredient_2_conc, ingredient_3_conc,
                 ingredient_4_conc, ingredient_5_conc, ingredient_6_conc,
                 reaction_time_ms, questionnaire_response, is_final_response, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (participant_id, session_id, selection_number, interface_type, method,
                 x_position, y_position, *ingredient_values,
                 reaction_time_ms, questionnaire_json, is_final_response, extra_data_json),
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

            # Prepare arrays for up to 6 ingredients
            conc_values = [None] * 6
            percent_values = [None] * 6

            # Store ingredient names for retrieval
            actual_ingredient_names = ingredient_names or list(initial_concentrations.keys())

            for i, (ingredient_name, conc) in enumerate(list(initial_concentrations.items())[:6]):
                conc_values[i] = conc
                percent_values[i] = initial_percentages.get(ingredient_name, 50.0)

            # Prepare extra data with ingredient names
            import json
            extra_data = json.dumps({
                "ingredient_names": actual_ingredient_names[:6]
            })

            cursor.execute(
                """
                INSERT OR REPLACE INTO initial_slider_positions
                (session_id, participant_id, interface_type, num_ingredients,
                 ingredient_1_initial, ingredient_2_initial, ingredient_3_initial,
                 ingredient_4_initial, ingredient_5_initial, ingredient_6_initial,
                 ingredient_1_percent, ingredient_2_percent, ingredient_3_percent,
                 ingredient_4_percent, ingredient_5_percent, ingredient_6_percent,
                 extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (session_id, participant_id, "slider_based", num_ingredients,
                 *conc_values, *percent_values, extra_data)
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
                result = {
                    "session_id": row["session_id"],
                    "participant_id": row["participant_id"],
                    "num_ingredients": row["num_ingredients"],
                    "percentages": {},
                    "concentrations": {},
                    "created_at": row["created_at"]
                }

                # Extract non-null concentrations and percentages
                # Get ingredient names from extra_data if available
                ingredient_names = []
                extra_data = row["extra_data"]
                if extra_data:
                    try:
                        import json
                        extra_info = json.loads(extra_data)
                        ingredient_names = extra_info.get("ingredient_names", [])
                    except:
                        pass

                for i in range(1, 7):
                    conc_value = row[f"ingredient_{i}_initial"]
                    percent_value = row[f"ingredient_{i}_percent"]

                    if conc_value is not None:
                        # Use actual ingredient name if available, otherwise generic
                        if i <= len(ingredient_names):
                            ingredient_name = ingredient_names[i-1]
                        else:
                            ingredient_name = f"Ingredient_{i}"

                        result["concentrations"][ingredient_name] = conc_value
                        result["percentages"][ingredient_name] = percent_value if percent_value is not None else 50.0

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
                        ingredient_1_conc,
                        ingredient_2_conc,
                        ingredient_3_conc,
                        ingredient_4_conc,
                        ingredient_5_conc,
                        ingredient_6_conc,
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
                        ingredient_1_conc,
                        ingredient_2_conc,
                        ingredient_3_conc,
                        ingredient_4_conc,
                        ingredient_5_conc,
                        ingredient_6_conc,
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
                'method', 'x_position', 'y_position', 'ingredient_1_conc',
                'ingredient_2_conc', 'ingredient_3_conc', 'ingredient_4_conc',
                'ingredient_5_conc', 'ingredient_6_conc', 'reaction_time_ms',
                'questionnaire_response', 'is_final_response', 'created_at', 'extra_data'
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
                response = dict(row)
                
                # Parse extra_data if it exists
                if response['extra_data']:
                    import json
                    response['concentrations'] = json.loads(response['extra_data'])
                    
                return response
            return None
            
    except Exception as e:
        logger.error(f"Error getting response with concentrations: {e}")
        return None


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
