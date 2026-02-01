"""
RoboTaste — Binary-Mix & Single-Variable Experiment App

OVERVIEW:
A trimmed, purpose-specific build of the RoboTaste interactive experiment platform
focused on binary mixtures (2-ingredient 2D grid) and single-variable experiments
(single slider). This variant removes multi-component UI scaffolding to keep the
codepath minimal for controlled taste-preference studies and easy replication.

SCOPE:
- 2D grid experiments for binary mixtures (Sugar + Salt mapping)
- Single-variable slider experiments for one-ingredient trials
- Session-based moderator/subject routing and basic persistence (SQLite)
- Accessibility defaults (focus outlines, SR-only support)

INTENDED USE:
This file supports multi-device experiments where a moderator configures trials
and participants respond via subject devices. The UI and CSS are intentionally
minimal to reduce cognitive load and simplify experiment replication.

Author: Masters Research Project
Version: 2.1-binary-only
Last Updated: 2025-11-19
"""

import streamlit as st
import logging
from datetime import datetime

# Import our modules
from robotaste.data.database import init_database
from robotaste.data.session_repo import (
    join_session,
    get_session_info,
    sync_session_state_to_streamlit as sync_session_state,
)
from robotaste.utils.viewport import (
    initialize_viewport_detection,
    get_responsive_font_scale,
)

# Page configuration
st.set_page_config(
    page_title="Taste Experiment System",
    page_icon="",
    layout="wide",
    initial_sidebar_state="auto",
)


def setup_logging():
    """Sets up logging to a file and the console."""
    from robotaste.utils.logging_manager import setup_logging as configure_logging

    configure_logging(component="app")
    logging.info("Logging configured to file and console.")


# Initialize viewport detection EARLY (before CSS)
# This must be done before rendering CSS that depends on viewport
if "viewport_initialized" not in st.session_state:
    viewport = initialize_viewport_detection()
    st.session_state.viewport_initialized = True
else:
    viewport = st.session_state.viewport_data

# Get font scale for responsive typography
font_scale = get_responsive_font_scale()

# Modern card-based CSS with balanced color palette and larger fonts
from robotaste.components.styles import apply_styles

apply_styles()

# Initialize database only once per session
# TODO: Add database health monitoring and automatic backup
if "db_initialized" not in st.session_state:
    if init_database():
        st.session_state.db_initialized = True
    else:
        st.error("Database initialization failed. Please check your setup.")
        st.stop()


# Initialize session state
def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "participant": None,
        "phase": "waiting",  # Changed from "welcome" to match ExperimentPhase enum
        "method": "linear",
        "auto_refresh": True,
        "last_sync": None,
        "theme_preference": "auto",
        "high_contrast": False,
        "session_code": None,
        "session_info": None,
        "device_role": None,
        "connection_status": "disconnected",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


def render_logo():
    """
    Render the Niv Lab logo at the top of the page.

    Must be called at the start of each view function to ensure it persists
    through Streamlit's rerun mechanism.
    """
    from pathlib import Path

    logo_path = Path(__file__).parent / "docs" / "niv_lab_logo.png"
    if logo_path.exists():
        col1, col2 = st.columns([1, 3])
        with col1:
            st.image(str(logo_path), width=250)


# Import interface modules after initialization to avoid circular imports
from robotaste.views.landing import landing_page
from robotaste.views.moderator import moderator_interface
from robotaste.views.subject import subject_interface


# Main application router
def main():
    """
    Multi-device application router with session management.

    Handles session-based routing for moderator and subject devices.
    Supports direct URL access with session codes for seamless multi-device experience.
    """
    # Configure logging only once per session
    if "logging_configured" not in st.session_state:
        setup_logging()
        st.session_state.logging_configured = True

    # Route to appropriate interface based on URL parameter and session state
    role = st.query_params.get("role", "")
    session_code = st.query_params.get("session", "")

    # Check if we have session info in session state, prioritize session state
    if st.session_state.session_code and st.session_state.device_role:
        role = st.session_state.device_role
        session_code = st.session_state.session_code
    # If URL params exist but session state is missing, try to sync
    elif role and session_code:
        if role == "moderator":
            # Get session by code, then extract session_id for syncing
            from robotaste.data.database import get_session_by_code

            session_info = get_session_by_code(session_code)
            if session_info and session_info.get("state") == "active":
                sync_session_state(session_info["session_id"], "moderator")
            else:
                # Invalid session, clear URL params
                st.query_params.clear()
                role = ""
                session_code = ""
        elif role == "subject":
            session_id = join_session(session_code)
            if session_id:
                sync_session_state(session_id, "subject")
            else:
                # Invalid session, clear URL params
                st.query_params.clear()
                role = ""
                session_code = ""

    # Route to appropriate interface - no placeholder to avoid blank screen issues
    if role and session_code:
        if role == "subject":
            subject_interface()
        elif role == "moderator":
            moderator_interface()

        # Auto-refresh disabled to prevent blank screen issues
        # Users can manually refresh using browser or interface controls
        # if st.session_state.get("auto_refresh", True):
        #     time.sleep(5)
        #     st.rerun()
    else:
        # Default landing page for session creation/joining
        landing_page()


if __name__ == "__main__":
    main()
