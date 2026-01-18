"""
Sample Bank Management for RoboTaste

This module handles randomized sample presentation from a predefined bank,
supporting both pure randomization and Latin square counterbalancing.

Author: RoboTaste Team
Version: 1.0
Created: 2026-01-18
"""

import json
import random
from typing import List, Dict, Any, Optional
from robotaste.data.database import get_database_connection


def generate_randomized_order(
    sample_ids: List[str],
    constraints: Optional[Dict[str, bool]] = None,
    seed: Optional[int] = None
) -> List[str]:
    """
    Generate randomized order with optional constraints.

    Args:
        sample_ids: List of sample IDs to randomize
        constraints: Optional constraints dict with keys:
            - prevent_consecutive_repeats: Prevent same sample appearing consecutively
            - ensure_all_used_before_repeat: Ensure all samples used before repeating
        seed: Optional random seed for reproducibility

    Returns:
        List of sample IDs in randomized order
    """
    if seed is not None:
        random.seed(seed)

    if not constraints:
        constraints = {}

    # Simple shuffle if no constraints
    if not constraints.get("prevent_consecutive_repeats", False):
        shuffled = sample_ids.copy()
        random.shuffle(shuffled)
        return shuffled

    # Shuffle with constraint: prevent consecutive repeats
    # Use swap algorithm to ensure no consecutive duplicates
    shuffled = sample_ids.copy()
    random.shuffle(shuffled)

    # Fix consecutive repeats by swapping
    for i in range(len(shuffled) - 1):
        if shuffled[i] == shuffled[i + 1]:
            # Find a different element to swap with
            for j in range(i + 2, len(shuffled)):
                if shuffled[j] != shuffled[i] and (j == len(shuffled) - 1 or shuffled[j] != shuffled[i + 1]):
                    # Swap
                    shuffled[i + 1], shuffled[j] = shuffled[j], shuffled[i + 1]
                    break

    return shuffled


def generate_latin_square_sequence(
    sample_ids: List[str],
    session_number: int,
    constraints: Optional[Dict[str, bool]] = None
) -> List[str]:
    """
    Generate Latin square sequence for a specific session number.

    Uses cyclic permutation: each session gets a rotated version of the base order.
    - Session 1: ABCD
    - Session 2: BCDA
    - Session 3: CADB
    - Session 4: DABC
    - Session 5: ABCD (wraps around)

    Args:
        sample_ids: List of sample IDs (base order)
        session_number: Session number (1-indexed)
        constraints: Optional constraints (currently not used for Latin square)

    Returns:
        List of sample IDs in Latin square order for this session
    """
    n = len(sample_ids)
    rotation = (session_number - 1) % n

    # Rotate the list
    sequence = sample_ids[rotation:] + sample_ids[:rotation]

    return sequence


