"""
Session Management for Multi-Device RoboTaste Deployment
========================================================

Updated for new database schema (robotaste.db).
Handles session creation, device pairing, and synchronization.

Key Changes from v1:
- Uses new sql_handler_new with simplified schema
- session_id (UUID) serves as both ID and join code
- Simplified state management
- No fine-grained phase tracking in DB

Author: Masters Research Project
Version: 2.0 - Simplified Architecture
Last Updated: November 2025
"""

import random
import string
import qrcode
import io
import base64
import json
from PIL import Image
import streamlit as st
from datetime import datetime
from typing import Optional, Dict, Any
import logging

# Import sql_handler
import sql_handler as sql

# Setup logging
logger = logging.getLogger(__name__)


def create_qr_code(url: str) -> str:
    """
    Create a QR code for the given URL and return as base64 string.

    Args:
        url: URL to encode in QR code

    Returns:
        Base64-encoded PNG image as data URI
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,  # type: ignore
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64 for embedding in HTML
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")  # type: ignore
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def create_session(moderator_name: str, experiment_config: Dict) -> str:
    """
    Create a new session with complete experiment configuration.

    Args:
        moderator_name: Name of moderator creating session
        experiment_config: Complete experiment configuration dict containing:
            - user_id: User (taster) ID
            - num_ingredients: Number of ingredients
            - interface_type: 'grid_2d' or 'slider_based'
            - method: 'linear', 'logarithmic', 'exponential'
            - ingredients: List of ingredient dicts
            - question_type_id: FK to questionnaire_types
            - bayesian_optimization: BO config dict

    Returns:
        session_id (UUID string) - also serves as join code

    Example:
        >>> config = {
        ...     "user_id": "taster_001",
        ...     "num_ingredients": 2,
        ...     "interface_type": "grid_2d",
        ...     "method": "logarithmic",
        ...     "ingredients": [
        ...         {"position": 1, "name": "Sugar", "min": 0.73, "max": 73.0, "unit": "mM"},
        ...         {"position": 2, "name": "Salt", "min": 0.10, "max": 10.0, "unit": "mM"}
        ...     ],
        ...     "question_type_id": 1,
        ...     "bayesian_optimization": {
        ...         "enabled": True,
        ...         "acquisition_function": "ei"
        ...     }
        ... }
        >>> session_id = create_session("Dr. Smith", config)
        >>> print(session_id)
        'abc-123-def-456'
    """
    try:
        # Extract required fields
        user_id = experiment_config.get("user_id", "default_user")
        num_ingredients = experiment_config["num_ingredients"]
        interface_type = experiment_config["interface_type"]
        method = experiment_config["method"]
        ingredients = experiment_config["ingredients"]
        question_type_id = experiment_config.get("question_type_id", 1)
        bo_config = experiment_config.get("bayesian_optimization", {})

        # Add moderator name to config
        full_config = {**experiment_config, "moderator_name": moderator_name}

        # Ensure user exists in database
        sql.create_user(user_id)

        # Step 1: Create minimal session
        session_id = sql.create_session(moderator_name)

        # Step 2: Update with full configuration
        sql.update_session_with_config(
            session_id=session_id,
            user_id=user_id,
            num_ingredients=num_ingredients,
            interface_type=interface_type,
            method=method,
            ingredients=ingredients,
            question_type_id=question_type_id,
            bo_config=bo_config,
            experiment_config=full_config,
        )

        logger.info(f"Created session {session_id} for moderator {moderator_name}")
        return session_id

    except KeyError as e:
        logger.error(f"Missing required field in experiment_config: {e}")
        raise ValueError(f"Invalid experiment_config: missing {e}")
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise


def join_session(session_id: str) -> bool:
    """
    Check if session exists and is active (subject can join).

    Args:
        session_id: Session UUID

    Returns:
        True if session exists and is active, False otherwise
    """
    try:
        session = sql.get_session(session_id)
        if session and session["state"] == "active":
            logger.info(f"Subject joined session {session_id}")
            return True

        logger.warning(f"Cannot join session {session_id} - not found or not active")
        return False

    except Exception as e:
        logger.error(f"Error checking session {session_id}: {e}")
        return False


def get_session_info(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get session information directly from database.

    Args:
        session_id: Session UUID

    Returns:
        Session dict from database, or None if not found
    """
    try:
        return sql.get_session(session_id)
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        return None


