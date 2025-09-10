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
    DEFAULT_INGREDIENT_CONFIG,
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
    get_live_subject_position,
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

        # Determine interface type based on moderator's configuration
        num_ingredients = mod_settings.get("num_ingredients", 2)
        experiment_config = {
            "num_ingredients": num_ingredients,
            "ingredients": DEFAULT_INGREDIENT_CONFIG[:num_ingredients],
        }

        mixture = MultiComponentMixture(experiment_config["ingredients"])
        interface_type = mixture.get_interface_type()

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

                initial_drawing = create_canvas_drawing(
                    mod_settings["x_position"],
                    mod_settings["y_position"],
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

            # Get current slider values from session state
            current_slider_values = getattr(
                st.session_state,
                "current_slider_values",
                mixture.get_default_slider_values(),
            )

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

            # Store current slider values (but don't trigger questionnaire automatically)
            if slider_changed:
                st.session_state.current_slider_values = slider_values

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
                st.session_state.pending_method = "slider_based"

                # Go to questionnaire
                st.session_state.phase = "post_questionnaire"
                st.rerun()

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
                        # Slider-based submission - save concentration data
                        slider_data = st.session_state.pending_slider_result
                        success = save_slider_trial(
                            st.session_state.participant,
                            slider_data["concentrations"],
                            st.session_state.pending_method,
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

    # Session overview dashboard
    st.markdown("### 📊 Session Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔑 Session Code", st.session_state.session_code)

    with col2:
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

    with col3:
        st.metric("🧪 Current Phase", session_info["current_phase"].title())

    with col4:
        st.metric("⏰ Status", "🟢 Active")

    # Display QR Code for easy subject access
    display_session_qr_code(st.session_state.session_code, context="dashboard")

    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🎮 Control Panel", "📊 Live Monitor", "📈 Analytics", "⚙️ Settings"]
    )

    with tab1:
        st.markdown("### 🚀 Experiment Control")

        control_col1, control_col2 = st.columns(2)

        with control_col1:
            st.markdown("#### 🎮 Session Controls")
            if st.button("🔄 Reset Session Phase", key="moderator_reset_session_phase"):
                update_session_activity(st.session_state.session_code, phase="reset")
                st.success("Session phase reset!")

            if st.button("⏹️ End Session", key="moderator_end_session"):
                st.warning("Session will be deactivated.")

        with control_col2:
            st.markdown("#### 📊 Data Management")
            if st.button("📥 Download Responses", key="moderator_download_responses"):
                st.success("Data download initiated!")

            if st.button("🗑️ Clear Session Data", key="moderator_clear_session_data"):
                st.warning("This will clear all response data!")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            """
            <div class="metric-card">
                <h4>🔑 Session Code</h4>
                <p style="font-size: 24px; font-weight: bold;">{}</p>
            </div>
            """.format(
                st.session_state.session_code
            ),
            unsafe_allow_html=True,
        )

    with col2:
        connection_status = get_connection_status(st.session_state.session_code)
        status_icon = "✅" if connection_status["subject_connected"] else "⏳"
        status_text = (
            "Connected" if connection_status["subject_connected"] else "Waiting"
        )
        st.markdown(
            """
            <div class="metric-card">
                <h4>👤 Subject Status</h4>
                <p>{} {}</p>
            </div>
            """.format(
                status_icon, status_text
            ),
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            """
            <div class="metric-card">
                <h4>🧪 Current Phase</h4>
                <p>{}</p>
            </div>
            """.format(
                session_info["current_phase"].title()
            ),
            unsafe_allow_html=True,
        )

    with col4:
        active_sessions = len([s for s in session_info if True])  # Simple count for now
        st.markdown(
            """
            <div class="metric-card">
                <h4>⏰ Session Age</h4>
                <p>{}</p>
            </div>
            """.format(
                "Active"
            ),
            unsafe_allow_html=True,
        )

    # Connection status and QR code section
    if not connection_status["subject_connected"]:
        st.warning("⏳ Waiting for subject to join session...")

        # Display QR code and session info for subject to join
        with st.expander("📱 Share with Subject", expanded=True):
            # Detect if we're running on Streamlit Cloud
            try:
                server_address = st.get_option("browser.serverAddress")
                if server_address and "streamlit.app" in server_address:
                    base_url = f"https://{server_address}"
                elif st.get_option("server.headless"):
                    # Running in cloud/headless mode, construct URL
                    base_url = (
                        "https://your-app.streamlit.app"  # Replace with actual URL
                    )
                else:
                    base_url = "http://localhost:8501"  # Local development
            except:
                base_url = "http://localhost:8501"  # Fallback

            display_session_qr_code(
                st.session_state.session_code, base_url, context="waiting"
            )
    else:
        st.success("✅ Subject device connected and active")

    # Configuration display panel
    st.markdown("### ⚙️ Current Session Configuration")

    # Initialize experiment configuration if not exists
    if "experiment_config" not in st.session_state:
        st.session_state.experiment_config = {
            "num_ingredients": 2,
            "ingredients": DEFAULT_INGREDIENT_CONFIG[:2],
        }

    config_col1, config_col2 = st.columns([1, 1])

    with config_col1:
        st.markdown(
            """
            <div class="status-card">
                <h3>🧪 Mixture Configuration</h3>
                <p><strong>Number of Ingredients:</strong> {}</p>
                <p><strong>Interface Type:</strong> {}</p>
                <p><strong>Mapping Method:</strong> {}</p>
            </div>
            """.format(
                st.session_state.experiment_config.get("num_ingredients", 2),
                (
                    "2D Grid (X-Y)"
                    if st.session_state.experiment_config.get("num_ingredients", 2) == 2
                    else "Vertical Sliders"
                ),
                (
                    "Linear/Log/Exp"
                    if st.session_state.experiment_config.get("num_ingredients", 2) == 2
                    else "Slider-based"
                ),
            ),
            unsafe_allow_html=True,
        )

    with config_col2:
        st.markdown(
            """
            <div class="status-card">
                <h3>📊 Concentration Ranges</h3>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Show concentration ranges for current configuration
        ingredients = st.session_state.experiment_config.get(
            "ingredients", DEFAULT_INGREDIENT_CONFIG[:2]
        )
        for i, ingredient in enumerate(ingredients[:4]):  # Show first 4 ingredients
            ingredient_label = (
                f"Ingredient {chr(65 + i)}"
                if len(ingredients) > 2
                else ingredient["name"].title()
            )
            st.write(
                f"**{ingredient_label}:** {ingredient['min_concentration']:.3f} - {ingredient['max_concentration']:.3f} mM"
            )

    # Session URLs section
    st.markdown("### 🔗 Session Access URLs")

    urls_col1, urls_col2 = st.columns([1, 1])

    with urls_col1:
        try:
            server_address = st.get_option("browser.serverAddress")
            if server_address and "streamlit.app" in server_address:
                base_url = f"https://{server_address}"
            else:
                base_url = "http://localhost:8501"
        except:
            base_url = "http://localhost:8501"

        session_urls = generate_session_urls(st.session_state.session_code, base_url)

        st.markdown("**Moderator URL:**")
        st.code(session_urls["moderator"], language="text")

    with urls_col2:
        st.markdown("**Subject URL:**")
        st.code(session_urls["subject"], language="text")

        if st.button("📋 Copy Subject URL", key="moderator_copy_subject_url"):
            st.success("URL copied! Share with participants.")

    # Session management controls
    st.markdown("### 🎮 Session Controls")

    control_col1, control_col2, control_col3, control_col4 = st.columns(4)

    with control_col1:
        if st.button(
            "🔄 Reset Session",
            help="Reset current session for selected participant",
            use_container_width=True,
            key="moderator_reset_session_main",
        ):
            if "participant" in st.session_state:
                success = clear_participant_session(st.session_state.participant)
                if success:
                    st.success("✅ Session reset successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Failed to reset session")
            else:
                st.warning("⚠️ No participant selected")

    with control_col2:
        if st.button(
            "🛑 End Session",
            help="End current session for all participants",
            use_container_width=True,
            key="moderator_end_session_all",
        ):
            # Here you would implement session ending logic
            st.warning("🚧 Session ending functionality coming soon")

    with control_col3:
        if st.button(
            "📥 Download Data",
            help="Export session data to CSV",
            use_container_width=True,
            key="moderator_download_data_main",
        ):
            if "participant" in st.session_state:
                responses_df = get_participant_responses(st.session_state.participant)
                if not responses_df.empty:
                    csv = responses_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "💾 Download CSV",
                        csv,
                        file_name=f"session_{st.session_state.session_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("📭 No data available to download")
            else:
                st.warning("⚠️ No participant selected")

    with control_col4:
        stats = get_database_stats()
        if st.button(
            f"📊 Stats ({stats['total_responses']})",
            help="View detailed session statistics",
            use_container_width=True,
            key="moderator_view_stats",
        ):
            st.info(f"📈 Total responses: {stats['total_responses']}")

    # Sidebar controls
    with st.sidebar:
        st.markdown("### 🎮 Quick Controls")

        # Accessibility options
        with st.expander("♿ Accessibility"):
            st.session_state.high_contrast = st.checkbox(
                "High Contrast Mode",
                value=st.session_state.get("high_contrast", False),
                help="Increase contrast for better visibility",
                key="moderator_high_contrast_toggle",
            )

            # High contrast styles are applied via CSS, no rerun needed

        st.divider()

        # Participant selection
        participants = get_all_participants()
        if not participants:
            participants = [st.session_state.participant]

        selected_participant = st.selectbox(
            "👤 Select Participant:",
            participants,
            index=(
                participants.index(st.session_state.participant)
                if st.session_state.participant in participants
                else 0
            ),
            key="moderator_select_participant",
        )

        if selected_participant != st.session_state.participant:
            st.session_state.participant = selected_participant

        # Add new participant
        with st.expander("➕ Add New Participant"):
            new_participant = st.text_input(
                "New Participant ID:", key="moderator_new_participant_input"
            )
            if (
                st.button(
                    "Add",
                    use_container_width=True,
                    key="moderator_add_participant_button",
                )
                and new_participant
            ):
                st.session_state.participant = new_participant
                st.rerun()

        st.divider()

        # Auto-refresh control
        st.session_state.auto_refresh = st.checkbox(
            "🔄 Auto-refresh",
            value=st.session_state.auto_refresh,
            key="moderator_auto_refresh_toggle",
        )

        # Database stats
        stats = get_database_stats()
        st.markdown("### 📊 System Stats")
        st.metric("Active Sessions", stats["active_sessions"])
        st.metric("Total Responses", stats["total_responses"])
        st.metric("Participants", stats["participants_with_data"])

    # Main dashboard
    tab1, tab2, tab3 = st.tabs(["🎮 Control Panel", "📊 Live Monitor", "📈 Analytics"])

    with tab1:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("### 🚀 Start New Trial")

            # Multi-component mixture configuration
            st.markdown("#### 🧪 Ingredient Configuration")

            # Number of ingredients selection
            num_ingredients = st.selectbox(
                "Number of ingredients:",
                [2, 3, 4, 5, 6],
                help="Select number of ingredients in the mixture (2 = 2D grid, 3+ = sliders)",
                key="moderator_num_ingredients_selector",
            )

            # Initialize experiment configuration in session state
            if "experiment_config" not in st.session_state:
                st.session_state.experiment_config = {
                    "num_ingredients": 2,
                    "ingredients": DEFAULT_INGREDIENT_CONFIG[:2],
                }

            # Update configuration when number changes
            if num_ingredients != st.session_state.experiment_config["num_ingredients"]:
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

            # Ingredient concentration ranges (for moderator only)
            with st.expander("⚙️ Concentration Ranges (Advanced)", expanded=False):
                st.write("**Concentration ranges for solution preparation:**")
                for i, ingredient in enumerate(
                    st.session_state.experiment_config["ingredients"]
                ):
                    st.write(
                        f"**{ingredient['name']}:** {ingredient['min_concentration']:.3f} - {ingredient['max_concentration']:.3f} mM"
                    )

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
                method = "slider_based"
                st.info("🎛️ Slider-based concentration control")

            # Start trial button
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
                    st.success(f"✅ Trial started for {st.session_state.participant}")
                    time.sleep(1)
                    st.rerun()

        with col2:
            st.markdown("### ⚙️ Session Management")

            # Current participant info
            mod_settings = get_moderator_settings(st.session_state.participant)
            if mod_settings:
                st.markdown(
                    f"""
                <div class="success-card">
                    <h4>✅ Active Session</h4>
                    <p><strong>Method:</strong> {mod_settings['method']}</p>
                    <p><strong>Start Position:</strong> ({mod_settings['x_position']:.0f}, {mod_settings['y_position']:.0f})</p>
                    <p><strong>Started:</strong> {mod_settings['created_at']}</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                <div class="warning-card">
                    <h4>⏳ No Active Session</h4>
                    <p>Start a new trial to activate this participant.</p>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            # Reset session
            if st.button(
                "🔄 Reset Session",
                use_container_width=True,
                key="moderator_reset_session_sidebar",
            ):
                success = clear_participant_session(st.session_state.participant)
                if success:
                    st.success("Session reset successfully!")
                    time.sleep(1)
                    st.rerun()

    with tab2:
        st.markdown("### 📡 Real-time Monitoring")

        # Get live or latest submitted response
        current_response = get_live_subject_position(st.session_state.participant)

        col1, col2 = st.columns([2, 1])

        with col1:
            if current_response:
                # is_submitted = current_response.get("is_submitted", False)
                status_text = "🎯 Live Subject Position"
                st.markdown(f"#### {status_text}")

                # Create exact replica of subject's grid
                # Get moderator settings to match the initial drawing
                mod_settings = get_moderator_settings(st.session_state.participant)
                if mod_settings:
                    # Create the same canvas as subject sees (no selection history for monitoring)
                    initial_drawing = create_canvas_drawing(
                        current_response["x_position"], current_response["y_position"]
                    )

                    # Display read-only version of subject's canvas
                    st.markdown(
                        '<div class="canvas-container">', unsafe_allow_html=True
                    )
                    st_canvas(
                        fill_color="#EF4444",
                        stroke_width=3,
                        stroke_color="#DC2626",
                        background_color="white",
                        update_streamlit=False,  # Make it truly read-only
                        height=CANVAS_SIZE,
                        width=CANVAS_SIZE,
                        drawing_mode="transform",  # Disable drawing
                        initial_drawing=initial_drawing,
                        key=f"monitoring_canvas_{st.session_state.participant}_{hash(str(current_response))}",
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

                    # Show status
                    # if is_submitted:
                    #     st.success("✅ Response submitted and recorded")
                    # else:
                    #     st.info("🔄 Subject is currently positioning...")

                else:
                    st.info("🔍 No active session to monitor.")

            else:
                st.info("🔍 No participant activity detected yet.")

        with col2:
            if current_response:
                st.markdown("#### 📊 Live Metrics")

                # Position metrics
                st.metric("X Position", f"{current_response['x_position']:.0f}")
                st.metric("Y Position", f"{current_response['y_position']:.0f}")

                # If this is a submitted response, show concentration data
                if current_response.get("is_submitted", False):
                    # Get concentration data from the response record
                    latest_submitted = get_latest_submitted_response(
                        st.session_state.participant
                    )
                    if latest_submitted:
                        st.metric(
                            "🍯 Sugar",
                            f"{latest_submitted['sugar_concentration']:.2f} mM",
                        )
                        st.metric(
                            "🧂 Salt",
                            f"{latest_submitted['salt_concentration']:.2f} mM",
                        )

                        # Solution prep info
                        st.markdown("##### 🧪 Solution Prep")
                        sugar_g = (
                            (latest_submitted["sugar_concentration"] / 1000.0)
                            * 342.3
                            * 0.1
                        )
                        salt_g = (
                            (latest_submitted["salt_concentration"] / 1000.0)
                            * 58.44
                            * 0.1
                        )
                        st.caption(f"Sugar: {sugar_g:.4f}g/100ml")
                        st.caption(f"Salt: {salt_g:.4f}g/100ml")

                        if latest_submitted["reaction_time_ms"]:
                            st.metric(
                                "⏱️ Reaction Time",
                                f"{latest_submitted['reaction_time_ms']} ms",
                            )

                else:
                    # For live positioning, calculate concentrations
                    mod_settings = get_moderator_settings(st.session_state.participant)
                    if mod_settings:
                        conc_info = get_concentration_display(
                            current_response["x_position"],
                            current_response["y_position"],
                            mod_settings["method"],
                        )

                        if "error" not in conc_info:
                            st.metric("🍯 Sugar", f"{conc_info['sugar_mm']:.2f} mM")
                            st.metric("🧂 Salt", f"{conc_info['salt_mm']:.2f} mM")

                            # Also show masses for solution preparation
                            st.markdown("##### 🧪 Solution Prep")
                            st.caption(
                                f"Sugar: {conc_info['sugar_g_per_100ml']:.4f}g/100ml"
                            )
                            st.caption(
                                f"Salt: {conc_info['salt_g_per_100ml']:.4f}g/100ml"
                            )

                st.caption(f"Last update: {current_response['created_at']}")
            else:
                st.write("Waiting for participant data...")

        # Auto-refresh disabled to prevent blank screen issues
        # User can manually refresh using browser or button controls
        # if st.session_state.auto_refresh:
        #     time.sleep(2)
        #     st.rerun()

    with tab3:
        st.markdown("### 📈 Response Analytics")

        # Debug: Check database directly
        with st.expander("🔍 Debug Database"):
            if st.button(
                "Check Responses Table", key="moderator_check_responses_debug"
            ):
                responses_df = get_participant_responses(st.session_state.participant)
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
        responses_df = get_participant_responses(st.session_state.participant, limit=50)

        if not responses_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 📊 Response Summary")
                st.dataframe(
                    responses_df[
                        [
                            "x_position",
                            "y_position",
                            "sugar_concentration",
                            "salt_concentration",
                            "method",
                            "created_at",
                        ]
                    ].head(10),
                    use_container_width=True,
                )

                # Download data
                csv = responses_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "📥 Download All Data",
                    csv,
                    file_name=f"responses_{st.session_state.participant}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )

            with col2:
                st.markdown("#### 📈 Response Patterns")

                # Position scatter plot
                if len(responses_df) > 1:
                    fig = px.scatter(
                        responses_df,
                        x="x_position",
                        y="y_position",
                        color="method",
                        title="Response Positions Over Time",
                        hover_data=["sugar_concentration", "salt_concentration"],
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)

                # Stats
                st.markdown("#### 📊 Statistics")
                col2a, col2b = st.columns(2)
                with col2a:
                    st.metric("Total Responses", len(responses_df))
                    st.metric(
                        "Avg Sugar (mM)",
                        f"{responses_df['sugar_concentration'].mean():.2f}",
                    )
                with col2b:
                    if "reaction_time_ms" in responses_df.columns:
                        st.metric(
                            "Avg RT (ms)",
                            f"{responses_df['reaction_time_ms'].mean():.0f}",
                        )
                    st.metric(
                        "Avg Salt (mM)",
                        f"{responses_df['salt_concentration'].mean():.2f}",
                    )
        else:
            st.info("📭 No response data available for this participant yet.")


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