def get_next_sample_from_bank(
    session_id: str,
    schedule_index: int,
    sample_bank_config: Dict[str, Any],
    cycle_number: int,
    cycle_range_start: int
) -> Dict[str, float]:
    """
    Get sample from bank for a specific cycle.

    Main entry point called by prepare_cycle_sample(). Handles:
    1. Initializing randomized order on first call (lazy initialization)
    2. Determining Latin square session number
    3. Retrieving sample from sequence based on cycle number

    This function is idempotent - calling it multiple times for the same cycle
    returns the same sample without side effects.

    Args:
        session_id: Current session ID
        schedule_index: Index of schedule entry (0-indexed)
        sample_bank_config: Sample bank configuration from protocol
        cycle_number: Current cycle number (1-indexed)
        cycle_range_start: Start of the cycle range for this schedule entry

    Returns:
        Dict of {ingredient_name: concentration} for this cycle

    Raises:
        ValueError: If sample bank is invalid or empty
    """
    # Extract bank configuration
    samples = sample_bank_config.get("samples", [])
    design_type = sample_bank_config.get("design_type", "randomized")
    constraints = sample_bank_config.get("constraints", {})

    if not samples:
        raise ValueError("Sample bank is empty")

    sample_ids = [s["id"] for s in samples]

    with get_database_connection() as conn:
        cursor = conn.cursor()

        # Check if state exists
        cursor.execute(
            """
            SELECT randomized_order, current_position, latin_square_session_number
            FROM session_sample_bank_state
            WHERE session_id = ? AND protocol_schedule_index = ?
            """,
            (session_id, schedule_index)
        )

        row = cursor.fetchone()

        if row is None:
            # First time - initialize state
            if design_type == "latin_square":
                # Determine session number by counting previous sessions
                session_number = _get_latin_square_session_number(session_id)
                randomized_order = generate_latin_square_sequence(
                    sample_ids, session_number, constraints
                )
            else:  # randomized
                randomized_order = generate_randomized_order(
                    sample_ids, constraints
                )
                session_number = None

            # Store state in database (current_position not used, kept for schema compatibility)
            cursor.execute(
                """
                INSERT INTO session_sample_bank_state
                (session_id, protocol_schedule_index, randomized_order, current_position,
                 latin_square_session_number, design_type, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?, datetime('now'), datetime('now'))
                """,
                (session_id, schedule_index, json.dumps(randomized_order),
                 session_number, design_type)
            )
            conn.commit()
        else:
            # State exists - load it
            randomized_order = json.loads(row[0])

        # Calculate position based on cycle number (idempotent)
        # Position = cycle_number - cycle_range_start
        # This ensures the same cycle always returns the same sample
        position_in_sequence = cycle_number - cycle_range_start

        # Handle wrap-around if needed
        if position_in_sequence >= len(randomized_order):
            position_in_sequence = position_in_sequence % len(randomized_order)

        sample_id = randomized_order[position_in_sequence]

        # Find the sample concentrations
        concentrations = None
        for sample in samples:
            if sample["id"] == sample_id:
                concentrations = sample["concentrations"]
                break

        if concentrations is None:
            raise ValueError(f"Sample ID '{sample_id}' not found in bank")

    return concentrations


def _get_latin_square_session_number(session_id: str) -> int:
    """
    Determine Latin square session number by counting previous sessions.

    Session number is based on how many sessions with the same protocol_id
    have been created before this one.

    Args:
        session_id: Current session ID

    Returns:
        Session number (1-indexed)
    """
    with get_database_connection() as conn:
        cursor = conn.cursor()

        # Get protocol_id and creation time for this session
        cursor.execute(
            """
            SELECT protocol_id, created_at
            FROM sessions
            WHERE session_id = ?
            """,
            (session_id,)
        )

        row = cursor.fetchone()
        if not row:
            return 1  # Default to session 1 if not found

        protocol_id = row[0]
        created_at = row[1]

        # Count sessions with same protocol_id created before this one
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM sessions
            WHERE protocol_id = ?
            AND session_id < ?
            AND deleted_at IS NULL
            """,
            (protocol_id, session_id)
        )

        count = cursor.fetchone()[0]

        # Session number is count + 1 (1-indexed)
        return count + 1


def get_bank_state(session_id: str, schedule_index: int) -> Optional[Dict[str, Any]]:
    """
    Get sample bank state for a session (for debugging/inspection).

    Args:
        session_id: Session ID
        schedule_index: Schedule entry index (0-indexed)

    Returns:
        Dict with state information or None if not found
    """
    with get_database_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT randomized_order, current_position, latin_square_session_number,
                   design_type, created_at, updated_at
            FROM session_sample_bank_state
            WHERE session_id = ? AND protocol_schedule_index = ?
            """,
            (session_id, schedule_index)
        )

        row = cursor.fetchone()

        if not row:
            return None

        return {
            "randomized_order": json.loads(row[0]),
            "current_position": row[1],
            "latin_square_session_number": row[2],
            "design_type": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }
