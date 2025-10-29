"""
🍯 RoboTaste - Interactive Taste Preference Experiment Platform

OVERVIEW:
=========
A sophisticated research platform for studying taste preferences through interactive
digital interfaces. Designed for Masters-level taste perception research with
comprehensive data collection and analysis capabilities.

CORE FEATURES:
==============
• Dual Interface Support: 2D grid (binary mixtures) + Multi-component sliders (2-6 ingredients)
• Real-time Questionnaire System: Post-selection feedback collection
• Persistent Selection History: Visual tracking of participant interactions
• Advanced Analytics: Concentration mapping and solution preparation calculations
• Role-based Access: Separate moderator and subject interfaces
• Comprehensive Data Storage: SQLite with JSON support for complex concentration data

INTERFACE MODES:
===============
1. 2D GRID MODE (2 ingredients):
   - Traditional X-Y coordinate selection
   - Maps to Sugar + Salt concentrations
   - Three mapping methods: linear, logarithmic, exponential
   - Concentration range: Sugar (0.73-73.0 mM), Salt (0.10-10.0 mM)

2. SLIDER MODE (3-6 ingredients):
   - Independent concentration sliders
   - Generic ingredient labels (A, B, C...)
   - Subject sees percentages, system calculates actual mM concentrations
   - Supports: Sugar, Salt, Citric Acid, Caffeine, Vanilla, Menthol

WORKFLOW:
=========
Subject Flow: Welcome → Pre-Questionnaire → Interface Selection → Post-Questionnaire → Final Response
Moderator Flow: Configure Experiment → Monitor Real-time → Analyze Data → Export Results

Author: Masters Research Project
Version: 2.0 - Multi-Component Support
Last Updated: 2025
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

# Custom CSS with proper dark/light mode support
st.markdown(
    """
