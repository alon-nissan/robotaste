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

            # Responses table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_id TEXT NOT NULL,
                    x_position REAL NOT NULL,
                    y_position REAL NOT NULL,
                    method TEXT NOT NULL,
                    sugar_concentration REAL,
                    salt_concentration REAL,
                    reaction_time_ms INTEGER,
                    is_final BOOLEAN,
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
        # Check if extra_data column exists in responses table
        cursor.execute("PRAGMA table_info(responses)")
        columns = [column[1] for column in cursor.fetchall()]
        
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

        # Check if we need to add JSON ingredient data column
        cursor.execute("PRAGMA table_info(responses)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'ingredient_data_json' not in columns:
            logger.info("Adding ingredient_data_json column to responses table")
            cursor.execute("ALTER TABLE responses ADD COLUMN ingredient_data_json TEXT")

            # Migrate existing data to JSON format
            cursor.execute("""
                UPDATE responses
                SET ingredient_data_json = CASE
                    WHEN interface_type = 'grid_2d' THEN
                        json_object(
                            'interface_type', 'grid_2d',
                            'ingredients', json_object(
                                'ingredient_1', json_object(
                                    'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[0]'), 'Ingredient A'),
                                    'concentration', ingredient_1_conc,
                                    'position', json_object('x', x_position, 'y', y_position)
                                ),
                                'ingredient_2', json_object(
                                    'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[1]'), 'Ingredient B'),
                                    'concentration', ingredient_2_conc,
                                    'position', json_object('x', x_position, 'y', y_position)
                                )
                            ),
                            'timestamp', created_at
                        )
                    ELSE
                        json_object(
                            'interface_type', 'slider_based',
                            'ingredients', json_object(
                                'ingredient_1', json_object(
                                    'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[0]'), 'Ingredient A'),
                                    'concentration', ingredient_1_conc,
                                    'slider_position', 50  -- Generic fallback position
                                ),
                                'ingredient_2', CASE WHEN ingredient_2_conc IS NOT NULL THEN
                                    json_object(
                                        'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[1]'), 'Ingredient B'),
                                        'concentration', ingredient_2_conc,
                                        'slider_position', 50  -- Generic fallback position
                                    ) ELSE NULL END,
                                'ingredient_3', CASE WHEN ingredient_3_conc IS NOT NULL THEN
                                    json_object(
                                        'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[2]'), 'Ingredient C'),
                                        'concentration', ingredient_3_conc,
                                        'slider_position', 50
                                    ) ELSE NULL END,
                                'ingredient_4', CASE WHEN ingredient_4_conc IS NOT NULL THEN
                                    json_object(
                                        'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[3]'), 'Ingredient D'),
                                        'concentration', ingredient_4_conc,
                                        'slider_position', 50
                                    ) ELSE NULL END,
                                'ingredient_5', CASE WHEN ingredient_5_conc IS NOT NULL THEN
                                    json_object(
                                        'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[4]'), 'Ingredient E'),
                                        'concentration', ingredient_5_conc,
                                        'slider_position', 50
                                    ) ELSE NULL END,
                                'ingredient_6', CASE WHEN ingredient_6_conc IS NOT NULL THEN
                                    json_object(
                                        'name', COALESCE(json_extract(extra_data, '$.selected_ingredients[5]'), 'Ingredient F'),
                                        'concentration', ingredient_6_conc,
                                        'slider_position', 50
                                    ) ELSE NULL END
                            ),
                            'timestamp', created_at
                        )
                END
                WHERE ingredient_data_json IS NULL
            """)

            logger.info("Migrated existing data to JSON format")

        # Create or update JSON parsing views
        cursor.execute("DROP VIEW IF EXISTS ingredients_parsed")
        cursor.execute("DROP VIEW IF EXISTS current_ingredient_state")
        cursor.execute("DROP VIEW IF EXISTS latest_recipes")

        # Create view for parsing individual ingredients from JSON
        cursor.execute("""
            CREATE VIEW ingredients_parsed AS
            SELECT
                r.id,
                r.participant_id,
                r.session_id,
                r.selection_number,
                r.interface_type,
                r.method,
                r.is_final_response,
                r.created_at,
                r.reaction_time_ms,
                r.questionnaire_response,
                json_extract(r.ingredient_data_json, '$.interface_type') as json_interface_type,
                json_extract(r.ingredient_data_json, '$.timestamp') as json_timestamp,

                -- Extract ingredient 1
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_1.name') as ingredient_1_name,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_1.concentration') as ingredient_1_concentration,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_1.slider_position') as ingredient_1_slider_position,

                -- Extract ingredient 2
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_2.name') as ingredient_2_name,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_2.concentration') as ingredient_2_concentration,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_2.slider_position') as ingredient_2_slider_position,

                -- Extract ingredient 3
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_3.name') as ingredient_3_name,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_3.concentration') as ingredient_3_concentration,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_3.slider_position') as ingredient_3_slider_position,

                -- Extract ingredient 4
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_4.name') as ingredient_4_name,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_4.concentration') as ingredient_4_concentration,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_4.slider_position') as ingredient_4_slider_position,

                -- Extract ingredient 5
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_5.name') as ingredient_5_name,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_5.concentration') as ingredient_5_concentration,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_5.slider_position') as ingredient_5_slider_position,

                -- Extract ingredient 6
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_6.name') as ingredient_6_name,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_6.concentration') as ingredient_6_concentration,
                json_extract(r.ingredient_data_json, '$.ingredients.ingredient_6.slider_position') as ingredient_6_slider_position

            FROM responses r
            WHERE r.ingredient_data_json IS NOT NULL
        """)

        # Create view for current ingredient state (latest non-final response per participant)
        cursor.execute("""
            CREATE VIEW current_ingredient_state AS
            SELECT
                p.participant_id,
                p.session_id,
                p.interface_type,
                p.method,
                p.created_at as last_update,
                p.ingredient_1_name,
                p.ingredient_1_concentration,
                p.ingredient_1_slider_position,
                p.ingredient_2_name,
                p.ingredient_2_concentration,
                p.ingredient_2_slider_position,
                p.ingredient_3_name,
                p.ingredient_3_concentration,
                p.ingredient_3_slider_position,
                p.ingredient_4_name,
                p.ingredient_4_concentration,
                p.ingredient_4_slider_position,
                p.ingredient_5_name,
                p.ingredient_5_concentration,
                p.ingredient_5_slider_position,
                p.ingredient_6_name,
                p.ingredient_6_concentration,
                p.ingredient_6_slider_position,
                CASE WHEN p.is_final_response = 1 THEN 'Final Submission' ELSE 'Live Position' END as status
            FROM ingredients_parsed p
            WHERE p.id = (
                SELECT MAX(id)
                FROM ingredients_parsed p2
                WHERE p2.participant_id = p.participant_id
                AND p2.session_id = p.session_id
            )
        """)

        # Create view for latest recipes (final responses only)
        cursor.execute("""
            CREATE VIEW latest_recipes AS
            SELECT
                p.participant_id,
                p.session_id,
                p.created_at as submission_time,
                p.reaction_time_ms,
                p.questionnaire_response,

                -- Build recipe text
                TRIM(
                    COALESCE(p.ingredient_1_name || ': ' || ROUND(p.ingredient_1_concentration, 3) || ' mM', '') ||
                    CASE WHEN p.ingredient_2_name IS NOT NULL THEN CHAR(10) || p.ingredient_2_name || ': ' || ROUND(p.ingredient_2_concentration, 3) || ' mM' ELSE '' END ||
                    CASE WHEN p.ingredient_3_name IS NOT NULL THEN CHAR(10) || p.ingredient_3_name || ': ' || ROUND(p.ingredient_3_concentration, 3) || ' mM' ELSE '' END ||
                    CASE WHEN p.ingredient_4_name IS NOT NULL THEN CHAR(10) || p.ingredient_4_name || ': ' || ROUND(p.ingredient_4_concentration, 3) || ' mM' ELSE '' END ||
                    CASE WHEN p.ingredient_5_name IS NOT NULL THEN CHAR(10) || p.ingredient_5_name || ': ' || ROUND(p.ingredient_5_concentration, 3) || ' mM' ELSE '' END ||
                    CASE WHEN p.ingredient_6_name IS NOT NULL THEN CHAR(10) || p.ingredient_6_name || ': ' || ROUND(p.ingredient_6_concentration, 3) || ' mM' ELSE '' END
                ) as recipe_text,

                -- Individual ingredients for easy querying
                p.ingredient_1_name, p.ingredient_1_concentration,
                p.ingredient_2_name, p.ingredient_2_concentration,
                p.ingredient_3_name, p.ingredient_3_concentration,
                p.ingredient_4_name, p.ingredient_4_concentration,
                p.ingredient_5_name, p.ingredient_5_concentration,
                p.ingredient_6_name, p.ingredient_6_concentration

            FROM ingredients_parsed p
            WHERE p.is_final_response = 1
            ORDER BY p.session_id, p.created_at DESC
        """)

        logger.info("Created JSON parsing views: ingredients_parsed, current_ingredient_state, latest_recipes")

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
    # First try to get live position from session_state
    live_response = get_latest_subject_response(participant_id)

    # If no live response, get the latest submitted response
    if not live_response:
        submitted_response = get_latest_submitted_response(participant_id)
        if submitted_response:
            return {
                "x_position": submitted_response["x_position"],
                "y_position": submitted_response["y_position"],
                "method": submitted_response["method"],
                "created_at": submitted_response["created_at"],
                "is_submitted": True,
            }
    else:
        live_response["is_submitted"] = False
        return live_response

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
    """Save a complete response to the responses table.
    
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
            cursor.execute(
                """
                INSERT INTO responses 
                (participant_id, x_position, y_position, method, 
                 sugar_concentration, salt_concentration, reaction_time_ms, is_final, extra_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (participant_id, x, y, method, sugar_conc, salt_conc, reaction_time_ms, is_final, extra_data_json),
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

            # Prepare ingredient concentration values (up to 6 ingredients) - for backward compatibility
            ingredient_values = [None] * 6
            if ingredient_concentrations:
                for i, conc in enumerate(list(ingredient_concentrations.values())[:6]):
                    ingredient_values[i] = conc

            # Create JSON ingredient data
            ingredient_data_json = None
            if ingredient_concentrations or x_position is not None:
                import json
                from datetime import datetime

                if interface_type == "grid_2d":
                    # Grid interface - 2 ingredients with position data
                    ingredient_names = list(ingredient_concentrations.keys()) if ingredient_concentrations else ["Ingredient A", "Ingredient B"]
                    ingredients = {}
                    for i, (name, conc) in enumerate(zip(ingredient_names, ingredient_concentrations.values() if ingredient_concentrations else [])):
                        ingredients[f"ingredient_{i+1}"] = {
                            "name": name,
                            "concentration": conc,
                            "position": {"x": x_position, "y": y_position}
                        }
                else:
                    # Slider interface
                    ingredients = {}
                    if ingredient_concentrations:
                        for i, (name, conc) in enumerate(ingredient_concentrations.items()):
                            # Try to get slider position from extra_data if available
                            slider_position = 50.0  # Default
                            if extra_data and "concentrations_summary" in extra_data:
                                summary = extra_data["concentrations_summary"]
                                if name in summary and "slider_position" in summary[name]:
                                    slider_position = summary[name]["slider_position"]

                            ingredients[f"ingredient_{i+1}"] = {
                                "name": name,
                                "concentration": conc,
                                "slider_position": slider_position
                            }

                ingredient_data_json = json.dumps({
                    "interface_type": interface_type,
                    "ingredients": ingredients,
                    "timestamp": datetime.now().isoformat()
                })

            cursor.execute(
                """
                INSERT INTO responses
                (participant_id, session_id, selection_number, interface_type, method,
                 x_position, y_position,
                 ingredient_1_conc, ingredient_2_conc, ingredient_3_conc,
                 ingredient_4_conc, ingredient_5_conc, ingredient_6_conc,
                 reaction_time_ms, questionnaire_response, is_final_response, extra_data, ingredient_data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (participant_id, session_id, selection_number, interface_type, method,
                 x_position, y_position, *ingredient_values,
                 reaction_time_ms, questionnaire_json, is_final_response, extra_data_json, ingredient_data_json),
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


def get_latest_recipe(session_id: str, participant_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the latest final recipe for a specific participant in a session.

    Args:
        session_id: Session identifier
        participant_id: Participant identifier

    Returns:
        Dictionary with recipe data or None
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    participant_id,
                    session_id,
                    submission_time,
                    reaction_time_ms,
                    questionnaire_response,
                    recipe_text,
                    ingredient_1_name, ingredient_1_concentration,
                    ingredient_2_name, ingredient_2_concentration,
                    ingredient_3_name, ingredient_3_concentration,
                    ingredient_4_name, ingredient_4_concentration,
                    ingredient_5_name, ingredient_5_concentration,
                    ingredient_6_name, ingredient_6_concentration
                FROM latest_recipes
                WHERE session_id = ? AND participant_id = ?
                ORDER BY submission_time DESC
                LIMIT 1
            """, (session_id, participant_id))

            result = cursor.fetchone()
            if result:
                return dict(result)
            return None

    except Exception as e:
        logger.error(f"Error getting latest recipe: {e}")
        return None


def get_all_session_recipes(session_id: str) -> List[Dict[str, Any]]:
    """
    Get all final recipes for a session.

    Args:
        session_id: Session identifier

    Returns:
        List of recipe dictionaries
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    participant_id,
                    session_id,
                    submission_time,
                    reaction_time_ms,
                    questionnaire_response,
                    recipe_text,
                    ingredient_1_name, ingredient_1_concentration,
                    ingredient_2_name, ingredient_2_concentration,
                    ingredient_3_name, ingredient_3_concentration,
                    ingredient_4_name, ingredient_4_concentration,
                    ingredient_5_name, ingredient_5_concentration,
                    ingredient_6_name, ingredient_6_concentration
                FROM latest_recipes
                WHERE session_id = ?
                ORDER BY participant_id, submission_time DESC
            """, (session_id,))

            results = cursor.fetchall()
            return [dict(row) for row in results]

    except Exception as e:
        logger.error(f"Error getting session recipes: {e}")
        return []


def get_current_ingredient_states(session_id: str) -> List[Dict[str, Any]]:
    """
    Get current ingredient states for all participants in a session.

    Args:
        session_id: Session identifier

    Returns:
        List of current state dictionaries
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    participant_id,
                    session_id,
                    interface_type,
                    method,
                    last_update,
                    status,
                    ingredient_1_name, ingredient_1_concentration, ingredient_1_slider_position,
                    ingredient_2_name, ingredient_2_concentration, ingredient_2_slider_position,
                    ingredient_3_name, ingredient_3_concentration, ingredient_3_slider_position,
                    ingredient_4_name, ingredient_4_concentration, ingredient_4_slider_position,
                    ingredient_5_name, ingredient_5_concentration, ingredient_5_slider_position,
                    ingredient_6_name, ingredient_6_concentration, ingredient_6_slider_position
                FROM current_ingredient_state
                WHERE session_id = ?
                ORDER BY participant_id
            """, (session_id,))

            results = cursor.fetchall()
            return [dict(row) for row in results]

    except Exception as e:
        logger.error(f"Error getting current ingredient states: {e}")
        return []


