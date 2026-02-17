"""
Session Endpoints — Create, read, and manage experiment sessions.

=== WHAT THIS FILE DOES ===
Provides endpoints for the moderator to:
1. Create a new session (POST /api/sessions)
2. Get session info (GET /api/sessions/{id})
3. Start a trial with a protocol (POST /api/sessions/{id}/start)
4. Get monitoring status (GET /api/sessions/{id}/status)
5. Get sample data (GET /api/sessions/{id}/samples)
6. Get mode info (GET /api/sessions/{id}/mode-info)
7. End a session (POST /api/sessions/{id}/end)

=== KEY CONCEPTS ===
- Pydantic BaseModel: A way to define the expected shape of request data.
  When the frontend sends JSON in a POST request, FastAPI validates it
  against the model and gives clear errors if the data is wrong.
- Optional[str]: TypeScript equivalent of "string | undefined".
  Means the field can be a string or None/missing.
"""

from fastapi import APIRouter, HTTPException

# Pydantic is FastAPI's data validation library.
# BaseModel: Define a class that describes what JSON data looks like.
# Optional: A field that can be None (not required).
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import EXISTING database and session functions from your codebase.
# These are the exact same functions Streamlit uses.
from robotaste.data.database import (
    create_session,          # Creates a new session row in SQLite
    get_session,             # Gets full session data by session_id
    get_session_samples,     # Gets all samples for a session
    get_session_stats,       # Gets aggregate stats (total cycles, etc.)
    get_current_cycle,       # Gets the current cycle number
    update_session_with_config,  # Saves experiment config to session
    update_current_phase,    # Updates the current phase
    update_session_state,    # Updates session state (active/completed)
)
from robotaste.data.session_repo import get_session_info
from robotaste.data.protocol_repo import get_protocol_by_id
from robotaste.core.moderator_metrics import get_current_mode_info
from robotaste.config.bo_config import get_default_bo_config


# ─── REQUEST MODELS ─────────────────────────────────────────────────────────
# These classes define what JSON the frontend must send in POST requests.
# FastAPI automatically validates incoming data against these models.

class CreateSessionRequest(BaseModel):
    """
    Expected JSON body for creating a new session.

    Example request body:
    {
        "moderator_name": "Dr. Smith"
    }

    The 'moderator_name' field defaults to "Research Team" if not provided.
    """
    moderator_name: str = "Research Team"


class StartSessionRequest(BaseModel):
    """
    Expected JSON body for starting a trial with a protocol.

    Example request body:
    {
        "protocol_id": "abc-123-def-456",
        "pump_volumes": {"Sugar": 50.0, "Salt": 50.0}
    }
    """
    protocol_id: str
    pump_volumes: Optional[Dict[str, float]] = None


# ─── CREATE ROUTER ──────────────────────────────────────────────────────────
router = APIRouter()


# ─── CREATE SESSION ─────────────────────────────────────────────────────────
@router.post("")
def create_new_session(request: CreateSessionRequest):
    """
    Create a new experiment session.

    This is the equivalent of clicking "Create New Session" in the Streamlit UI.
    Returns the session_id (UUID) and session_code (6-character human-readable code).
    """
    # Call existing function — it creates a row in the 'sessions' SQLite table
    session_id, session_code = create_session(request.moderator_name)

    return {
        "session_id": session_id,
        "session_code": session_code,
        "moderator_name": request.moderator_name,
    }


# ─── GET SESSION ────────────────────────────────────────────────────────────
@router.get("/{session_id}")
def get_session_details(session_id: str):
    """
    Get full session data including experiment config.

    Returns the complete session object from the database.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ─── START SESSION WITH PROTOCOL ────────────────────────────────────────────
@router.post("/{session_id}/start")
def start_session(session_id: str, request: StartSessionRequest):
    """
    Start a trial by applying a protocol to the session.

    This is the equivalent of clicking "Start Trial" in the Streamlit moderator UI.
    It:
    1. Loads the protocol from the database
    2. Builds the experiment_config from the protocol
    3. Saves it to the session
    4. Transitions the phase from WAITING to the first active phase

    This replicates the logic in moderator.py's start_session_with_protocol().
    """
    # Step 1: Load the protocol
    protocol = get_protocol_by_id(request.protocol_id)
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")

    # Step 2: Verify session exists
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Step 3: Build experiment config from protocol
    # This mirrors what start_session_with_protocol() does in moderator.py
    experiment_config = _build_experiment_config(protocol, request.pump_volumes)

    # Step 4: Save config to session
    # update_session_with_config() requires these individual positional args
    # (it stores ingredients and BO config in separate DB tables alongside
    # the main experiment_config JSON blob)
    try:
        ingredients = experiment_config.get("ingredients", [])
        bo_config = experiment_config.get("bayesian_optimization", get_default_bo_config())
        num_ingredients = experiment_config.get("num_ingredients", len(ingredients))
        interface_type = experiment_config.get("interface_type", "single_slider")
        method = experiment_config.get("method", "linear")

        update_session_with_config(
            session_id=session_id,
            user_id=None,  # Participant hasn't joined yet
            num_ingredients=num_ingredients,
            interface_type=interface_type,
            method=method,
            ingredients=ingredients,
            bo_config=bo_config,
            experiment_config=experiment_config,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save config: {str(e)}"
        )

    # Step 5: Transition to first phase
    try:
        update_current_phase(session_id, "registration")
        update_session_state(session_id, "active")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start session: {str(e)}"
        )

    return {
        "message": "Session started successfully",
        "session_id": session_id,
        "protocol_name": protocol.get("name", "Unknown"),
        "current_phase": "registration",
    }


# ─── GET SESSION STATUS (for monitoring) ────────────────────────────────────
@router.get("/{session_id}/status")
def get_session_status(session_id: str):
    """
    Get current session status for the monitoring dashboard.

    Returns cycle number, current phase, mode info, and basic stats.
    The React monitoring page polls this endpoint every few seconds.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_info = get_session_info(session_id)
    current_cycle = get_current_cycle(session_id)
    stats = get_session_stats(session_id)

    return {
        "session_id": session_id,
        "session_code": session.get("session_code", ""),
        "current_phase": session_info.get("current_phase", "unknown") if session_info else "unknown",
        "current_cycle": current_cycle,
        "state": session.get("state", "unknown"),
        "total_cycles": stats.get("total_cycles", 0) if stats else 0,
        "experiment_config": session.get("experiment_config", {}),
    }