<style>
    /* CSS Variables for theme consistency */
    :root {
        --primary-color: #4f46e5;
        --primary-light: #818cf8;
        --primary-dark: #3730a3;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --error-color: #ef4444;
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        --bg-primary: #ffffff;
        --bg-secondary: #f9fafb;
        --border-color: #e5e7eb;
        --shadow-light: rgba(0, 0, 0, 0.1);
    }
    
    /* Dark mode variables */
    [data-theme="dark"], .stApp[data-theme="dark"] {
        --text-primary: #f9fafb !important;
        --text-secondary: #d1d5db !important;
        --bg-primary: #1f2937 !important;
        --bg-secondary: #374151 !important;
        --border-color: #4b5563 !important;
        --shadow-light: rgba(255, 255, 255, 0.1) !important;
    }
    
    /* Force dark mode styles when detected */
    @media (prefers-color-scheme: dark) {
        :root {
            --text-primary: #f9fafb !important;
            --text-secondary: #d1d5db !important;
            --bg-primary: #1f2937 !important;
            --bg-secondary: #374151 !important;
            --border-color: #4b5563 !important;
            --shadow-light: rgba(255, 255, 255, 0.1) !important;
        }
    }
    
    .main-header {
        padding: 1.5rem;
        background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
        color: white;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 12px var(--shadow-light);
    }
    
    .main-header h1 {
        margin: 0;
        font-weight: 600;
        font-size: 2rem;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
        font-size: 1.1rem;
    }
    
    .status-card {
        background: var(--bg-secondary);
        color: var(--text-primary);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid var(--primary-color);
        margin: 1rem 0;
        box-shadow: 0 2px 8px var(--shadow-light);
        border: 1px solid var(--border-color);
    }
    
    .status-card h3 {
        margin: 0 0 0.5rem 0;
        color: var(--text-primary);
        font-weight: 600;
    }
    
    .status-card p {
        margin: 0.25rem 0;
        color: var(--text-secondary);
    }
    
    .success-card {
        background: var(--bg-secondary);
        color: var(--text-primary);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid var(--success-color);
        box-shadow: 0 2px 8px var(--shadow-light);
        border: 1px solid var(--border-color);
    }
    
    .success-card h4 {
        margin: 0 0 0.5rem 0;
        color: var(--success-color);
        font-weight: 600;
    }
    
    .success-card p {
        margin: 0.25rem 0;
        color: var(--text-secondary);
    }
    
    .warning-card {
        background: var(--bg-secondary);
        color: var(--text-primary);
        padding: 1.5rem;
        border-radius: 12px;
        border-left: 4px solid var(--warning-color);
        box-shadow: 0 2px 8px var(--shadow-light);
        border: 1px solid var(--border-color);
    }
    
    .warning-card h4 {
        margin: 0 0 0.5rem 0;
        color: var(--warning-color);
        font-weight: 600;
    }
    
    .warning-card p {
        margin: 0.25rem 0;
        color: var(--text-secondary);
    }
    
    .metric-card {
        background: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px var(--shadow-light);
        border: 1px solid var(--border-color);
        transition: all 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px var(--shadow-light);
    }
    
    .metric-card h4 {
        margin: 0 0 0.5rem 0 !important;
        color: var(--primary-color) !important;
        font-weight: 600;
    }
    
    .metric-card p {
        margin: 0 !important;
        color: var(--text-primary) !important;
        line-height: 1.5;
        opacity: 0.8;
    }
    
    /* Force text visibility in metric cards */
    .metric-card * {
        color: inherit !important;
    }
    
    .metric-card h4 {
        color: var(--primary-color) !important;
    }
    
    .canvas-container {
        border: 2px solid var(--border-color);
        border-radius: 12px;
        padding: 1.5rem;
        background: var(--bg-primary);
        box-shadow: 0 4px 12px var(--shadow-light);
        transition: all 0.2s ease;
    }
    
    .canvas-container:hover {
        border-color: var(--primary-light);
    }
    
    /* Phase-specific styling with better contrast */
    .phase-welcome {
        background: var(--bg-secondary);
        border-left-color: var(--warning-color) !important;
    }
    
    .phase-respond {
        background: var(--bg-secondary);
        border-left-color: var(--primary-color) !important;
    }
    
    .phase-done {
        background: var(--bg-secondary);
        border-left-color: var(--success-color) !important;
    }
    
    /* Improve button styling */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid var(--border-color);
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px var(--shadow-light);
    }
    
    /* Better tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }
    
    /* Improve metric display */
    [data-testid="metric-container"] {
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 1px 3px var(--shadow-light);
    }
    
    /* Better sidebar styling */
    .css-1d391kg {
        background: var(--bg-secondary);
    }
    
    /* Improve text input styling */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid var(--border-color);
        background: var(--bg-primary);
        color: var(--text-primary);
    }
    
    .stSelectbox > div > div > div {
        border-radius: 8px;
        border: 1px solid var(--border-color);
        background: var(--bg-primary);
    }
    
    /* Improve dataframe styling */
    .stDataFrame {
        border: 1px solid var(--border-color);
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Better alert styling */
    .stAlert {
        border-radius: 8px;
        border: 1px solid var(--border-color);
    }
    
    /* Better focus indicators for keyboard navigation */
    button:focus, input:focus, select:focus {
        outline: 2px solid var(--primary-color) !important;
        outline-offset: 2px !important;
    }
    
    /* Screen reader only text */
    .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        border: 0;
    }
    
    /* Skip link for keyboard users */
    .skip-link {
        position: absolute;
        top: -40px;
        left: 6px;
        background: var(--primary-color);
        color: white;
        padding: 8px;
        text-decoration: none;
        border-radius: 4px;
        z-index: 1000;
    }
    
    .skip-link:focus {
        top: 6px;
    }
    
    /* Responsive design improvements */
    @media (max-width: 768px) {
        .main-header {
            padding: 1rem;
        }
        
        .main-header h1 {
            font-size: 1.5rem;
        }
        
        .status-card, .success-card, .warning-card, .metric-card {
            padding: 1rem;
        }
        
        .canvas-container {
            padding: 1rem;
        }
    }
    
    /* Fix select box styling for better theme compatibility */
    .stSelectbox > div > div > select {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    .stSelectbox > div > div > div {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }
    
    .stSelectbox label {
        color: var(--text-primary) !important;
    }
    
    /* Fix dropdown menu styling */
    .stSelectbox > div > div > div > div {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    /* Ensure text inputs also follow theme */
    .stTextInput > div > div > input {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }
    
    .stTextInput label {
        color: var(--text-primary) !important;
    }
    
    /* Fix button styling for consistency */
    .stButton > button {
        border: 1px solid var(--border-color) !important;
    }
    
    /* Alternative approach: Force dark mode if selectbox styling fails */
</style>
""",
    unsafe_allow_html=True,
)

# Apply dark mode CSS if enabled by user
if st.session_state.get("force_dark_mode", False):
    st.markdown(
        """
        <style>
        /* Force dark mode when setting is enabled */
        .stApp {
            color-scheme: dark;
            background-color: #1f2937 !important;
            color: #f9fafb !important;
        }
        
        /* Ensure all elements use dark theme */
        .stSelectbox > div > div > select,
        .stSelectbox > div > div > div,
        .stTextInput > div > div > input {
            background-color: #374151 !important;
            color: #f9fafb !important;
            border: 1px solid #4b5563 !important;
        }
        
        /* Fix sidebar styling in dark mode */
        .stSidebar .stSelectbox > div > div > select,
        .stSidebar .stSelectbox > div > div > div {
            background-color: #374151 !important;
            color: #f9fafb !important;
        }
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
    # Clean up old sessions periodically
    from session_manager import cleanup_old_sessions

    cleanup_old_sessions(24)  # Clean sessions older than 24 hours

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
    # TODO: Add application health checks and monitoring
    main()

# =============================================================================
# END OF FILE - DEVELOPMENT NOTES
# =============================================================================
# KEY TECHNICAL DEBT:
# - Unused column variables (col1, col3) in UI layouts - should be cleaned up
# - Theme toggle functionality needs proper persistence
# - Moderator interface needs authentication system
#
# SECURITY CONSIDERATIONS:
# - Add password protection for moderator access before production
# - Implement session timeouts for participant safety
# - Add data validation for all user inputs
#
# PERFORMANCE OPTIMIZATIONS:
# - Implement caching for repeated database queries
# - Add connection pooling for concurrent users
# - Optimize large dataset rendering
# =============================================================================
