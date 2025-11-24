"""
Session Management for Multi-Device RoboTaste Deployment
========================================================

Handles session creation, device pairing, and synchronization.

Author: Masters Research Project
Last Updated: 2025
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


def join_session(session_code: str) -> Optional[str]:
    """
    Check if session exists and is active (subject can join).

    Args:
        session_code: 6-character session code

    Returns:
        session_id (UUID) if session exists and is active, None otherwise
    """
    try:
        session = sql.get_session_by_code(session_code)
        if session and session["state"] == "active":
            session_id = session["session_id"]
            logger.info(f"Subject joined session {session_code} (ID: {session_id})")
            return session_id

        logger.warning(f"Cannot join session {session_code} - not found or not active")
        return None

    except Exception as e:
        logger.error(f"Error checking session {session_code}: {e}")
        return None


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
        st.session_state.session_code = session_info.get("session_code", "")  # Get 6-char code from DB
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
            # Store full experiment_config for fallback checks in subject_interface
            st.session_state.experiment_config = experiment_config
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
            # Sync initial slider values (for cycle 0 selection_data)
            initial_slider = experiment_config.get("initial_slider_values", {})
            if initial_slider:
                st.session_state.random_slider_values = initial_slider
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


def get_base_url() -> str:
    """
    Automatically detect the base URL based on the deployment environment.

    Checks for:
    - Streamlit Cloud deployment (streamlit.app)
    - Local development (localhost with port)

    Returns:
        Base URL appropriate for the current environment
    """
    try:
        # Try to get the actual hostname/URL from Streamlit's query params or config
        from streamlit.web import cli as stcli
        import socket

        # Check if we're on Streamlit Cloud by examining the hostname
        hostname = socket.gethostname()

        # Check if running on streamlit.app (cloud deployment)
        if "streamlit" in hostname.lower() or st.get_option("browser.serverAddress") == "robotaste.streamlit.app":
            return "https://robotaste.streamlit.app"

        # For local development, try to get the actual server address and port
        server_port = st.get_option("server.port")
        server_address = st.get_option("browser.serverAddress")

        if server_address and server_address not in ["localhost", "0.0.0.0", ""]:
            # Use configured server address
            return f"http://{server_address}:{server_port}"
        else:
            # Default to localhost with port
            return f"http://localhost:{server_port}"

    except Exception as e:
        logger.warning(f"Could not detect environment, defaulting to Streamlit Cloud: {e}")
        # Default to production URL if detection fails
        return "https://robotaste.streamlit.app"


def generate_session_urls(
    session_code: str, base_url: Optional[str] = None
) -> Dict[str, str]:
    """
    Generate URLs for moderator and subject interfaces.

    Args:
        session_code: 6-character session code (user-facing identifier)
        base_url: Base URL of deployment (auto-detected if not provided)

    Returns:
        Dict with 'moderator' and 'subject' URLs
    """
    if base_url is None:
        base_url = get_base_url()

    return {
        "moderator": f"{base_url}/?role=moderator&session={session_code}",
        "subject": f"{base_url}/?role=subject&session={session_code}",
    }


def display_session_qr_code(
    session_code: str,
    base_url: Optional[str] = None,
    context: str = "default",
):
    """
    Display QR code for subject to join session.

    Args:
        session_code: 6-character session code
        base_url: Base URL of deployment (auto-detected if not provided)
        context: Unique context string for widget keys
    """
    urls = generate_session_urls(session_code, base_url)
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
        st.markdown("**Session Code:**")
        st.code(session_code, language="text")
        st.markdown("**Subject URL:**")
        st.code(subject_url, language="text")

        if st.button(
            "Copy Subject URL",
            help="Copy URL to clipboard",
            key=f"session_qr_copy_url_{context}_{session_code}",
        ):
            st.success("URL copied to clipboard!")


def display_subject_access_section(session_code: str, base_url: Optional[str] = None):
    """
    Display compact subject access section with QR code and link for moderator overview.

    This is a more compact version designed for the moderator overview tab.

    Args:
        session_code: 6-character session code
        base_url: Base URL of deployment (auto-detected if not provided)
    """
    urls = generate_session_urls(session_code, base_url)
    subject_url = urls["subject"]
    qr_code_data = create_qr_code(subject_url)

    st.markdown("**Subject Interface Access**")

    col1, col2 = st.columns([1, 2])

    with col1:
        # Display QR code
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="{qr_code_data}" alt="QR Code" style="max-width: 150px; border: 2px solid #e0e0e0; border-radius: 8px; padding: 5px;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**Share this link with participants:**")
        st.markdown(f"[{subject_url}]({subject_url})")
        st.caption("Scan the QR code or share the link above to allow subjects to join this session.")