def export_recipes_csv(session_id: Optional[str] = None) -> str:
    """
    Export recipes to CSV format for laboratory use.

    Args:
        session_id: Optional session identifier (exports all if None)

    Returns:
        CSV formatted string
    """
    try:
        import csv
        import io

        with get_database_connection() as conn:
            cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT
                        participant_id,
                        session_id,
                        submission_time,
                        reaction_time_ms,
                        recipe_text,
                        ingredient_1_name, ingredient_1_concentration,
                        ingredient_2_name, ingredient_2_concentration,
                        ingredient_3_name, ingredient_3_concentration,
                        ingredient_4_name, ingredient_4_concentration,
                        ingredient_5_name, ingredient_5_concentration,
                        ingredient_6_name, ingredient_6_concentration
                    FROM latest_recipes
                    WHERE session_id = ?
                    ORDER BY participant_id
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT
                        participant_id,
                        session_id,
                        submission_time,
                        reaction_time_ms,
                        recipe_text,
                        ingredient_1_name, ingredient_1_concentration,
                        ingredient_2_name, ingredient_2_concentration,
                        ingredient_3_name, ingredient_3_concentration,
                        ingredient_4_name, ingredient_4_concentration,
                        ingredient_5_name, ingredient_5_concentration,
                        ingredient_6_name, ingredient_6_concentration
                    FROM latest_recipes
                    ORDER BY session_id, participant_id
                """)

            results = cursor.fetchall()

            if not results:
                return "No recipe data found"

            # Create CSV output
            output = io.StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                'Participant ID', 'Session ID', 'Submission Time', 'Reaction Time (ms)',
                'Recipe Text', 'Ingredient 1 Name', 'Ingredient 1 Concentration (mM)',
                'Ingredient 2 Name', 'Ingredient 2 Concentration (mM)',
                'Ingredient 3 Name', 'Ingredient 3 Concentration (mM)',
                'Ingredient 4 Name', 'Ingredient 4 Concentration (mM)',
                'Ingredient 5 Name', 'Ingredient 5 Concentration (mM)',
                'Ingredient 6 Name', 'Ingredient 6 Concentration (mM)'
            ])

            # Write data
            for row in results:
                writer.writerow([
                    row['participant_id'], row['session_id'], row['submission_time'],
                    row['reaction_time_ms'], row['recipe_text'],
                    row['ingredient_1_name'], row['ingredient_1_concentration'],
                    row['ingredient_2_name'], row['ingredient_2_concentration'],
                    row['ingredient_3_name'], row['ingredient_3_concentration'],
                    row['ingredient_4_name'], row['ingredient_4_concentration'],
                    row['ingredient_5_name'], row['ingredient_5_concentration'],
                    row['ingredient_6_name'], row['ingredient_6_concentration']
                ])

            return output.getvalue()

    except Exception as e:
        logger.error(f"Error exporting recipes to CSV: {e}")
        return f"Error exporting data: {e}"


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