def sync_session_state(session_id: str, role: str) -> bool:
    """
    Sync session state between devices using new database.

    Loads session config from database into Streamlit session_state.

    Args:
        session_id: Session UUID
        role: 'moderator' or 'subject'

    Returns:
        True if sync successful, False otherwise
    """
    try:
        session_info = get_session_info(session_id)

        if not session_info:
            logger.warning(f"Cannot sync session {session_id} - not found")
            return False

        # Store session info in Streamlit session state
        st.session_state.session_id = session_id
        st.session_state.session_code = (
            session_id  # Also set session_code for compatibility
        )
        st.session_state.session_info = session_info
        st.session_state.device_role = role
        st.session_state.last_sync = datetime.now()

        # Get experiment configuration (already parsed by sql handler)
        experiment_config = session_info.get("experiment_config")
        if experiment_config:
            # Set key config values in session_state for UI access
            st.session_state.interface_type = experiment_config.get(
                "interface_type", "grid_2d"
            )
            st.session_state.num_ingredients = experiment_config.get(
                "num_ingredients", 2
            )
            st.session_state.method = experiment_config.get("method", "logarithmic")
            st.session_state.ingredients = experiment_config.get("ingredients", [])
            st.session_state.questionnaire_type = session_info.get(
                "questionnaire_name", "hedonic_preference"
            )
            st.session_state.moderator_name = experiment_config.get(
                "moderator_name", "Moderator"
            )
            # Sync initial concentrations (for cycle 0 questionnaire save)
            initial_conc = experiment_config.get("initial_concentrations", {})
            if initial_conc:
                st.session_state.current_tasted_sample = initial_conc
            # Update both the UI control variable AND display variable
            phase_from_db = session_info.get("current_phase", "waiting")
            st.session_state.phase = phase_from_db  # UI control variable
            st.session_state.current_phase = phase_from_db  # Display variable

            logger.info(f"Synced session {session_id} for {role}")
        else:
            # Session not fully configured yet - set minimal defaults
            logger.info(
                f"Session {session_id} not fully configured yet, using defaults"
            )
            st.session_state.interface_type = "grid_2d"
            st.session_state.num_ingredients = 2
            st.session_state.method = "logarithmic"
            st.session_state.ingredients = []
            st.session_state.questionnaire_type = "hedonic_preference"
            st.session_state.moderator_name = st.session_state.get(
                "moderator_name", "Moderator"
            )
            # Update both the UI control variable AND display variable
            phase_from_db = session_info.get("current_phase", "waiting")
            st.session_state.phase = phase_from_db  # UI control variable
            st.session_state.current_phase = phase_from_db  # Display variable

        return True

    except Exception as e:
        logger.error(f"Error syncing session state: {e}")
        return False


def generate_session_urls(
    session_id: str, base_url: str = "https://robotaste.streamlit.app"
) -> Dict[str, str]:
    """
    Generate URLs for moderator and subject interfaces.

    Args:
        session_id: Session UUID (serves as join code)
        base_url: Base URL of deployment

    Returns:
        Dict with 'moderator' and 'subject' URLs
    """
    return {
        "moderator": f"{base_url}/?role=moderator&session={session_id}",
        "subject": f"{base_url}/?role=subject&session={session_id}",
    }


def display_session_qr_code(
    session_id: str,
    base_url: str = "https://robotaste.streamlit.app",
    context: str = "default",
):
    """
    Display QR code for subject to join session.

    Args:
        session_id: Session UUID
        base_url: Base URL of deployment
        context: Unique context string for widget keys
    """
    urls = generate_session_urls(session_id, base_url)
    subject_url = urls["subject"]
    qr_code_data = create_qr_code(subject_url)

    st.markdown("### Subject Access")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(
            f"""
        <div style="text-align: center; padding: 20px;">
            <h4>Scan QR Code</h4>
            <img src="{qr_code_data}" alt="QR Code" style="max-width: 200px;">
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**Session ID:**")
        st.code(session_id, language="text")
        st.markdown("**Subject URL:**")
        st.code(subject_url, language="text")

        if st.button(
            "Copy Subject URL",
            help="Copy URL to clipboard",
            key=f"session_qr_copy_url_{context}_{session_id[:8]}",
        ):
            st.success("URL copied to clipboard!")


def cleanup_old_sessions(hours: int = 24):
    """Clean up sessions older than specified hours."""
    with sql.get_database_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE sessions SET is_active = 0 
            WHERE last_activity < datetime('now', '-{} hours')
        """.format(
                hours
            )
        )

        conn.commit()