# ─── GET SESSION SAMPLES ───────────────────────────────────────────────────
@router.get("/{session_id}/samples")
def get_samples(session_id: str):
    """
    Get all samples (taste trials) for a session.

    Each sample contains:
    - cycle_number: Which cycle this was
    - ingredient_concentration: The concentrations used
    - questionnaire_answer: The participant's response
    - created_at: Timestamp
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    samples = get_session_samples(session_id)
    return {"samples": samples or []}


# ─── GET MODE INFO ──────────────────────────────────────────────────────────
@router.get("/{session_id}/mode-info")
def get_mode_info(session_id: str):
    """
    Get current mode information (predetermined/user_selected/bo_selected).

    Used by the monitoring page to determine which visualization to show.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        mode_info = get_current_mode_info(session_id)
        return mode_info
    except Exception as e:
        return {
            "current_mode": "unknown",
            "current_cycle": 0,
            "is_mixed_mode": False,
            "all_modes": [],
            "error": str(e),
        }


# ─── END SESSION ────────────────────────────────────────────────────────────
@router.post("/{session_id}/end")
def end_session(session_id: str):
    """
    End the session by transitioning to COMPLETE phase.
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    try:
        update_current_phase(session_id, "complete")
        update_session_state(session_id, "completed")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to end session: {str(e)}"
        )

    return {"message": "Session ended", "session_id": session_id}


# ─── HELPER FUNCTIONS ──────────────────────────────────────────────────────

def _build_experiment_config(protocol: dict, pump_volumes: Optional[Dict[str, float]] = None) -> dict:
    """
    Build experiment_config dict from a protocol.

    This mirrors the logic in moderator.py's start_session_with_protocol().
    The experiment_config is stored in the session and used by both
    the subject UI and the monitoring dashboard.

    Args:
        protocol: Full protocol dict from the database
        pump_volumes: Optional initial pump volumes per ingredient (in mL)

    Returns:
        experiment_config dict ready to be saved to the session
    """
    # Extract ingredients and convert to the format expected by the experiment
    ingredients = protocol.get("ingredients", [])
    experiment_ingredients = []
    for ing in ingredients:
        experiment_ingredients.append({
            "name": ing.get("name"),
            "min_concentration_mM": ing.get("min_concentration", 0),
            "max_concentration_mM": ing.get("max_concentration", 100),
        })

    # Get questionnaire config
    questionnaire_type = protocol.get("questionnaire_type", "liking_scale")
    questionnaire_config = protocol.get("questionnaire")

    # If no inline questionnaire, create from type name
    if not questionnaire_config:
        from robotaste.config.questionnaire import get_questionnaire_config
        questionnaire_config = get_questionnaire_config(questionnaire_type)

    # Build the config
    config = {
        "protocol_id": protocol.get("protocol_id"),
        "protocol_name": protocol.get("name"),
        "num_ingredients": len(experiment_ingredients),
        "ingredients": experiment_ingredients,
        "interface_type": "2d_grid" if len(experiment_ingredients) == 2 else "single_slider",
        "questionnaire": questionnaire_config,
        "questionnaire_name": questionnaire_type,
        "stopping_criteria": protocol.get("stopping_criteria", {"max_cycles": 10}),
        "sample_selection_schedule": protocol.get("sample_selection_schedule", []),
    }

    # Add BO config if present
    bo_config = protocol.get("bayesian_optimization")
    if bo_config:
        config["bayesian_optimization"] = bo_config

    # Add pump config if present
    pump_config = protocol.get("pump_config")
    if pump_config:
        config["pump_config"] = pump_config

    # Add initial pump volumes if provided
    if pump_volumes:
        config["initial_pump_volumes_ml"] = pump_volumes

    # Add phase sequence if present
    phase_sequence = protocol.get("phase_sequence")
    if phase_sequence:
        config["phase_sequence"] = phase_sequence

    return config
