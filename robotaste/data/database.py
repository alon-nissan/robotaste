"""
RoboTaste Database Layer - Pure SQL Operations

Handles all database interactions with SQLite.
This is the REFACTORED version with:
- All raw SQL operations
- No UI dependencies (no Streamlit)
- Clean separation from business logic

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import sqlite3
import pandas as pd
import json
import uuid
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Tuple, Dict, Any, List
import logging
import os

# Configuration
DB_PATH = "robotaste.db"

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# Section 1: Database Connection & Initialization
# ============================================================================


@contextmanager
def get_database_connection():
    """
    Context manager for database connections with automatic cleanup.

    Yields:
        sqlite3.Connection with row_factory set for dict-like access
    """
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
    """
    Initialize database from robotaste/data/schema.sql file.

    Returns:
        True if successful, False otherwise
    """
    try:
        # Try to find schema file in multiple locations
        schema_paths = [
            "robotaste/data/schema.sql",  # New package location
            "robotaste_schema.sql",  # Old location (backward compat)
            os.path.join(os.path.dirname(__file__), "schema.sql"),  # Relative to this file
        ]

        schema_sql = None
        for path in schema_paths:
            if os.path.exists(path):
                with open(path, "r") as f:
                    schema_sql = f.read()
                logger.info(f"Found schema file at: {path}")
                break

        if not schema_sql:
            raise FileNotFoundError(
                f"schema.sql not found in expected locations: {schema_paths}"
            )

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Execute schema (CREATE TABLE IF NOT EXISTS)
            cursor.executescript(schema_sql)

            conn.commit()
            logger.info("Database initialized successfully from schema.sql")
            return True

    except FileNotFoundError as e:
        logger.error(str(e))
        return False
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


# ============================================================================
# Section 2: Session Management
# ============================================================================


def generate_session_code() -> str:
    """
    Generate a unique 6-character alphanumeric session code.
    Uses uppercase letters and digits (A-Z, 0-9) for 36^6 = 2.2 billion combinations.

    Returns:
        6-character session code (e.g., "A3X9K2")
    """
    import random
    import string

    # Use uppercase letters and digits only (more readable than mixed case)
    chars = string.ascii_uppercase + string.digits
    max_attempts = 100

    for attempt in range(max_attempts):
        # Generate random 6-character code
        code = "".join(random.choices(chars, k=6))

        # Check if code already exists in database
        try:
            with get_database_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT session_code FROM sessions WHERE session_code = ?", (code,)
                )
                if cursor.fetchone() is None:
                    # Code is unique
                    return code
        except Exception as e:
            logger.error(f"Error checking session code uniqueness: {e}")
            raise

    # If we couldn't find a unique code after max_attempts, raise error
    raise RuntimeError(
        f"Failed to generate unique session code after {max_attempts} attempts"
    )


def create_session(
    moderator_name: str, protocol_id: Optional[str] = None
) -> Tuple[str, str]:
    """
    Create new session with optional protocol.

    Args:
        moderator_name: Name of the moderator (not stored in DB)
        protocol_id: Optional protocol ID to link to the session.

    Returns:
        Tuple of (session_id (UUID string), session_code (6-char string))
    """
    session_id = str(uuid.uuid4())
    session_code = generate_session_code()

    with get_database_connection() as conn:
        cursor = conn.cursor()
        # Insert session with both identifiers and optional protocol_id
        cursor.execute(
            """
            INSERT INTO sessions (
                session_id, session_code, protocol_id, state
            ) VALUES (?, ?, ?, 'active')
        """,
            (session_id, session_code, protocol_id),
        )
        conn.commit()
        if protocol_id:
            logger.info(f"Created session {session_id} with code {session_code} using protocol {protocol_id}")
        else:
            logger.info(f"Created session {session_id} with code {session_code}")
        return session_id, session_code


def get_session(session_id: str) -> Optional[Dict]:
    """
    Get complete session configuration with parsed JSON fields.

    Args:
        session_id: Session UUID

    Returns:
        Dict with session data including parsed JSON fields, or None if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    s.session_id, s.session_code, s.user_id, s.ingredients, s.question_type_id,
                    s.state, s.current_phase, s.current_cycle, s.experiment_config,
                    s.created_at, s.updated_at,
                    qt.name as questionnaire_name, qt.data as questionnaire_data
                FROM sessions s
                LEFT JOIN questionnaire_types qt ON s.question_type_id = qt.id
                WHERE s.session_id = ?
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Parse JSON fields
            return {
                "session_id": row["session_id"],
                "session_code": row["session_code"],
                "user_id": row["user_id"],
                "ingredients": (
                    json.loads(row["ingredients"]) if row["ingredients"] else []
                ),
                "question_type_id": row["question_type_id"],
                "questionnaire_name": row["questionnaire_name"],
                "questionnaire_data": (
                    json.loads(row["questionnaire_data"])
                    if row["questionnaire_data"]
                    else None
                ),
                "state": row["state"],
                "current_phase": row["current_phase"],
                "experiment_config": (
                    json.loads(row["experiment_config"])
                    if row["experiment_config"]
                    else {}
                ),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        return None


def get_session_by_code(session_code: str) -> Optional[Dict]:
    """
    Get complete session configuration by 6-character session code.

    Args:
        session_code: 6-character session code (e.g., "A3X9K2")

    Returns:
        Dict with session data (same structure as get_session()), or None if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    s.session_id, s.session_code, s.user_id, s.ingredients, s.question_type_id,
                    s.state, s.current_phase, s.current_cycle, s.experiment_config,
                    s.created_at, s.updated_at,
                    qt.name as questionnaire_name, qt.data as questionnaire_data
                FROM sessions s
                LEFT JOIN questionnaire_types qt ON s.question_type_id = qt.id
                WHERE s.session_code = ?
            """,
                (session_code,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Parse JSON fields (same structure as get_session())
            return {
                "session_id": row["session_id"],
                "session_code": row["session_code"],
                "user_id": row["user_id"],
                "ingredients": (
                    json.loads(row["ingredients"]) if row["ingredients"] else []
                ),
                "question_type_id": row["question_type_id"],
                "questionnaire_name": row["questionnaire_name"],
                "questionnaire_data": (
                    json.loads(row["questionnaire_data"])
                    if row["questionnaire_data"]
                    else None
                ),
                "state": row["state"],
                "current_phase": row["current_phase"],
                "experiment_config": (
                    json.loads(row["experiment_config"])
                    if row["experiment_config"]
                    else {}
                ),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    except Exception as e:
        logger.error(f"Failed to get session by code {session_code}: {e}")
        return None


def update_session_state(session_id: str, state: str) -> bool:
    """
    Update session state.

    Args:
        session_id: Session UUID
        state: New state ('active', 'completed', 'cancelled')

    Returns:
        True if successful, False otherwise
    """
    if state not in ("active", "completed", "cancelled"):
        logger.error(f"Invalid state: {state}")
        return False

    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """,
                (state, session_id),
            )
            conn.commit()

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Updated session {session_id} state to '{state}'")
            return success

    except Exception as e:
        logger.error(f"Failed to update session state: {e}")
        return False


def update_current_phase(session_id: str, phase: str) -> bool:
    """
    Update current phase for multi-device synchronization.

    Args:
        session_id: Session UUID
        phase: New phase (waiting, robot_preparing, loading, questionnaire, selection, complete)

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET current_phase = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """,
                (phase, session_id),
            )
            conn.commit()

            success = cursor.rowcount > 0
            if success:
                logger.info(f"Updated session {session_id} current_phase to '{phase}'")
            return success

    except Exception as e:
        logger.error(f"Failed to update current phase: {e}")
        return False


def get_current_cycle(session_id: str) -> int:
    """
    Get current cycle number from experiment_config.

    Args:
        session_id: Session UUID

    Returns:
        Current cycle number (0 if not found)
    """
    session = get_session(session_id)
    if session:
        return session["experiment_config"].get("current_cycle", 0)
    return 0


def increment_cycle(session_id: str) -> int:
    """
    Increment cycle in experiment_config and return new value.

    Args:
        session_id: Session UUID

    Returns:
        New cycle number (0 if failed)
    """
    try:
        session = get_session(session_id)
        if not session:
            return 0

        config = session["experiment_config"]
        config["current_cycle"] = config.get("current_cycle", 0) + 1

        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE sessions
                SET experiment_config = ?, current_cycle = ?, updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """,
                (json.dumps(config), config["current_cycle"], session_id),
            )
            conn.commit()

        new_cycle = config["current_cycle"]
        logger.info(f"Incremented session {session_id} to cycle {new_cycle}")
        return new_cycle

    except Exception as e:
        logger.error(f"Failed to increment cycle: {e}")
        return 0


def create_minimal_session(session_id: str) -> bool:
    """
    Create a minimal session record in database with just session_id and state.

    Args:
        session_id: Session UUID

    Returns:
        True if successful, False otherwise
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Insert minimal session
            cursor.execute(
                """
                INSERT INTO sessions (session_id, state)
                VALUES (?, 'active')
            """,
                (session_id,),
            )

            conn.commit()

        logger.info(f"Created minimal session {session_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to create minimal session: {e}")
        return False


def get_sessions_by_protocol(protocol_id: str) -> List[Dict]:
    """
    Get all sessions using a specific protocol.

    Args:
        protocol_id: Protocol UUID

    Returns:
        List of session dictionaries
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    s.session_id, s.session_code, s.user_id, s.ingredients, s.question_type_id,
                    s.state, s.current_phase, s.current_cycle, s.experiment_config,
                    s.created_at, s.updated_at,
                    qt.name as questionnaire_name, qt.data as questionnaire_data
                FROM sessions s
                LEFT JOIN questionnaire_types qt ON s.question_type_id = qt.id
                WHERE s.protocol_id = ?
                ORDER BY s.created_at DESC
            """,
                (protocol_id,),
            )

            sessions = []
            for row in cursor.fetchall():
                sessions.append(
                    {
                        "session_id": row["session_id"],
                        "session_code": row["session_code"],
                        "user_id": row["user_id"],
                        "ingredients": (
                            json.loads(row["ingredients"]) if row["ingredients"] else []
                        ),
                        "question_type_id": row["question_type_id"],
                        "questionnaire_name": row["questionnaire_name"],
                        "questionnaire_data": (
                            json.loads(row["questionnaire_data"])
                            if row["questionnaire_data"]
                            else None
                        ),
                        "state": row["state"],
                        "current_phase": row["current_phase"],
                        "experiment_config": (
                            json.loads(row["experiment_config"])
                            if row["experiment_config"]
                            else {}
                        ),
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }
                )

            logger.info(f"Retrieved {len(sessions)} sessions for protocol {protocol_id}")
            return sessions

    except Exception as e:
        logger.error(f"Failed to get sessions by protocol: {e}")
        return []


def update_session_with_config(
    session_id: str,
    user_id: str,
    num_ingredients: int,
    interface_type: str,
    method: str,
    ingredients: List[Dict],
    question_type_id: int,
    bo_config: Dict,
    experiment_config: Dict,
) -> bool:
    """
    Update existing session with full configuration.

    Called when moderator finishes configuration and clicks "Start Trial".

    Args:
        session_id: Session UUID (already generated)
        user_id: Participant/user ID
        num_ingredients: Number of ingredients
        interface_type: 'grid_2d' or 'slider_based'
        method: Mapping method ('linear', 'logarithmic', 'exponential')
        ingredients: List of ingredient dicts
        question_type_id: ID of questionnaire type
        bo_config: Bayesian optimization configuration dict
        experiment_config: Full experiment configuration dict

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Updating session {session_id} with full configuration")

        # Build complete config
        full_config = {
            **experiment_config,
            "num_ingredients": num_ingredients,
            "interface_type": interface_type,
            "method": method,
            "current_cycle": 0,
            "created_at": datetime.now().isoformat(),
        }

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Check if session exists, if not create it
            cursor.execute(
                "SELECT session_id FROM sessions WHERE session_id = ?", (session_id,)
            )
            if not cursor.fetchone():
                logger.info(f"Session {session_id} doesn't exist, creating it first")
                session_code = generate_session_code()
                cursor.execute(
                    """
                    INSERT INTO sessions (session_id, session_code, state, current_phase)
                    VALUES (?, ?, 'active', 'waiting')
                """,
                    (session_id, session_code),
                )

            # Update session with full config
            cursor.execute(
                """
                UPDATE sessions
                SET user_id = ?,
                    ingredients = ?,
                    question_type_id = ?,
                    experiment_config = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """,
                (
                    user_id,
                    json.dumps(ingredients),
                    question_type_id,
                    json.dumps(full_config),
                    session_id,
                ),
            )

            # Insert or replace BO configuration
            stopping_criteria = bo_config.get("stopping_criteria", {})

            cursor.execute(
                """
                INSERT OR REPLACE INTO bo_configuration (
                    session_id, enabled, min_samples_for_bo,
                    acquisition_function, ei_xi, ucb_kappa,
                    adaptive_acquisition, exploration_budget,
                    xi_exploration, xi_exploitation,
                    kappa_exploration, kappa_exploitation,
                    kernel_nu, length_scale_initial, length_scale_bounds,
                    constant_kernel_bounds, alpha, n_restarts_optimizer,
                    normalize_y, random_state, only_final_responses,
                    convergence_enabled, min_cycles_1d, max_cycles_1d,
                    min_cycles_2d, max_cycles_2d, ei_threshold, ucb_threshold,
                    stability_window, stability_threshold, consecutive_required, stopping_mode
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id,
                    1 if bo_config.get("enabled", True) else 0,
                    bo_config.get("min_samples_for_bo", 3),
                    bo_config.get("acquisition_function", "ei"),
                    bo_config.get("ei_xi", 0.01),
                    bo_config.get("ucb_kappa", 2.0),
                    # Adaptive acquisition parameters
                    1 if bo_config.get("adaptive_acquisition", True) else 0,
                    bo_config.get("exploration_budget", 0.25),
                    bo_config.get("xi_exploration", 0.1),
                    bo_config.get("xi_exploitation", 0.01),
                    bo_config.get("kappa_exploration", 3.0),
                    bo_config.get("kappa_exploitation", 1.0),
                    # GP kernel parameters
                    bo_config.get("kernel_nu", 2.5),
                    bo_config.get("length_scale_initial", 1.0),
                    json.dumps(bo_config.get("length_scale_bounds", [0.1, 10.0])),
                    json.dumps(bo_config.get("constant_kernel_bounds", [0.001, 1000.0])),
                    bo_config.get("alpha", 0.001),
                    bo_config.get("n_restarts_optimizer", 10),
                    1 if bo_config.get("normalize_y", True) else 0,
                    bo_config.get("random_state", 42),
                    1 if bo_config.get("only_final_responses", True) else 0,
                    # Stopping criteria
                    1 if stopping_criteria.get("enabled", True) else 0,
                    stopping_criteria.get("min_cycles_1d", 10),
                    stopping_criteria.get("max_cycles_1d", 30),
                    stopping_criteria.get("min_cycles_2d", 15),
                    stopping_criteria.get("max_cycles_2d", 50),
                    stopping_criteria.get("ei_threshold", 0.001),
                    stopping_criteria.get("ucb_threshold", 0.01),
                    stopping_criteria.get("stability_window", 5),
                    stopping_criteria.get("stability_threshold", 0.05),
                    stopping_criteria.get("consecutive_required", 2),
                    stopping_criteria.get("stopping_mode", "suggest_auto"),
                ),
            )

            conn.commit()

        logger.info(f"Updated session {session_id} with full configuration")
        return True

    except Exception as e:
        logger.error(f"Failed to update session: {e}")
        import traceback

        logger.error(f"Full traceback: {traceback.format_exc()}")
        return False


# ============================================================================
# Section 3: User Management
# ============================================================================


def create_user(user_id: str) -> bool:
    """
    Create user (taste tester) if doesn't exist.

    Args:
        user_id: Unique user identifier

    Returns:
        True if created or already exists, False on error
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO users (id)
                VALUES (?)
            """,
                (user_id,),
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Created user {user_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        return False


def get_user(user_id: str) -> Optional[Dict]:
    """
    Get user info.

    Args:
        user_id: User identifier

    Returns:
        Dict with user data or None if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    except Exception as e:
        logger.error(f"Failed to get user {user_id}: {e}")
        return None


def update_user_profile(user_id: str, name: str, gender: str, age: int) -> bool:
    """Updates user profile with demographic data."""
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET name = ?, gender = ?, age = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (name, gender, age, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Failed to update profile: {e}")
        return False


# ============================================================================
# Section 4: Sample/Cycle Operations
# ============================================================================


def save_sample_cycle(
    session_id: str,
    cycle_number: int,
    ingredient_concentration: Dict[str, float],
    selection_data: Dict,
    questionnaire_answer: Dict,
    is_final: bool = False,
    selection_mode: str = "user_selected",
    was_bo_overridden: bool = False,
) -> str:
    """
    Save complete cycle data in ONE row.

    Combines: solution tasted + questionnaire + selection for next.

    Args:
        session_id: Session UUID
        cycle_number: Current cycle (1, 2, 3, ...)
        ingredient_concentration: What they tasted
        selection_data: Their selection for next cycle
        questionnaire_answer: Their questionnaire responses
        is_final: True if last cycle in session
        selection_mode: Mode used for this sample ("user_selected", "bo_selected", "predetermined")
        was_bo_overridden: True if user overrode BO suggestion in bo_selected mode

    Returns:
        sample_id (UUID)
    """
    try:
        sample_id = str(uuid.uuid4())

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Extract BO acquisition parameters from selection_data if available
            acquisition_function = None
            acquisition_xi = None
            acquisition_kappa = None
            acquisition_value = None
            predicted_value = None
            uncertainty = None

            if selection_data and isinstance(selection_data, dict):
                acquisition_function = selection_data.get("acquisition_function")

                acquisition_params = selection_data.get("acquisition_params", {})
                if isinstance(acquisition_params, dict):
                    acquisition_xi = acquisition_params.get("xi")
                    acquisition_kappa = acquisition_params.get("kappa")

                acquisition_value = selection_data.get("acquisition_value")
                predicted_value = selection_data.get("predicted_value")
                uncertainty = selection_data.get("uncertainty")

            cursor.execute(
                """
                INSERT INTO samples (
                    sample_id, session_id, cycle_number,
                    ingredient_concentration, selection_data,
                    questionnaire_answer, is_final,
                    selection_mode, was_bo_overridden,
                    acquisition_function, acquisition_xi, acquisition_kappa,
                    acquisition_value, predicted_value, uncertainty
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    sample_id,
                    session_id,
                    cycle_number,
                    json.dumps(ingredient_concentration),
                    json.dumps(selection_data) if selection_data else None,
                    json.dumps(questionnaire_answer),
                    1 if is_final else 0,
                    selection_mode,
                    1 if was_bo_overridden else 0,
                    acquisition_function,
                    acquisition_xi,
                    acquisition_kappa,
                    acquisition_value,
                    predicted_value,
                    uncertainty,
                ),
            )

            conn.commit()
            logger.info(
                f"Saved sample {sample_id} for session {session_id}, cycle {cycle_number}, mode={selection_mode}"
            )
            if acquisition_function:
                logger.info(
                    f"  BO parameters: {acquisition_function}, "
                    f"xi={acquisition_xi}, kappa={acquisition_kappa}, "
                    f"predicted={predicted_value}, uncertainty={uncertainty}"
                )
            if was_bo_overridden:
                logger.info(f"  User overrode BO suggestion")
            return sample_id

    except Exception as e:
        logger.error(f"Failed to save sample: {e}")
        raise


def get_sample(sample_id: str) -> Optional[Dict]:
    """
    Get sample by ID with parsed JSON fields.

    Args:
        sample_id: Sample UUID

    Returns:
        Dict with sample data including parsed JSON, or None if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM samples WHERE sample_id = ?", (sample_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "sample_id": row["sample_id"],
                "session_id": row["session_id"],
                "cycle_number": row["cycle_number"],
                "ingredient_concentration": json.loads(row["ingredient_concentration"]),
                "selection_data": (
                    json.loads(row["selection_data"]) if row["selection_data"] else None
                ),
                "questionnaire_answer": json.loads(row["questionnaire_answer"]),
                "is_final": bool(row["is_final"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    except Exception as e:
        logger.error(f"Failed to get sample {sample_id}: {e}")
        return None


def get_session_samples(session_id: str, only_final: bool = False) -> List[Dict]:
    """
    Get all samples for a session, ordered by cycle.

    Args:
        session_id: Session UUID
        only_final: If True, return only samples where is_final=1

    Returns:
        List of sample dicts with parsed JSON fields
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            if only_final:
                cursor.execute(
                    """
                    SELECT * FROM samples
                    WHERE session_id = ? AND is_final = 1
                    ORDER BY cycle_number ASC
                """,
                    (session_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM samples
                    WHERE session_id = ?
                    ORDER BY cycle_number ASC
                """,
                    (session_id,),
                )

            samples = []
            for row in cursor.fetchall():
                samples.append(
                    {
                        "sample_id": row["sample_id"],
                        "session_id": row["session_id"],
                        "cycle_number": row["cycle_number"],
                        "ingredient_concentration": json.loads(
                            row["ingredient_concentration"]
                        ),
                        "selection_data": (
                            json.loads(row["selection_data"])
                            if row["selection_data"]
                            else None
                        ),
                        "questionnaire_answer": json.loads(row["questionnaire_answer"]),
                        "is_final": bool(row["is_final"]),
                        "created_at": row["created_at"],
                    }
                )

            return samples

    except Exception as e:
        logger.error(f"Failed to get session samples: {e}")
        return []


def get_latest_sample_concentrations(session_id: str) -> Optional[Dict[str, float]]:
    """
    Get ingredient concentrations from the most recent sample for live monitoring.

    Args:
        session_id: Session UUID

    Returns:
        Dict of ingredient concentrations or None if no samples exist
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT ingredient_concentration
                FROM samples
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if not row or not row["ingredient_concentration"]:
                return None

            # Parse and return concentrations
            concentrations = json.loads(row["ingredient_concentration"])
            return concentrations

    except Exception as e:
        logger.error(f"Failed to get latest sample concentrations: {e}")
        return None


# ============================================================================
# Section 5: Questionnaire Operations
# ============================================================================


def get_questionnaire_type_id(questionnaire_type_name: str) -> Optional[int]:
    """
    Get questionnaire_type_id from questionnaire_types table.

    Args:
        questionnaire_type_name: Name of questionnaire type (e.g., 'hedonic_continuous')

    Returns:
        Integer ID from questionnaire_types table, or None if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id FROM questionnaire_types
                WHERE name = ?
            """,
                (questionnaire_type_name,),
            )
            row = cursor.fetchone()
            if row:
                return row["id"]
            else:
                logger.warning(
                    f"Questionnaire type '{questionnaire_type_name}' not found in database"
                )
                return None

    except Exception as e:
        logger.error(f"Failed to get questionnaire type ID: {e}")
        return None


# ============================================================================
# Section 6: BO Integration
# ============================================================================


def get_training_data(session_id: str, only_final: bool = False) -> pd.DataFrame:
    """
    Get training data for BO model.

    Returns DataFrame with ingredient concentrations + target values.

    Args:
        session_id: Session UUID
        only_final: If True, use only samples where is_final=1

    Returns:
        DataFrame with columns: [ingredient1, ingredient2, ..., target_value]
    """
    try:
        from robotaste.config.questionnaire import extract_target_variable

        # Get session to know questionnaire type and ingredient order
        session = get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return pd.DataFrame()

        # Get expected ingredient order from experiment config
        experiment_config = session.get("experiment_config", {})
        expected_ingredients = [
            ing["name"] for ing in experiment_config.get("ingredients", [])
        ]

        if not expected_ingredients:
            logger.warning(
                f"No ingredients defined in experiment config for session {session_id}"
            )
            # Fallback: try to extract from first sample
            samples = get_session_samples(session_id, only_final=only_final)
            if samples and samples[0].get("ingredient_concentration"):
                expected_ingredients = list(
                    samples[0]["ingredient_concentration"].keys()
                )
                logger.info(
                    f"Using ingredient order from first sample: {expected_ingredients}"
                )
            else:
                return pd.DataFrame()

        # Get questionnaire type name
        questionnaire_type = session.get("questionnaire_name")
        if not questionnaire_type:
            logger.warning(f"No questionnaire type for session {session_id}")
            return pd.DataFrame()

        # Get target variable name from questionnaire config
        target_column_name = "target_value"  # Default fallback
        questionnaire_config = None
        try:
            from robotaste.config.questionnaire import QUESTIONNAIRE_CONFIGS

            questionnaire_type_normalized = questionnaire_type.strip().lower()
            q_def = QUESTIONNAIRE_CONFIGS.get(questionnaire_type_normalized)
            if not q_def:
                q_def = QUESTIONNAIRE_CONFIGS.get(questionnaire_type)
            if q_def:
                questionnaire_config = q_def  # Store the full config
                bayesian_config = q_def.get("bayesian_target", {})
                target_key = bayesian_config.get("variable")
                if target_key:
                    target_column_name = target_key
                    logger.info(f"Using target column name: '{target_column_name}'")
        except Exception as e:
            logger.warning(
                f"Could not get target variable name from config: {e}, using default 'target_value'"
            )

        # Get samples
        samples = get_session_samples(session_id, only_final=only_final)
        if not samples:
            logger.info(f"No samples found for session {session_id}")
            return pd.DataFrame()

        # Fallback questionnaire config if not found
        if not questionnaire_config:
            logger.warning(f"Using fallback questionnaire config for type: {questionnaire_type}")
            questionnaire_config = {
                "bayesian_target": {
                    "variable": "overall_liking",
                    "higher_is_better": True,
                    "expected_range": [1, 9]
                }
            }

        # Build training data with ORDERED columns matching experiment config
        data = []
        for sample in samples:
            # Get concentrations
            concentrations = sample["ingredient_concentration"]

            # Extract target value
            target = extract_target_variable(
                sample["questionnaire_answer"], questionnaire_config
            )

            if target is not None:
                # Build row with ingredients in experiment config order
                row = {}
                for ing_name in expected_ingredients:
                    if ing_name in concentrations:
                        row[ing_name] = concentrations[ing_name]
                    else:
                        logger.warning(
                            f"Missing ingredient {ing_name} in sample {sample.get('sample_id', 'unknown')}"
                        )
                        row[ing_name] = 0.0  # Fallback to zero if missing

                row[target_column_name] = target
                data.append(row)

        df = pd.DataFrame(data)

        # Verify column order matches expected (sanity check)
        expected_cols = expected_ingredients + [target_column_name]
        if not df.empty and list(df.columns) != expected_cols:
            logger.warning(
                f"Column order mismatch! Expected {expected_cols}, got {list(df.columns)}"
            )
            # Reorder columns to match expectation
            df = df[expected_cols]

        logger.info(
            f"Retrieved {len(df)} training samples for session {session_id} with columns: {list(df.columns)}"
        )
        return df

    except Exception as e:
        logger.error(f"Failed to get training data: {e}")
        return pd.DataFrame()


def get_bo_config(session_id: str) -> Dict:
    """
    Get BO configuration for session.

    Args:
        session_id: Session UUID

    Returns:
        Dict with BO config, or empty dict if not found
    """
    try:
        with get_database_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM bo_configuration WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()

            if not row:
                logger.warning(f"No BO config found for session {session_id}")
                return {}

            return {
                "enabled": bool(row["enabled"]),
                "min_samples_for_bo": row["min_samples_for_bo"],
                "acquisition_function": row["acquisition_function"],
                "ei_xi": row["ei_xi"],
                "ucb_kappa": row["ucb_kappa"],
                "adaptive_acquisition": bool(row["adaptive_acquisition"]),
                "exploration_budget": row["exploration_budget"],
                "xi_exploration": row["xi_exploration"],
                "xi_exploitation": row["xi_exploitation"],
                "kappa_exploration": row["kappa_exploration"],
                "kappa_exploitation": row["kappa_exploitation"],
                "kernel_nu": row["kernel_nu"],
                "length_scale_initial": row["length_scale_initial"],
                "length_scale_bounds": json.loads(row["length_scale_bounds"]),
                "constant_kernel_bounds": json.loads(row["constant_kernel_bounds"]),
                "alpha": row["alpha"],
                "n_restarts_optimizer": row["n_restarts_optimizer"],
                "normalize_y": bool(row["normalize_y"]),
                "random_state": row["random_state"],
                "only_final_responses": bool(row["only_final_responses"]),
                # Stopping criteria
                "stopping_criteria": {
                    "enabled": bool(row["convergence_enabled"]),
                    "min_cycles_1d": row["min_cycles_1d"],
                    "max_cycles_1d": row["max_cycles_1d"],
                    "min_cycles_2d": row["min_cycles_2d"],
                    "max_cycles_2d": row["max_cycles_2d"],
                    "ei_threshold": row["ei_threshold"],
                    "ucb_threshold": row["ucb_threshold"],
                    "stability_window": row["stability_window"],
                    "stability_threshold": row["stability_threshold"],
                    "consecutive_required": row["consecutive_required"],
                    "stopping_mode": row["stopping_mode"],
                },
            }

    except Exception as e:
        logger.error(f"Failed to get BO config: {e}")
        return {}


# ============================================================================
# Section 7: Export & Utilities
# ============================================================================


def export_session_csv(session_id: str) -> str:
    """
    Export session data to CSV string.

    Flattens all JSON fields into columns for easy analysis.

    Args:
        session_id: Session UUID

    Returns:
        CSV string with all session data
    """
    try:
        samples = get_session_samples(session_id)
        if not samples:
            logger.warning(f"No samples to export for session {session_id}")
            return ""

        session = get_session(session_id)

        # Flatten data for CSV
        rows = []
        for sample in samples:
            row = {
                "session_id": session_id,
                "cycle_number": sample["cycle_number"],
                "is_final": sample["is_final"],
                "created_at": sample["created_at"],
                # Unpack concentrations
                **{
                    f"concentration_{k}": v
                    for k, v in sample["ingredient_concentration"].items()
                },
                # Unpack selection data
                **{
                    f"selection_{k}": v
                    for k, v in (sample["selection_data"] or {}).items()
                },
                # Unpack questionnaire
                **{f"q_{k}": v for k, v in sample["questionnaire_answer"].items()},
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        csv_string = df.to_csv(index=False)
        logger.info(f"Exported {len(df)} rows for session {session_id}")
        return csv_string

    except Exception as e:
        logger.error(f"Failed to export CSV: {e}")
        return ""


def get_session_stats(session_id: str) -> Dict:
    """
    Get session statistics.

    Args:
        session_id: Session UUID

    Returns:
        Dict with statistics
    """
    try:
        samples = get_session_samples(session_id)
        if not samples:
            return {
                "total_cycles": 0,
                "is_completed": False,
                "created_at": None,
                "last_cycle_at": None,
            }

        return {
            "total_cycles": len(samples),
            "is_completed": any(s["is_final"] for s in samples),
            "created_at": samples[0]["created_at"] if samples else None,
            "last_cycle_at": samples[-1]["created_at"] if samples else None,
        }

    except Exception as e:
        logger.error(f"Failed to get session stats: {e}")
        return {}
