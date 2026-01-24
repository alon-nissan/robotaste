"""
RoboTaste Session Repository - High-Level Session Management

Provides high-level abstractions for session operations, including:
- Session creation and joining
- Multi-device synchronization
- QR code generation
- URL handling

This layer sits above database.py and provides business logic for session management.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import qrcode
import io
import base64
import uuid
from typing import Optional, Dict, Any
import logging

# Import database layer
from robotaste.data import database as db

# Setup logging
logger = logging.getLogger(__name__)


# ============================================================================
# QR Code & URL Generation
# ============================================================================


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
        import streamlit as st
        import socket

        # Check if we're on Streamlit Cloud by examining the hostname
        hostname = socket.gethostname()

        # Check if running on streamlit.app (cloud deployment)
        if (
            "streamlit" in hostname.lower()
            or st.get_option("browser.serverAddress") == "robotaste.streamlit.app"
        ):
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
        logger.warning(
            f"Could not detect environment, defaulting to Streamlit Cloud: {e}"
        )
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


# ============================================================================
# Session Operations
# ============================================================================


def join_session(session_code: str) -> Optional[str]:
    """
    Check if session exists and is active, then generate UUID for participant.

    This is the SINGLE POINT OF UUID GENERATION for participants.
    The UUID is stored in session_state but NOT linked to the session in the database
    until the participant completes registration.

    Args:
        session_code: 6-character session code

    Returns:
        session_id (UUID) if session exists and is active, None otherwise

    Note:
        The participant UUID is stored in st.session_state.participant and will be
        linked to the session in the database when registration is completed.
    """
    try:
        import streamlit as st

        session = db.get_session_by_code(session_code)
        if not session:
            logger.warning(f"Session {session_code} not found")
            return None

        if session["state"] != "active":
            logger.warning(f"Session {session_code} is not active")
            return None

        session_id = session["session_id"]

        # Check if session already has a participant (enforce 1:1 relationship)
        if session.get("user_id"):
            logger.warning(
                f"Session {session_code} already has participant {session['user_id']}. "
                "Multiple subjects cannot join the same session."
            )
            return None

        # Generate new UUID for this participant
        user_id = str(uuid.uuid4())
        logger.info(f"Generated user ID {user_id} for session {session_code}")

        # Create user record in database (demographics will be added during registration)
        if not db.create_user(user_id):
            logger.error(f"Failed to create user {user_id}")
            return None

        # Store UUID in session_state (will be linked to session after registration)
        st.session_state.participant = user_id

        logger.info(
            f"Subject joined session {session_code} (ID: {session_id}, user: {user_id}). "
            "User will be linked to session after registration."
        )
        return session_id

    except Exception as e:
        logger.error(f"Error joining session {session_code}: {e}")
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
        return db.get_session(session_id)
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        return None


def sync_session_state_to_streamlit(session_id: str, role: str) -> bool:
    """
    Sync session state between devices using database.

    Loads session config from database into Streamlit session_state.

    Args:
        session_id: Session UUID
        role: 'moderator' or 'subject'

    Returns:
        True if sync successful, False otherwise

    Note:
        This function requires Streamlit context and should only be called from UI layer.
    """
    try:
        import streamlit as st
        from datetime import datetime

        session_info = get_session_info(session_id)

        if not session_info:
            logger.warning(f"Cannot sync session {session_id} - not found")
            return False

        # Store session info in Streamlit session state
        st.session_state.session_id = session_id
        st.session_state.session_code = session_info.get("session_code", "")
        st.session_state.session_info = session_info
        st.session_state.device_role = role
        st.session_state.last_sync = datetime.now()

        # Sync participant ID from session's user_id
        # IMPORTANT: Don't overwrite if we have a UUID in session_state but DB has None
        # (this happens when subject joins but hasn't completed registration yet)
        db_user_id = session_info.get("user_id")
        current_participant = st.session_state.get("participant")

        if db_user_id:
            # Database has a user_id, use it (participant has registered)
            st.session_state.participant = db_user_id
            logger.info(f"Synced participant {db_user_id} from database for {role}")
        elif not current_participant:
            # Database has no user_id AND session_state has no participant
            # Set to None (no one has joined yet)
            st.session_state.participant = None
            logger.debug(f"No participant has joined session {session_id} yet")
        else:
            # Database has no user_id BUT session_state has a participant UUID
            # Keep the session_state value (participant joined but hasn't registered yet)
            logger.debug(f"Preserving participant {current_participant} from session_state (not yet registered)")

        # Get experiment configuration (already parsed by database layer)
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
            st.session_state.experiment_config = experiment_config
            st.session_state.questionnaire_type = session_info.get(
                "questionnaire_name", "hedonic"
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
            st.session_state.questionnaire_type = "hedonic"
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


# ============================================================================
# UI Helper Functions (Streamlit-specific)
# ============================================================================


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

    Note:
        This function requires Streamlit context.
    """
    import streamlit as st

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
    Matches the clean, scientific aesthetic of mashaniv.wixsite.com/niv-taste-lab

    Args:
        session_code: 6-character session code
        base_url: Base URL of deployment (auto-detected if not provided)

    Note:
        This function requires Streamlit context.
    """
    import streamlit as st

    urls = generate_session_urls(session_code, base_url)
    subject_url = urls["subject"]
    qr_code_data = create_qr_code(subject_url)

    # Clean header with session code in prominent display
    st.markdown(
        f"""
        <div style='text-align: center; padding: 1.5rem;
        background: #F8F9FA; border-radius: 8px;
        border-left: 4px solid #521924; margin-bottom: 1.5rem;'>
            <div style='font-size: 0.85rem; color: #7F8C8D;
            font-weight: 400; margin-bottom: 0.25rem;
            letter-spacing: 0.1em; text-transform: uppercase;'>
            Session Code
            </div>
            <div style='font-size: 2rem; color: #2C3E50;
            font-weight: 600; letter-spacing: 0.3rem;
            font-family: "Monaco", "Courier New", monospace;'>
            {session_code}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        # Display QR code with cleaner styling
        st.markdown("**Scan to Join**")
        st.markdown(
            f"""
            <div style="text-align: center;">
                <img src="{qr_code_data}" alt="QR Code"
                style="max-width: 150px; border: 1px solid #E5E7EB;
                border-radius: 8px; padding: 8px; background: white;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**Share This Link**")
        st.code(subject_url, language=None)
        st.caption(
            "Subjects can scan the QR code or click the link to join the experiment."
        )
