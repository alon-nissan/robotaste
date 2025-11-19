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

# Import our modules
from sql_handler import init_database
from session_manager import (
    join_session,
    get_session_info,
    sync_session_state,
)

# Page configuration
st.set_page_config(
    page_title="Taste Experiment System",
    page_icon="",
    layout="wide",
    initial_sidebar_state="auto",
)

# Consolidated minimal CSS: accessible, low-visual-noise styles for experiments
st.markdown(
    """
<style>
    :root {
        --primary-color: #4f46e5;
        --text-primary: #111827;
        --bg-primary: #ffffff;
        --border-color: #e5e7eb;
        --shadow-light: rgba(0,0,0,0.06);
    }

    /* Dark-mode variable overrides */
    [data-theme="dark"], @media (prefers-color-scheme: dark) {
        :root { --text-primary: #f9fafb; --bg-primary: #1f2937; --border-color: #4b5563; --shadow-light: rgba(255,255,255,0.04); }
    }

    .main-header { padding: 1rem; background: var(--primary-color); color: white; border-radius: 8px; text-align: center; margin-bottom: 1rem; }
    .main-header h1 { margin: 0; font-weight: 600; font-size: 1.25rem; }

    button:focus, input:focus, select:focus { outline: 2px solid var(--primary-color); outline-offset: 2px; }

    .stButton > button { border-radius: 6px; border: 1px solid var(--border-color); padding: 0.45rem 0.75rem; background: transparent; }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 2px 6px var(--shadow-light); }

    .stTextInput input, .stTextInput > div > div > input { border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary); padding: 0.35rem; }

    .stSelectbox select, .stSelectbox > div > div > select { border-radius: 6px; border: 1px solid var(--border-color); background: var(--bg-primary); color: var(--text-primary); padding: 0.25rem; }

    .stTabs [data-baseweb="tab"] { padding: 0.5rem 1rem; border-radius: 6px 6px 0 0; }

    [data-testid="metric-container"] { padding: 0.75rem; border: 1px solid var(--border-color); border-radius: 8px; background: var(--bg-primary); }

    .stDataFrame { border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; }
    .stAlert { border-radius: 8px; border: 1px solid var(--border-color); }

    .sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
    .skip-link { position: absolute; top: -40px; left: 6px; background: var(--primary-color); color: white; padding: 8px; border-radius: 4px; z-index: 1000; }

    @media (max-width: 768px) { .main-header { padding: 0.75rem; } .main-header h1 { font-size: 1rem; } }
</style>
""",
    unsafe_allow_html=True,
)

# Apply dark mode CSS if enabled by user (minimal override)
if st.session_state.get("force_dark_mode", False):
    st.markdown(
        """
        <style>
        /* Minimal dark-mode hint: prefer dark color-scheme */
        .stApp { color-scheme: dark; }
        </style>
        """,
        unsafe_allow_html=True,
    )

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
        "participant": "participant_001",
        "phase": "welcome",
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


def add_accessibility_features():
    """Add accessibility enhancements based on user preferences."""

    # High contrast mode
    if st.session_state.get("high_contrast", False):
        st.markdown(
            """
        <style>
            :root {
                --primary-color: #0066cc !important;
                --success-color: #008000 !important;
                --warning-color: #ff8800 !important;
                --error-color: #cc0000 !important;
                --text-primary: #000000 !important;
                --bg-primary: #ffffff !important;
                --border-color: #333333 !important;
            }
            
            [data-theme="dark"] {
                --text-primary: #ffffff !important;
                --bg-primary: #000000 !important;
                --border-color: #cccccc !important;
            }
            
            .main-header, .status-card, .success-card, .warning-card, .metric-card {
                border: 2px solid var(--text-primary) !important;
            }
            
            button, input, select {
                border: 2px solid var(--text-primary) !important;
                background: var(--bg-primary) !important;
                color: var(--text-primary) !important;
            }
        </style>
        """,
            unsafe_allow_html=True,
        )


# Add accessibility features
add_accessibility_features()


# Import interface modules after initialization to avoid circular imports
from landing_page import landing_page
from moderator_interface import moderator_interface
from subject_interface import subject_interface


# Main application router
def main():
    """
    Multi-device application router with session management.

    Handles session-based routing for moderator and subject devices.
    Supports direct URL access with session codes for seamless multi-device experience.
    """

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
            session_info = get_session_info(session_code)
            if session_info and session_info["is_active"]:
                sync_session_state(session_code, "moderator")
            else:
                # Invalid session, clear URL params
                st.query_params.clear()
                role = ""
                session_code = ""
        elif role == "subject":
            if join_session(session_code):
                sync_session_state(session_code, "subject")
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
