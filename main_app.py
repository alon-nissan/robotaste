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
import pandas as pd
import time
import plotly.express as px
import plotly.graph_objects as go
from streamlit_drawable_canvas import st_canvas
from datetime import datetime
from typing import Optional
import streamlit_vertical_slider as svs

# Import our modules
from callback import (
    ConcentrationMapper,
    create_canvas_drawing,
    start_trial,
    finish_trial,
    get_concentration_display,
    CANVAS_SIZE,
    save_intermediate_click,
    clear_canvas_state,
    render_questionnaire,
    show_preparation_message,
    MultiComponentMixture,
    create_ingredient_sliders,
    INTERFACE_2D_GRID,
    INTERFACE_SLIDERS,
    save_slider_trial,
    cleanup_pending_results,
)
from sql_handler import (
    init_database,
    is_participant_activated,
    get_moderator_settings,
    get_latest_subject_response,
    update_session_state,
    get_participant_responses,
    clear_participant_session,
    get_all_participants,
    get_database_stats,
    get_latest_submitted_response,
    get_latest_recipe_for_participant,
    get_live_subject_position,
    save_multi_ingredient_response,
    store_user_interaction_v2,
    export_responses_csv,
    get_initial_slider_positions,
)
from session_manager import (
    create_session,
    join_session,
    get_session_info,
    update_session_activity,
    display_session_qr_code,
    sync_session_state,
    get_connection_status,
    generate_session_urls,
)

# Page configuration
st.set_page_config(
    page_title="Taste Experiment System",
    page_icon="🧪",
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
        st.error("⚠️ Database initialization failed. Please check your setup.")
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


def create_header(title: str, subtitle: str = "", icon: str = "🧪"):
    """Create a beautiful, accessible header section."""

    # Theme toggle in header
    # TODO: Remove unused col1, col3 variables for cleaner code
    col1, col2, col3 = st.columns([1, 2, 1])
    with col3:
        # Add theme preference (stored in session state)
        if "theme_preference" not in st.session_state:
            st.session_state.theme_preference = "auto"

        theme_options = {"🌓 Auto": "auto", "☀️ Light": "light", "🌙 Dark": "dark"}

        selected_theme = st.selectbox(
            "Theme",
            options=list(theme_options.keys()),
            index=list(theme_options.values()).index(st.session_state.theme_preference),
            key="header_theme_selector",
            label_visibility="collapsed",
        )

        st.session_state.theme_preference = theme_options[selected_theme]

    # Header content
    st.markdown(
        f"""
    <div class="main-header">
        <h1>{icon} {title}</h1>
        {f"<p>{subtitle}</p>" if subtitle else ""}
    </div>
    """,
        unsafe_allow_html=True,
    )


def display_phase_status(phase: str, participant_id: str):
    """Display current phase with beautiful, accessible status card."""
    phase_info = {
        "welcome": {
            "icon": "👋",
            "title": "Welcome Phase",
            "desc": "Waiting to begin experiment",
            "class": "phase-welcome",
            "color": "var(--warning-color)",
        },
        "pre_questionnaire": {
            "icon": "📋",
            "title": "Pre-Sample Questionnaire",
            "desc": "Please complete the initial questionnaire",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "respond": {
            "icon": "🎯",
            "title": "Response Phase",
            "desc": "Experiment in progress - make your selection",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "post_response_message": {
            "icon": "🧪",
            "title": "Solution Preparation",
            "desc": "Thank you for your response - solution is being prepared",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "post_questionnaire": {
            "icon": "📋",
            "title": "Post-Response Questionnaire",
            "desc": "Please answer questions about your response",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "done": {
            "icon": "✅",
            "title": "Completed",
            "desc": "Trial finished successfully",
            "class": "phase-done",
            "color": "var(--success-color)",
        },
    }

    info = phase_info.get(phase, phase_info["welcome"])

    st.markdown(
        f"""
    <div class="status-card {info['class']}">
        <h3 style="color: {info['color']};">{info['icon']} {info['title']}</h3>
        <p><strong>Participant:</strong> {participant_id}</p>
        <p style="font-size: 1.1rem; margin-top: 0.5rem;">{info['desc']}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )


def subject_interface():
    """Multi-device subject interface with session management."""
    # Check if we have a valid session
    if not st.session_state.session_code:
        st.error(
            "❌ No active session. Please join a session using the code provided by your moderator."
        )
        if st.button("🏠 Return to Home", key="subject_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    session_info = get_session_info(st.session_state.session_code)
    if not session_info or not session_info["is_active"]:
        st.error("❌ Session expired or invalid.")
        st.session_state.session_code = None
        if st.button("🏠 Return to Home", key="subject_return_home_invalid_session"):
            st.query_params.clear()
            st.rerun()
        return

    create_header(
        f"Session {st.session_state.session_code}", f"Taste Preference Experiment", "👤"
    )

    # Update session activity
    update_session_activity(st.session_state.session_code)

    # Get or set participant ID
    if st.session_state.phase == "welcome":
        # TODO: Remove unused col1, col3 variables
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 👋 Welcome!")
            st.write("Please enter your participant ID to begin the experiment.")

            participant_id = st.text_input(
                "Participant ID:",
                value=st.session_state.participant,
                placeholder="e.g., participant_001",
                key="subject_participant_id_input",
            )

            if participant_id != st.session_state.participant:
                st.session_state.participant = participant_id

            # Check if activated by moderator
            if st.button(
                "🚀 Check Status",
                type="primary",
                use_container_width=True,
                key="subject_check_status_button",
            ):
                if is_participant_activated(participant_id):
                    st.session_state.phase = "pre_questionnaire"
                    st.success("✅ Ready to begin!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("⏳ Waiting for moderator to start your session.")

            # Auto-check disabled to prevent infinite reload loops
            # User can manually check status using the button above
            # with st.empty():
            #     if is_participant_activated(participant_id):
            #         st.session_state.phase = "pre_questionnaire"
            #         st.rerun()
            #     else:
            #         time.sleep(3)
            #         st.rerun()

    elif st.session_state.phase == "pre_questionnaire":
        display_phase_status("pre_questionnaire", st.session_state.participant)

        # Render initial impression questionnaire (using unified questionnaire)
        # TODO: Remove unused col1, col3 variables for cleaner code
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(
                "📍 Please provide your initial impression of the random starting solution shown on the canvas."
            )
            responses = render_questionnaire(
                "unified_feedback", st.session_state.participant
            )

            if responses:
                # Store questionnaire responses in session state for potential database storage
                st.session_state.initial_questionnaire_responses = responses
                # Move to respond phase
                st.session_state.phase = "respond"
                st.rerun()

    elif st.session_state.phase == "respond":
        display_phase_status("respond", st.session_state.participant)

        # Get moderator settings
        mod_settings = get_moderator_settings(st.session_state.participant)
        if not mod_settings:
            st.error("❌ No experiment settings found. Please contact the moderator.")
            return

        # Determine interface type based on session state set by start_trial
        num_ingredients = st.session_state.get("num_ingredients", 2)
        interface_type = st.session_state.get("interface_type", INTERFACE_2D_GRID)

        # Ensure DEFAULT_INGREDIENT_CONFIG is available
        from callback import DEFAULT_INGREDIENT_CONFIG

        experiment_config = {
            "num_ingredients": num_ingredients,
            "ingredients": DEFAULT_INGREDIENT_CONFIG[:num_ingredients],
        }

        mixture = MultiComponentMixture(experiment_config["ingredients"])

        # Verify interface type matches ingredients (safety check)
        calculated_interface = mixture.get_interface_type()
        if calculated_interface != interface_type:
            st.warning(f"Interface type mismatch. Using calculated: {calculated_interface}")
            interface_type = calculated_interface

        if interface_type == INTERFACE_2D_GRID:
            # Traditional 2D grid interface
            st.markdown("### 🎯 Make Your Selection")
            st.write(
                "Click anywhere on the grid below to indicate your taste preference."
            )

            # Create canvas with grid and starting position
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.markdown('<div class="canvas-container">', unsafe_allow_html=True)

                # Get selection history for persistent visualization
                selection_history = getattr(st.session_state, "selection_history", None)

                # Legacy canvas drawing - mod_settings no longer contains x/y positions
                # Use default canvas for grid interface
                initial_drawing = create_canvas_drawing(
                    300,  # Default center position
                    300,  # Default center position
                    selection_history,
                )

            canvas_result = st_canvas(
                fill_color=(
                    "#EF4444"
                    if not st.session_state.get("high_contrast", False)
                    else "#FF0000"
                ),
                stroke_width=2,
                stroke_color=(
                    "#DC2626"
                    if not st.session_state.get("high_contrast", False)
                    else "#000000"
                ),
                background_color="white",
                update_streamlit=True,
                height=CANVAS_SIZE,
                width=CANVAS_SIZE,
                drawing_mode="point",
                point_display_radius=8,
                display_toolbar=False,
                initial_drawing=initial_drawing,
                key=f"subject_canvas_{st.session_state.participant}_{st.session_state.session_code}",
            )

            st.markdown("</div>", unsafe_allow_html=True)

            # Update position in database when user clicks
            if canvas_result and canvas_result.json_data:
                try:
                    objects = canvas_result.json_data.get("objects", [])
                    for obj in reversed(objects):
                        if obj.get("type") == "circle" and obj.get("fill") in [
                            "#EF4444",
                            "#FF0000",
                        ]:
                            x, y = obj.get("left", 0), obj.get("top", 0)

                            # Check if this is a new position (to avoid saving duplicates)
                            if not hasattr(
                                st.session_state, "last_saved_position"
                            ) or st.session_state.last_saved_position != (x, y):

                                # Initialize selection history if it doesn't exist
                                if not hasattr(st.session_state, "selection_history"):
                                    st.session_state.selection_history = []

                                # Add selection to history with order number
                                selection_number = (
                                    len(st.session_state.selection_history) + 1
                                )
                                st.session_state.selection_history.append(
                                    {
                                        "x": x,
                                        "y": y,
                                        "order": selection_number,
                                        "timestamp": time.time(),
                                    }
                                )

                                # Save intermediate click to responses table (for trajectory tracking)
                                success = save_intermediate_click(
                                    st.session_state.participant,
                                    x,
                                    y,
                                    mod_settings["method"],
                                )

                                if success:
                                    st.session_state.last_saved_position = (x, y)

                                # Also update session state for live monitoring
                                update_session_state(
                                    user_type="sub",
                                    participant_id=st.session_state.participant,
                                    method=mod_settings["method"],
                                    x=x,
                                    y=y,
                                )

                                # Store current canvas result for later submission
                                st.session_state.pending_canvas_result = canvas_result
                                st.session_state.pending_method = mod_settings["method"]

                                # Immediately go to questionnaire (no submit button needed)
                                st.session_state.phase = "post_questionnaire"
                                st.rerun()

                            # Display current position and selection history
                            st.write(f"**Current Position:** X: {x:.0f}, Y: {y:.0f}")
                            if hasattr(st.session_state, "selection_history"):
                                st.write(
                                    f"**Selections made:** {len(st.session_state.selection_history)}"
                                )
                            break

                except Exception as e:
                    st.error(f"Error processing selection: {e}")

        else:
            # Multi-ingredient slider interface
            st.markdown("### 🎛️ Adjust Ingredient Concentrations")
            st.write(
                "Use the vertical sliders below to adjust the concentration of each ingredient in your mixture."
            )

            # Enhanced CSS for vertical sliders and mixer-board aesthetic
            st.markdown(
                """
            <style>
            /* Vertical slider container styling */
            .vertical-slider-container {
                background: linear-gradient(145deg, #f8fafc, #e2e8f0);
                border-radius: 16px;
                padding: 24px;
                margin: 16px 0;
                box-shadow: 
                    0 10px 25px rgba(0,0,0,0.1),
                    0 4px 10px rgba(0,0,0,0.05),
                    inset 0 1px 0 rgba(255,255,255,0.5);
                border: 1px solid rgba(255,255,255,0.8);
            }
            
            /* Individual slider column styling */
            .slider-channel {
                background: linear-gradient(145deg, #ffffff, #f1f5f9);
                border-radius: 12px;
                padding: 20px 16px;
                margin: 0 8px;
                box-shadow: 
                    0 4px 12px rgba(0,0,0,0.08),
                    inset 0 1px 0 rgba(255,255,255,0.8),
                    inset 0 -1px 0 rgba(0,0,0,0.05);
                border: 1px solid rgba(226,232,240,0.8);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }
            
            .slider-channel:hover {
                transform: translateY(-2px);
                box-shadow: 
                    0 8px 20px rgba(0,0,0,0.12),
                    inset 0 1px 0 rgba(255,255,255,0.9);
            }
            
            .slider-channel::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg, #3b82f6, #8b5cf6, #06b6d4);
                border-radius: 12px 12px 0 0;
                opacity: 0.7;
            }
            
            /* Slider label styling */
            .slider-label {
                font-weight: 600;
                font-size: 16px;
                color: #1e293b;
                margin-bottom: 12px;
                text-align: center;
                letter-spacing: 0.5px;
                text-shadow: 0 1px 2px rgba(255,255,255,0.8);
            }
            
            /* Value display styling */
            .slider-value {
                font-weight: 500;
                font-size: 14px;
                color: #475569;
                text-align: center;
                margin-top: 8px;
                padding: 6px 12px;
                background: linear-gradient(145deg, #f8fafc, #e2e8f0);
                border-radius: 8px;
                border: 1px solid rgba(203,213,225,0.6);
                box-shadow: inset 0 1px 2px rgba(0,0,0,0.05);
            }
            
            /* Vertical slider component styling */
            .vertical-slider-wrapper {
                display: flex;
                flex-direction: column;
                align-items: center;
                height: 300px;
                margin: 0 auto;
            }
            
            /* Custom styling for the vertical slider component */
            iframe[title="streamlit_vertical_slider.vertical_slider"] {
                border: none !important;
                background: transparent !important;
                width: 100% !important;
                height: 280px !important;
                margin: 10px 0 !important;
            }
            
            /* Dark mode adaptations */
            @media (prefers-color-scheme: dark) {
                .vertical-slider-container {
                    background: linear-gradient(145deg, #1e293b, #0f172a) !important;
                    border: 1px solid rgba(71, 85, 105, 0.5) !important;
                }
                
                .slider-channel {
                    background: linear-gradient(145deg, #334155, #1e293b) !important;
                    border: 1px solid rgba(100, 116, 139, 0.3) !important;
                    box-shadow: 
                        0 4px 12px rgba(0,0,0,0.3),
                        inset 0 1px 0 rgba(148,163,184,0.1) !important;
                }
                
                .slider-channel:hover {
                    background: linear-gradient(145deg, #3f4b5c, #2a3441) !important;
                }
                
                .slider-label {
                    color: #e2e8f0 !important;
                    text-shadow: 0 1px 2px rgba(0,0,0,0.5) !important;
                }
                
                .slider-value {
                    background: linear-gradient(145deg, #1e293b, #0f172a) !important;
                    border: 1px solid rgba(71, 85, 105, 0.5) !important;
                    color: #cbd5e1 !important;
                    box-shadow: inset 0 1px 2px rgba(0,0,0,0.3) !important;
                }
            }
            
            /* Streamlit dark theme overrides */
            [data-theme="dark"] .vertical-slider-container {
                background: linear-gradient(145deg, #1e293b, #0f172a) !important;
                border: 1px solid rgba(71, 85, 105, 0.5) !important;
            }
            
            [data-theme="dark"] .slider-channel {
                background: linear-gradient(145deg, #334155, #1e293b) !important;
                border: 1px solid rgba(100, 116, 139, 0.3) !important;
            }
            
            [data-theme="dark"] .slider-label {
                color: #e2e8f0 !important;
            }
            
            [data-theme="dark"] .slider-value {
                background: linear-gradient(145deg, #1e293b, #0f172a) !important;
                color: #cbd5e1 !important;
                border: 1px solid rgba(71, 85, 105, 0.5) !important;
            }
            
            /* Finish button styling */
            .finish-button-container {
                text-align: center;
                margin-top: 32px;
                padding: 20px;
            }
            
            .stButton > button {
                background: linear-gradient(145deg, #10b981, #059669) !important;
                color: white !important;
                font-weight: 600 !important;
                font-size: 18px !important;
                padding: 12px 32px !important;
                border-radius: 12px !important;
                border: none !important;
                box-shadow: 
                    0 4px 12px rgba(16,185,129,0.3),
                    0 2px 4px rgba(0,0,0,0.1) !important;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                text-transform: uppercase !important;
                letter-spacing: 1px !important;
            }
            
            .stButton > button:hover {
                transform: translateY(-2px) !important;
                box-shadow: 
                    0 8px 20px rgba(16,185,129,0.4),
                    0 4px 8px rgba(0,0,0,0.15) !important;
                background: linear-gradient(145deg, #059669, #047857) !important;
            }
            
            .stButton > button:active {
                transform: translateY(0px) !important;
                box-shadow: 
                    0 2px 8px rgba(16,185,129,0.3),
                    0 1px 3px rgba(0,0,0,0.2) !important;
            }
            </style>
            """,
                unsafe_allow_html=True,
            )

            # Load initial slider positions from database if available
            initial_positions = None
            if hasattr(st.session_state, "participant") and hasattr(
                st.session_state, "session_code"
            ):
                initial_positions = get_initial_slider_positions(
                    session_id=st.session_state.session_code,
                    participant_id=st.session_state.participant,
                )

            # Get current slider values from session state
            # Priority: current_slider_values > database initial positions > random_slider_values > defaults
            if hasattr(st.session_state, "current_slider_values"):
                current_slider_values = st.session_state.current_slider_values
            else:
                # Load initial positions from database first
                if initial_positions and initial_positions.get("percentages"):
                    # Use database initial positions
                    current_slider_values = {}
                    for ingredient in experiment_config["ingredients"]:
                        ingredient_name = ingredient["name"]
                        # Map ingredient names to database positions (need to handle generic names)
                        db_percentages = initial_positions["percentages"]
                        if ingredient_name in db_percentages:
                            current_slider_values[ingredient_name] = db_percentages[
                                ingredient_name
                            ]
                        else:
                            # Try to map by position (fallback for generic names like Ingredient_1)
                            ingredient_index = next(
                                (
                                    i
                                    for i, ing in enumerate(
                                        experiment_config["ingredients"]
                                    )
                                    if ing["name"] == ingredient_name
                                ),
                                None,
                            )
                            if ingredient_index is not None:
                                generic_key = f"Ingredient_{ingredient_index + 1}"
                                current_slider_values[ingredient_name] = (
                                    db_percentages.get(generic_key, 50.0)
                                )
                            else:
                                current_slider_values[ingredient_name] = 50.0
                else:
                    # Try to ensure random values are loaded from database
                    from callback import ensure_random_values_loaded

                    ensure_random_values_loaded(st.session_state.participant)

                    # Use random values if available, otherwise defaults
                    random_values = st.session_state.get("random_slider_values", {})
                    if random_values:
                        current_slider_values = random_values.copy()
                    else:
                        current_slider_values = mixture.get_default_slider_values()

            # Create vertical slider interface with mixer-board styling
            st.markdown(
                '<div class="vertical-slider-container">', unsafe_allow_html=True
            )

            slider_values = {}
            slider_changed = False

            # Create columns for vertical sliders
            num_cols = len(experiment_config["ingredients"])
            cols = st.columns(num_cols)

            for i, ingredient in enumerate(experiment_config["ingredients"]):
                ingredient_name = ingredient["name"]

                with cols[i]:
                    st.markdown('<div class="slider-channel">', unsafe_allow_html=True)

                    # Slider label
                    st.markdown(
                        f'<div class="slider-label">Ingredient {chr(65 + i)}</div>',
                        unsafe_allow_html=True,
                    )

                    # Create vertical slider
                    slider_key = f"ingredient_{ingredient_name}_{st.session_state.participant}_{st.session_state.session_code}"

                    # Use current slider values (which already prioritizes random values)
                    default_value = current_slider_values.get(ingredient_name, 50.0)

                    slider_values[ingredient_name] = svs.vertical_slider(
                        key=slider_key,
                        default_value=default_value,
                        step=1.0,
                        min_value=0.0,
                        max_value=100.0,
                        slider_color="#3b82f6",  # Blue color matching the theme
                        track_color="#e2e8f0",  # Light gray track
                        thumb_color="#1e40af",  # Darker blue thumb
                    )

                    # Show position as percentage with custom styling
                    st.markdown(
                        f'<div class="slider-value">{slider_values[ingredient_name]:.1f}%</div>',
                        unsafe_allow_html=True,
                    )

                    st.markdown("</div>", unsafe_allow_html=True)

                    # Check if this slider changed
                    if slider_values[ingredient_name] != current_slider_values.get(
                        ingredient_name, 50.0
                    ):
                        slider_changed = True

            st.markdown("</div>", unsafe_allow_html=True)

            # Store current slider values and update database for real-time monitoring
            if slider_changed:
                st.session_state.current_slider_values = slider_values

                # Store real-time slider movements for monitoring
                try:

                    # Calculate actual concentrations for monitoring
                    concentrations = mixture.calculate_concentrations_from_sliders(
                        slider_values
                    )

                    # Prepare concentration data for storage
                    slider_concentrations = {}
                    actual_concentrations = {}

                    for ingredient_name, conc_data in concentrations.items():
                        slider_concentrations[ingredient_name] = conc_data[
                            "slider_position"
                        ]
                        actual_concentrations[ingredient_name] = conc_data[
                            "actual_concentration_mM"
                        ]

                    # Store as real-time interaction (not final response)
                    experiment_id = st.session_state.get("experiment_id")
                    if experiment_id and st.session_state.get("participant"):
                        store_user_interaction_v2(
                            experiment_id=experiment_id,
                            participant_id=st.session_state.participant,
                            interaction_type="slider_adjustment",
                            slider_concentrations=slider_concentrations,
                            actual_concentrations=actual_concentrations,
                            is_final_response=False,
                            extra_data={
                                "interface_type": INTERFACE_SLIDERS,
                                "real_time_update": True,
                            },
                        )
                except Exception as e:
                    # Don't break the UI if monitoring storage fails
                    pass

            # Add Finish button with enhanced styling
            st.markdown('<div class="finish-button-container">', unsafe_allow_html=True)

            # Only show finish button if user has made some adjustments or show it by default
            finish_button_clicked = st.button(
                "🎯 Finish Selection",
                type="primary",
                use_container_width=False,
                help="Complete your mixture selection and proceed to the questionnaire",
                key="subject_finish_sliders_button",
            )

            st.markdown("</div>", unsafe_allow_html=True)

            # Handle finish button click
            if finish_button_clicked:
                # Use current slider values (from session state or current values)
                final_slider_values = (
                    st.session_state.current_slider_values
                    if hasattr(st.session_state, "current_slider_values")
                    else slider_values
                )

                # Calculate actual concentrations
                concentrations = mixture.calculate_concentrations_from_sliders(
                    final_slider_values
                )

                # Save to database immediately when Finish button is clicked

                # Calculate reaction time from trial start
                reaction_time_ms = None
                if hasattr(st.session_state, "trial_start_time"):
                    reaction_time_ms = int(
                        (time.perf_counter() - st.session_state.trial_start_time) * 1000
                    )

                # Extract actual mM concentrations for database storage
                ingredient_concentrations = {}
                for ingredient_name, conc_data in concentrations.items():
                    ingredient_concentrations[ingredient_name] = conc_data[
                        "actual_concentration_mM"
                    ]

                # Save slider response to database
                success = save_multi_ingredient_response(
                    participant_id=st.session_state.participant,
                    session_id=st.session_state.get("session_code", "default_session"),
                    method=INTERFACE_SLIDERS,
                    interface_type=INTERFACE_SLIDERS,
                    ingredient_concentrations=ingredient_concentrations,
                    reaction_time_ms=reaction_time_ms,
                    questionnaire_response=None,  # Will be updated in questionnaire phase
                    is_final_response=False,  # Not final until questionnaire completed
                    extra_data={
                        "concentrations_summary": concentrations,
                        "slider_interface": True,
                        "finish_button_clicked": True,
                    },
                )

                if success:
                    # Initialize selection history if it doesn't exist
                    if not hasattr(st.session_state, "selection_history"):
                        st.session_state.selection_history = []

                    # Add final selection to history
                    selection_number = len(st.session_state.selection_history) + 1
                    st.session_state.selection_history.append(
                        {
                            "slider_values": final_slider_values.copy(),
                            "concentrations": concentrations,
                            "order": selection_number,
                            "timestamp": time.time(),
                            "interface_type": "sliders",
                        }
                    )

                    # Store final values and trigger questionnaire
                    st.session_state.current_slider_values = final_slider_values
                    st.session_state.pending_slider_result = {
                        "slider_values": final_slider_values,
                        "concentrations": concentrations,
                    }
                    st.session_state.pending_method = INTERFACE_SLIDERS

                    st.success("✅ Slider selection recorded!")
                    # Go to questionnaire
                    st.session_state.phase = "post_questionnaire"
                    st.rerun()
                else:
                    st.error("❌ Failed to save slider selection. Please try again.")

            # Display selection history
            if (
                hasattr(st.session_state, "selection_history")
                and st.session_state.selection_history
            ):
                st.write(
                    f"**Selections made:** {len(st.session_state.selection_history)}"
                )

                # Show last selection details (for subject reference)
                last_selection = st.session_state.selection_history[-1]
                if "slider_values" in last_selection:
                    st.write("**Last selection:**")
                    for i, (ingredient_name, value) in enumerate(
                        last_selection["slider_values"].items()
                    ):
                        st.write(f"  Ingredient {chr(65 + i)}: {value:.1f}%")

    elif st.session_state.phase == "post_response_message":
        display_phase_status("post_response_message", st.session_state.participant)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            show_preparation_message()

            # Auto-advance to questionnaire after brief delay
            if st.button(
                "Continue to Questionnaire",
                type="primary",
                use_container_width=True,
                key="subject_continue_questionnaire_button",
            ):
                st.session_state.phase = "post_questionnaire"
                st.rerun()

    elif st.session_state.phase == "post_questionnaire":
        display_phase_status("post_questionnaire", st.session_state.participant)

        # Show selection history summary
        if (
            hasattr(st.session_state, "selection_history")
            and st.session_state.selection_history
        ):
            st.info(
                f"You have made {len(st.session_state.selection_history)} selection(s) so far."
            )

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Determine if this should show Final Response button
            # Show Final Response if user has made multiple selections or wants to finish
            show_final = st.checkbox(
                "Ready to submit final response?",
                help="Check this box if you're done making selections and want to submit your final response.",
                key=f"subject_ready_final_response_{st.session_state.participant}_{st.session_state.session_code}",
            )

            responses = render_questionnaire(
                "unified_feedback",
                st.session_state.participant,
                show_final_response=show_final,
            )

            if responses:
                # Store questionnaire responses
                st.session_state.post_questionnaire_responses = responses

                if responses.get("is_final", False):
                    # Complete the trial with final submission
                    success = False

                    # Handle both canvas and slider results
                    if hasattr(st.session_state, "pending_canvas_result"):
                        # Traditional 2D grid submission
                        success = finish_trial(
                            st.session_state.pending_canvas_result,
                            st.session_state.participant,
                            st.session_state.pending_method,
                        )
                    elif hasattr(st.session_state, "pending_slider_result"):
                        # Slider-based submission - update existing record with questionnaire and mark as final
                        slider_data = st.session_state.pending_slider_result

                        # Extract actual mM concentrations for database storage
                        ingredient_concentrations = {}
                        for ingredient_name, conc_data in slider_data[
                            "concentrations"
                        ].items():
                            ingredient_concentrations[ingredient_name] = conc_data[
                                "actual_concentration_mM"
                            ]

                        # Calculate reaction time from trial start
                        reaction_time_ms = None
                        if hasattr(st.session_state, "trial_start_time"):
                            reaction_time_ms = int(
                                (
                                    time.perf_counter()
                                    - st.session_state.trial_start_time
                                )
                                * 1000
                            )

                        # Save final response with questionnaire data
                        success = save_multi_ingredient_response(
                            participant_id=st.session_state.participant,
                            session_id=st.session_state.get(
                                "session_code", "default_session"
                            ),
                            method=INTERFACE_SLIDERS,
                            interface_type=INTERFACE_SLIDERS,
                            ingredient_concentrations=ingredient_concentrations,
                            reaction_time_ms=reaction_time_ms,
                            questionnaire_response=responses,  # Include questionnaire responses
                            is_final_response=True,  # Mark as final
                            extra_data={
                                "concentrations_summary": slider_data["concentrations"],
                                "slider_interface": True,
                                "final_submission": True,
                            },
                        )

                    if success:
                        st.session_state.phase = "done"
                        # Clean up temporary storage
                        cleanup_pending_results()
                        st.rerun()
                    else:
                        st.error(
                            "Failed to submit response. Please contact the moderator."
                        )
                else:
                    # Return to interface for more selections
                    # Clean up temporary storage since we're not submitting yet
                    cleanup_pending_results()

                    st.session_state.phase = "respond"
                    st.success("Continue making selections!")
                    st.rerun()

    elif st.session_state.phase == "done":
        display_phase_status("done", st.session_state.participant)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🎉 Thank You!")
            st.success("Your response has been recorded successfully.")

            if hasattr(st.session_state, "last_response"):
                resp = st.session_state.last_response

                st.markdown("#### 📊 Your Selection:")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Position", f"({resp['x']:.0f}, {resp['y']:.0f})")
                with col_b:
                    st.metric(
                        "⏱️ Response Time", f"{resp.get('reaction_time_ms', 0)} ms"
                    )

            # Auto-refresh disabled to prevent blank screen issues
            st.info(
                "Waiting for next trial... (refresh browser to check for new trials)"
            )

            # Check if moderator started a new trial (only on user action, not automatic)
            if st.button("🔄 Check for New Trial", key="subject_check_new_trial"):
                if is_participant_activated(st.session_state.participant):
                    mod_settings = get_moderator_settings(st.session_state.participant)
                    if mod_settings and mod_settings["created_at"] != getattr(
                        st.session_state, "last_trial_time", None
                    ):
                        st.session_state.phase = (
                            "respond"  # Skip pre-questionnaire for subsequent trials
                        )
                        st.session_state.last_trial_time = mod_settings["created_at"]
                        st.rerun()
                    else:
                        st.info("No new trials available yet.")
                else:
                    st.info("No new trials available yet.")

            # Automatic refresh disabled to prevent screen blanking
            # st.rerun()


def moderator_interface():
    """Multi-device moderator interface with session management."""

    # Validate session
    if not st.session_state.session_code:
        st.error("❌ No active session. Please create or join a session.")
        if st.button("🏠 Return to Home", key="moderator_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    session_info = get_session_info(st.session_state.session_code)
    if not session_info or not session_info["is_active"]:
        st.error("❌ Session expired or invalid.")
        st.session_state.session_code = None
        if st.button("🏠 Return to Home", key="moderator_return_home_invalid_session"):
            st.query_params.clear()
            st.rerun()
        return

    # Header
    create_header(
        f"Moderator Dashboard - {st.session_state.session_code}",
        f"Managing session for {session_info['moderator_name']}",
        "🎮",
    )

    # ===== TOP SECTION: Essential Session Info & Quick Actions =====
    st.markdown("### 📊 Session Overview")

    # Essential session metrics in a clean layout
    overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)

    with overview_col1:
        st.metric("🔑 Session Code", st.session_state.session_code)

    with overview_col2:
        connection_status = get_connection_status(st.session_state.session_code)
        status_text = (
            "Connected"
            if connection_status.get("subject_connected", False)
            else "Waiting"
        )
        status_color = (
            "🟢" if connection_status.get("subject_connected", False) else "🟡"
        )
        st.metric("👤 Subject Status", f"{status_color} {status_text}")

    with overview_col3:
        st.metric("🧪 Current Phase", session_info["current_phase"].title())

    with overview_col4:
        st.metric("⏰ Status", "🟢 Active")

    # ===== SESSION STATE MANAGEMENT =====
    # Initialize session active state
    if "session_active" not in st.session_state:
        st.session_state.session_active = False

    # ===== EXPERIMENT CONFIGURATION & START CONTROLS (HIGHEST PRIORITY) =====
    st.markdown("---")

    # Show different views based on session state
    if not st.session_state.session_active:
        # SETUP MODE: Show experiment configuration
        st.markdown("### 🚀 Experiment Setup & Launch")
    else:
        # MONITORING MODE: Show session controls and configuration summary
        col_config, col_reset = st.columns([3, 1])
        with col_config:
            st.markdown("### 📊 Active Session Configuration")

            # Display current session configuration
            if st.session_state.get("selected_ingredients") and st.session_state.get(
                "ingredient_ranges"
            ):
                config_parts = []
                for ingredient_name in st.session_state.selected_ingredients:
                    if ingredient_name in st.session_state.ingredient_ranges:
                        ranges = st.session_state.ingredient_ranges[ingredient_name]
                        config_parts.append(
                            f"{ingredient_name}: {ranges['min']:.1f}-{ranges['max']:.1f} mM"
                        )

                config_display = " | ".join(config_parts)
                st.info(f"**Ingredients:** {config_display}")

                # Show interface and method info
                num_ingredients = len(st.session_state.selected_ingredients)
                interface_type = "🎯 2D Grid" if num_ingredients == 2 else "🎛️ Slider"
                method_display = (
                    st.session_state.get("mapping_method", "linear")
                    if num_ingredients == 2
                    else INTERFACE_SLIDERS
                )
                st.info(
                    f"**Interface:** {interface_type} | **Method:** {method_display}"
                )

        with col_reset:
            # New Session button to reset back to setup
            if st.button(
                "🆕 New Session",
                type="secondary",
                use_container_width=True,
                key="new_session_button",
                help="End current session and return to setup",
            ):
                # Reset session state
                st.session_state.session_active = False
                if "participant" in st.session_state:
                    clear_participant_session(st.session_state.participant)
                st.success("Session ended. Returning to setup...")
                time.sleep(1)
                st.rerun()

    # Show setup section only if session is not active
    if not st.session_state.session_active:
        # Two-column layout for configuration and start controls
        config_col1, config_col2 = st.columns([2, 1])

        with config_col1:
            # Multi-component mixture configuration
            st.markdown("#### 🧪 Ingredient Configuration")

            # Number of ingredients selection
            # Import ingredient list for selection
            from callback import DEFAULT_INGREDIENT_CONFIG

            # Ingredient selection multiselect
            available_ingredients = [ing["name"] for ing in DEFAULT_INGREDIENT_CONFIG]

            # Initialize selected ingredients in session state if not exists
            if "selected_ingredients" not in st.session_state:
                st.session_state.selected_ingredients = [
                    available_ingredients[0],
                    available_ingredients[1],
                ]  # Default to first 2

            selected_ingredients = st.multiselect(
                "🧪 Select Ingredients:",
                options=available_ingredients,
                default=st.session_state.selected_ingredients,
                help="Choose 2-6 ingredients for your experiment (2 = 2D grid, 3+ = sliders)",
                key="moderator_ingredient_selector",
            )

            # Validation: ensure 2-6 ingredients are selected
            if len(selected_ingredients) < 2:
                st.error("⚠️ Please select at least 2 ingredients")
                selected_ingredients = (
                    st.session_state.selected_ingredients
                )  # Keep previous valid selection
            elif len(selected_ingredients) > 6:
                st.error("⚠️ Maximum 6 ingredients allowed")
                selected_ingredients = selected_ingredients[:6]  # Truncate to 6

            # Update session state
            st.session_state.selected_ingredients = selected_ingredients

        # ===== INGREDIENT RANGE CONFIGURATION =====
        if selected_ingredients:
            st.markdown("#### 📏 Concentration Ranges")
            st.info("Set the minimum and maximum concentrations for each ingredient")

            # Initialize ingredient ranges in session state
            if "ingredient_ranges" not in st.session_state:
                st.session_state.ingredient_ranges = {}

            # Create range selectors for each selected ingredient
            range_cols = st.columns(2)  # Two columns for compact layout
            for i, ingredient_name in enumerate(selected_ingredients):
                col_idx = i % 2
                with range_cols[col_idx]:
                    st.markdown(f"**{ingredient_name}**")

                    # Get default ranges from DEFAULT_INGREDIENT_CONFIG
                    from callback import DEFAULT_INGREDIENT_CONFIG

                    default_ingredient = next(
                        (
                            ing
                            for ing in DEFAULT_INGREDIENT_CONFIG
                            if ing["name"] == ingredient_name
                        ),
                        None,
                    )
                    default_min = (
                        default_ingredient.get("min_concentration", 0.0)
                        if default_ingredient
                        else 0.0
                    )
                    default_max = (
                        default_ingredient.get("max_concentration", 20.0)
                        if default_ingredient
                        else 20.0
                    )

                    # Initialize with defaults if not set
                    if ingredient_name not in st.session_state.ingredient_ranges:
                        st.session_state.ingredient_ranges[ingredient_name] = {
                            "min": default_min,
                            "max": default_max,
                        }

                    current_range = st.session_state.ingredient_ranges[ingredient_name]

                    # Create input fields for min and max
                    min_col, max_col = st.columns(2)
                    with min_col:
                        min_val = st.number_input(
                            f"Min (mM)",
                            min_value=0.0,
                            max_value=1000.0,
                            value=current_range["min"],
                            step=0.1,
                            key=f"min_{ingredient_name}",
                            help=f"Minimum concentration for {ingredient_name}",
                        )
                    with max_col:
                        max_val = st.number_input(
                            f"Max (mM)",
                            min_value=0.1,
                            max_value=1000.0,
                            value=current_range["max"],
                            step=0.1,
                            key=f"max_{ingredient_name}",
                            help=f"Maximum concentration for {ingredient_name}",
                        )

                    # Validation: ensure min < max
                    if min_val >= max_val:
                        st.error(f"⚠️ Min must be less than Max for {ingredient_name}")
                        # Keep previous valid values
                        min_val = current_range["min"]
                        max_val = current_range["max"]

                    # Update session state
                    st.session_state.ingredient_ranges[ingredient_name] = {
                        "min": min_val,
                        "max": max_val,
                    }

            st.markdown("---")

        # Auto-determine number of ingredients from selection
        num_ingredients = len(selected_ingredients)

        # Initialize experiment configuration in session state
        if "experiment_config" not in st.session_state:
            # Ensure DEFAULT_INGREDIENT_CONFIG is available
            from callback import DEFAULT_INGREDIENT_CONFIG

            st.session_state.experiment_config = {
                "num_ingredients": 2,
                "ingredients": DEFAULT_INGREDIENT_CONFIG[:2],
            }

        # Update configuration when number changes
        if num_ingredients != st.session_state.experiment_config["num_ingredients"]:
            # Ensure DEFAULT_INGREDIENT_CONFIG is available
            from callback import DEFAULT_INGREDIENT_CONFIG

            st.session_state.experiment_config["num_ingredients"] = num_ingredients
            st.session_state.experiment_config["ingredients"] = (
                DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
            )

        # Create mixture handler
        mixture = MultiComponentMixture(
            st.session_state.experiment_config["ingredients"]
        )
        interface_type = mixture.get_interface_type()

        # Show interface type
        interface_info = {
            INTERFACE_2D_GRID: "🎯 2D Grid Interface (X-Y coordinates)",
            INTERFACE_SLIDERS: "🎛️ Slider Interface (Independent concentrations)",
        }
        st.info(f"Interface: {interface_info[interface_type]}")

        # Method selection (only for 2D grid)
        if interface_type == INTERFACE_2D_GRID:
            method = st.selectbox(
                "🧮 Mapping Method:",
                ["linear", "logarithmic", "exponential"],
                help="Choose how coordinates map to concentrations",
                key="moderator_mapping_method_selector",
            )

            # Method explanation
            method_info = {
                "linear": "📈 Direct proportional mapping",
                "logarithmic": "📊 Logarithmic scale mapping",
                "exponential": "📉 Exponential scale mapping",
            }
            st.info(method_info[method])
        else:
            method = INTERFACE_SLIDERS
            st.info("🎛️ Slider-based concentration control")

            # Random start option for sliders
            st.session_state.use_random_start = st.checkbox(
                "🎲 Random Starting Positions",
                value=st.session_state.get("use_random_start", False),
                help="Start sliders at randomized positions instead of 50% for each trial",
                key="moderator_random_start_toggle",
            )

        with config_col2:
            st.markdown("#### 🚀 Launch Trial")

            # Show current participant
            participant_display = st.session_state.get("participant", "None selected")
            st.write(f"**Current Participant:** {participant_display}")

            # Start trial button (prominent)
            if st.button(
                "🚀 Start Trial",
                type="primary",
                use_container_width=True,
                key="moderator_start_trial_button",
            ):
                num_ingredients = st.session_state.experiment_config["num_ingredients"]
                success = start_trial(
                    "mod", st.session_state.participant, method, num_ingredients
                )
                if success:
                    clear_canvas_state()  # Clear any previous canvas state
                    st.session_state.session_active = True  # Activate session
                    st.success(f"✅ Trial started for {st.session_state.participant}")
                    time.sleep(1)
                    st.rerun()

            # Reset session button
            if st.button(
                "🔄 Reset Session",
                use_container_width=True,
                key="moderator_reset_session_main_top",
            ):
                if "participant" in st.session_state:
                    success = clear_participant_session(st.session_state.participant)
                    if success:
                        st.success("✅ Session reset successfully!")
                        time.sleep(1)
                        st.rerun()

    # ===== SUBJECT CONNECTION & ACCESS SECTION =====
    st.markdown("---")

    if not connection_status["subject_connected"]:
        with st.expander("📱 Subject Access - QR Code & Session Info", expanded=False):
            st.info(
                "⏳ Waiting for subject to join session... Share the QR code or session code below."
            )

            # Smart URL detection - production first, then localhost for development
            try:
                server_address = st.get_option("browser.serverAddress")
                if server_address and "streamlit.app" in server_address:
                    base_url = f"https://{server_address}"
                elif st.get_option("server.headless"):
                    # Running in cloud/headless mode, use production URL
                    base_url = "https://robotaste.streamlit.app"
                else:
                    # Check if running locally (port 8501 indicates local development)
                    base_url = "http://localhost:8501"  # Local development
            except:
                # Default to production URL for QR codes
                base_url = "https://robotaste.streamlit.app"

            display_session_qr_code(
                st.session_state.session_code, base_url, context="waiting"
            )
    else:
        st.success("✅ Subject device connected and active")

    # ===== ORGANIZED TABS FOR MONITORING & MANAGEMENT =====
    # Only show monitoring tabs when session is active
    if st.session_state.session_active:
        st.markdown("---")

        # Streamlined tabs - keep essential functionality organized
        main_tab1, main_tab2, main_tab3 = st.tabs(
            ["📊 Live Monitor", "📈 Analytics", "⚙️ Settings"]
        )

        with main_tab1:
            # Add refresh button at the top
            col_header, col_refresh = st.columns([4, 1])
            with col_header:
                st.markdown("### 📡 Real-time Monitoring")
            with col_refresh:
                if st.button(
                    "🔄 Refresh",
                    key="live_monitor_refresh",
                    help="Refresh monitoring data",
                    use_container_width=True
                ):
                    st.rerun()

            # Show current participant session info
            st.info(
                "Live monitoring functionality - shows real-time participant responses"
            )

            # Get live or latest submitted response
            current_response = get_live_subject_position(st.session_state.participant)

            col1, col2 = st.columns([2, 1])

            with col1:
                if current_response:
                    interface_type = current_response.get("interface_type", INTERFACE_2D_GRID)
                    method = current_response.get("method", INTERFACE_2D_GRID)
                    status_text = "🎯 Live Subject Position"
                    st.markdown(f"#### {status_text}")

                    # Initialize concentration_data for all interface types
                    concentration_data = current_response.get(
                        "ingredient_concentrations",
                        current_response.get("concentration_data", {})
                    )

                    if interface_type == INTERFACE_SLIDERS or method == INTERFACE_SLIDERS:
                        # Monitor slider interface using new database function
                        st.markdown("**🎛️ Slider Interface Monitoring**")
                        # For slider positions, we can derive from concentrations if needed
                        slider_data = concentration_data
                        is_submitted = current_response.get("is_submitted", False)

                        status_emoji = "✅" if is_submitted else "🔄"
                        status_text = (
                            "Final Submission" if is_submitted else "Live Adjustment"
                        )
                        st.markdown(f"**Status:** {status_emoji} {status_text}")

                        if concentration_data:
                            # Display concentrations and visual representation
                            st.markdown("#### 🧪 Current Ingredient Concentrations")

                            # Create visual representation of concentrations
                            for ingredient_name, conc_mM in concentration_data.items():
                                col_name, col_bar, col_value = st.columns([2, 4, 1])

                                with col_name:
                                    st.markdown(f"**{ingredient_name}**")

                                with col_bar:
                                    # Assume typical range 0-50 mM for progress bar (adjustable)
                                    max_concentration = 50.0
                                    progress_value = min(conc_mM / max_concentration, 1.0)
                                    st.progress(progress_value)

                                with col_value:
                                    st.markdown(f"**{conc_mM:.1f} mM**")
                        else:
                            st.info("🔄 Subject hasn't started adjusting sliders yet")

                            # Show what ingredients are being tested
                            num_ingredients = current_response.get("num_ingredients", 4)
                            if num_ingredients:
                                from callback import DEFAULT_INGREDIENT_CONFIG

                                ingredients = DEFAULT_INGREDIENT_CONFIG[
                                    :num_ingredients
                                ]
                                st.markdown("#### 🧪 Expected Ingredients:")
                                for ing in ingredients:
                                    st.markdown(
                                        f"• {ing['name']} ({ing['min_concentration']}-{ing['max_concentration']} {ing['unit']})"
                                    )

                    else:
                        # Monitor grid interface - show ingredient concentrations instead of coordinates
                        st.markdown("**🎯 Grid Interface Monitoring**")

                        # Show ingredient concentrations for grid interface too
                        if concentration_data:
                            st.markdown("#### 🧪 Current Ingredient Concentrations")

                            for ingredient_name, conc_mM in concentration_data.items():
                                col_name, col_value = st.columns([3, 1])

                                with col_name:
                                    st.markdown(f"**{ingredient_name}**")

                                with col_value:
                                    st.markdown(f"**{conc_mM:.1f} mM**")
                        else:
                            st.info("🔄 No grid data available yet")

                        # Legacy canvas drawing code removed since we no longer use x/y positions
                        # Grid interface now shows concentration data above instead of canvas visualization

                else:
                    st.info("🔍 No participant activity detected yet.")

            with col2:
                if current_response:
                    method = current_response.get("method", INTERFACE_2D_GRID)
                    st.markdown("#### 📊 Live Metrics")

                    if method == INTERFACE_SLIDERS:
                        # Slider-based metrics
                        current_sliders = getattr(
                            st.session_state, "current_slider_values", {}
                        )
                        if current_sliders:
                            st.metric("Interface Type", "🎛️ Multi-Slider")
                            st.metric("Ingredients", str(len(current_sliders)))

                            # Show average position
                            avg_pos = sum(current_sliders.values()) / len(
                                current_sliders
                            )
                            st.metric("Avg Position", f"{avg_pos:.1f}%")
                        else:
                            st.metric("Interface Type", "🎛️ Multi-Slider")
                            st.metric("Status", "⏳ Starting...")
                    else:
                        # Grid-based metrics - show concentration data instead of coordinates
                        if concentration_data:
                            # Show total ingredients metric
                            num_ingredients = len(concentration_data)
                            st.metric("Active Ingredients", f"{num_ingredients}")

                            # Show total concentration
                            total_conc = sum(concentration_data.values())
                            st.metric("Total Concentration", f"{total_conc:.1f} mM")
                        else:
                            st.metric("Interface Type", "🎯 Grid-based")
                            st.metric("Status", "⏳ No data yet")

                    # Show current recipe - works for both live and submitted responses
                    if st.session_state.get("participant"):
                        st.markdown("##### 🧪 Current Recipe")

                        # Get latest recipe for the participant
                        current_recipe = get_latest_recipe_for_participant(
                            st.session_state.participant
                        )

                        if current_recipe and current_recipe != "No recipe yet":
                            # Display the recipe prominently
                            st.success(current_recipe)

                            # Show individual ingredient metrics if available
                            latest_submitted = get_latest_submitted_response(
                                st.session_state.participant
                            )
                            if latest_submitted and latest_submitted.get(
                                "ingredient_concentrations"
                            ):
                                ingredients = latest_submitted[
                                    "ingredient_concentrations"
                                ]

                                # Display metrics for each ingredient
                                for (
                                    ingredient_name,
                                    concentration,
                                ) in ingredients.items():
                                    if concentration > 0:
                                        st.metric(
                                            f"🧪 {ingredient_name}",
                                            f"{concentration:.1f} mM",
                                        )
                        else:
                            # Show placeholder when no recipe is available
                            if current_response.get("is_submitted", False):
                                st.info("⏳ Calculating recipe...")
                            else:
                                st.info("👀 Waiting for participant response...")

                    # Show reaction time if available
                    if current_response.get("is_submitted", False):
                        latest_submitted = get_latest_submitted_response(
                            st.session_state.participant
                        )
                        if latest_submitted and latest_submitted.get(
                            "reaction_time_ms"
                        ):
                            st.metric(
                                "⏱️ Reaction Time",
                                f"{latest_submitted['reaction_time_ms']} ms",
                            )

                    else:
                        # For live positioning, calculate concentrations
                        st.write("here")

                    st.caption(f"Last update: {current_response['created_at']}")
                else:
                    st.write("Waiting for participant data...")

        # Auto-refresh disabled to prevent blank screen issues
        # User can manually refresh using browser or button controls
        # if st.session_state.auto_refresh:
        #     time.sleep(2)
        #     st.rerun()

        with main_tab3:
            st.markdown("### ⚙️ Session Settings")

            # Theme Settings
            st.markdown("#### 🎨 Theme & Display")

            # Force dark mode option for better readability
            force_dark_mode = st.checkbox(
                "🌙 Force Dark Mode (recommended for better readability)",
                value=st.session_state.get("force_dark_mode", False),
                key="moderator_force_dark_mode",
                help="Enables dark mode theme to fix text visibility issues in select boxes",
            )

            if force_dark_mode != st.session_state.get("force_dark_mode", False):
                st.session_state.force_dark_mode = force_dark_mode
                # Add JavaScript to apply theme change
                if force_dark_mode:
                    st.markdown(
                        """
                        <script>
                        document.documentElement.setAttribute('data-theme', 'dark');
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                st.success(
                    "Theme setting updated! Refresh the page to see full effects."
                )

            # Display Settings
            auto_refresh = st.checkbox(
                "🔄 Auto-refresh monitoring (experimental)",
                value=st.session_state.get("auto_refresh", False),
                key="moderator_auto_refresh_setting",
                help="Automatically refresh live monitoring data (may cause performance issues)",
            )
            st.session_state.auto_refresh = auto_refresh

            st.divider()

            # Data Export Section
            st.markdown("#### 📊 Data Export")

            if st.button(
                "📥 Export Session Data (CSV)",
                key="moderator_export_csv",
                help="Download all experiment data for this session as CSV file",
            ):
                try:

                    session_code = st.session_state.get(
                        "session_code", "default_session"
                    )
                    csv_data = export_responses_csv(session_code)

                    if csv_data:
                        # Create download button
                        st.download_button(
                            label="💾 Download CSV File",
                            data=csv_data,
                            file_name=f"robotaste_session_{session_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_csv_data",
                        )
                        st.success("✅ Export data ready for download!")
                    else:
                        st.warning("⚠️ No data found to export for this session.")

                except Exception as e:
                    st.error(f"❌ Error exporting data: {e}")

            # Summary of data that will be exported
            with st.expander("ℹ️ What data gets exported?"):
                st.markdown(
                    """
                **CSV Export includes:**
                - 👤 Participant IDs and session information
                - 🎛️ Interface type (grid vs. slider) and method used
                - 🎲 Random start settings and initial positions
                - 📍 All user interactions (clicks, slider adjustments)
                - ⏱️ Reaction times and timestamps
                - 🧪 Actual concentrations (mM values) for all ingredients
                - ✅ Final response indicators
                - 📋 Questionnaire responses (if any)
                
                **Data is organized chronologically** for easy analysis in research tools like R, Python, or Excel.
                """
                )

            st.divider()

            # Debug: Check database directly
            with st.expander("🔍 Debug Database"):
                if st.button(
                    "Check Responses Table", key="moderator_check_responses_debug"
                ):
                    responses_df = get_participant_responses(
                        st.session_state.participant
                    )
                    st.write(
                        f"Found {len(responses_df)} responses for {st.session_state.participant}"
                    )
                    if not responses_df.empty:
                        st.dataframe(responses_df)
                    else:
                        st.write("No responses found in database")

                    # Also check all participants
                    all_participants = get_all_participants()
                    st.write(f"All participants in database: {all_participants}")

                # Get response history
                responses_df = get_participant_responses(
                    st.session_state.participant, limit=50
                )

    if not st.session_state.session_active:
        # Show message when session is not active
        st.info(
            "👆 Configure your experiment above and click 'Start Trial' to begin monitoring."
        )


def landing_page():
    """Multi-device landing page with session management."""
    create_header("RoboTaste Multi-Device System", "Create or join a session", "🧪")

    # Check URL parameters for session joining
    role = st.query_params.get("role", "")
    session_code = st.query_params.get("session", "")

    if role and session_code:
        # Direct access via URL with session code
        if role == "subject":
            if join_session(session_code):
                sync_session_state(session_code, "subject")
                st.success(f"✅ Joined session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ Invalid or expired session code: {session_code}")
                st.query_params.clear()
                st.rerun()
        elif role == "moderator":
            session_info = get_session_info(session_code)
            if session_info and session_info["is_active"]:
                sync_session_state(session_code, "moderator")
                st.success(f"✅ Resumed moderator session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"❌ Invalid or expired session code: {session_code}")
                st.query_params.clear()
                st.rerun()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Tab selection for different entry modes
        tab1, tab2, tab3 = st.tabs(["🎮 New Session", "📱 Join Session", "ℹ️ About"])

        with tab1:
            st.markdown("### 🔧 Create New Session (Moderator)")
            st.info(
                "Start a new experiment session that subjects can join using a session code or QR code."
            )

            moderator_name = st.text_input(
                "Moderator Name:",
                value="Research Team",
                help="This will be displayed to subjects",
                key="landing_moderator_name_input",
            )

            if st.button(
                "🚀 Create New Session",
                type="primary",
                use_container_width=True,
                key="landing_create_session_button",
            ):
                new_session_code = create_session(moderator_name)

                # Properly sync session state
                if sync_session_state(new_session_code, "moderator"):
                    st.query_params.update(
                        {"role": "moderator", "session": new_session_code}
                    )
                    st.success(f"✅ Session created: {new_session_code}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to create session. Please try again.")

        with tab2:
            st.markdown("### 👤 Join Existing Session (Subject)")
            st.info(
                "Enter the session code provided by your moderator to join an active experiment."
            )

            input_session_code = st.text_input(
                "Session Code:",
                placeholder="e.g., ABC123",
                max_chars=6,
                help="6-character code provided by the moderator",
                key="landing_session_code_input",
            ).upper()

            if st.button(
                "📱 Join Session",
                type="primary",
                use_container_width=True,
                key="landing_join_session_button",
            ):
                if input_session_code and len(input_session_code) == 6:
                    if join_session(input_session_code):
                        st.session_state.session_code = input_session_code
                        st.session_state.device_role = "subject"
                        st.query_params.update(
                            {"role": "subject", "session": input_session_code}
                        )
                        st.success(f"✅ Joined session {input_session_code}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid or expired session code")
                else:
                    st.error("❌ Please enter a valid 6-character session code")

        with tab3:
            st.markdown("### 📖 About RoboTaste")
            st.markdown(
                """
            **Multi-Device Taste Preference Experiment Platform**
            
            **Features:**
            - 🎯 **2D Grid Interface**: Binary mixtures with coordinate selection
            - 🎛️ **Vertical Sliders**: Multi-component concentration control
            - 📱 **Multi-Device**: Moderator dashboard + subject interface
            - 📊 **Real-time Sync**: Live monitoring and data collection
            - ☁️ **Cloud Ready**: Deployed on Streamlit Cloud
            
            **How to Use:**
            1. **Moderator**: Create a new session from any device
            2. **Subject**: Join using the 6-digit session code or QR code
            3. **Experiment**: Real-time synchronized taste preference testing
            
            **Device Requirements:**
            - Moderator: Desktop/laptop with large screen
            - Subject: Any device (phone, tablet, laptop)
            """
            )

            # Show active sessions for debugging (admin view)
            if st.button(
                "🔍 Show Active Sessions (Debug)", key="landing_debug_active_sessions"
            ):
                from session_manager import get_active_sessions

                sessions = get_active_sessions()
                if sessions:
                    st.write(f"**{len(sessions)} active sessions:**")
                    for session in sessions:
                        st.write(
                            f"- {session['session_code']}: {session['moderator_name']} "
                            f"({'✅ Subject Connected' if session['subject_connected'] else '⏳ Waiting for Subject'})"
                        )
                else:
                    st.write("No active sessions found")


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
