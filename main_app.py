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
   - Supports: Configurable ingredient library (up to 6 ingredients)

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
    save_multi_ingredient_response,
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
        /* Colors */
        --primary-color: #4f46e5;
        --primary-light: #818cf8;
        --primary-dark: #3730a3;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --error-color: #ef4444;
        
        /* Text */
        --text-primary: #1f2937;
        --text-secondary: #6b7280;
        
        /* Backgrounds */
        --bg-primary: #ffffff;
        --bg-secondary: #f9fafb;
        --border-color: #e5e7eb;
        --shadow-light: rgba(0, 0, 0, 0.1);
        
        /* Transitions */
        --transition-base: all 0.2s ease;
        
        /* Spacing */
        --spacing-sm: 0.5rem;
        --spacing-md: 1rem;
        --spacing-lg: 1.5rem;
        
        /* Border Radius */
        --radius-sm: 8px;
        --radius-md: 12px;
    }
    
    /* Dark mode variables */
    [data-theme="dark"], .stApp[data-theme="dark"], @media (prefers-color-scheme: dark) {
        --text-primary: #f9fafb;
        --text-secondary: #d1d5db;
        --bg-primary: #1f2937;
        --bg-secondary: #374151;
        --border-color: #4b5563;
        --shadow-light: rgba(255, 255, 255, 0.1);
    }
    
    /* Base styles */
    .main-header, .status-card, .success-card, .warning-card, .metric-card {
        padding: var(--spacing-lg);
        border-radius: var(--radius-md);
        box-shadow: 0 2px 8px var(--shadow-light);
        transition: var(--transition-base);
    }
    
    /* Header */
    .main-header {
        background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    
    .main-header h1 { font-size: 2rem; font-weight: 600; margin: 0; }
    .main-header p { font-size: 1.1rem; opacity: 0.9; margin-top: var(--spacing-sm); }
    
    /* Cards */
    .card-base {
        background: var(--bg-secondary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: var(--spacing-lg);
        margin: var(--spacing-md) 0;
        transition: var(--transition-base);
    }
    
    .status-card, .success-card, .warning-card { 
        @extend .card-base;
        border-left-width: 4px;
    }
    
    .status-card { border-left-color: var(--primary-color); }
    .success-card { border-left-color: var(--success-color); }
    .warning-card { border-left-color: var(--warning-color); }
    
    /* Card Typography */
    .status-card h3, .success-card h4, .warning-card h4 {
        margin: 0 0 var(--spacing-sm) 0;
        font-weight: 600;
    }
    
    .status-card p, .success-card p, .warning-card p {
        color: var(--text-secondary);
        margin: calc(var(--spacing-sm)/2) 0;
    }
    
    /* Metric Cards */
    .metric-card {
        background: var(--bg-primary);
        color: var(--text-primary);
        border: 1px solid var(--border-color);
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px var(--shadow-light);
    }
    
    /* Canvas */
    .canvas-container {
        border: 2px solid var(--border-color);
        border-radius: var(--radius-md);
        padding: var(--spacing-lg);
        background: var(--bg-primary);
        box-shadow: 0 4px 12px var(--shadow-light);
        transition: var(--transition-base);
    }
    
    .canvas-container:hover {
        border-color: var(--primary-light);
    }
    
    /* Streamlit Components */
    .stButton > button,
    .stTextInput > div > div > input,
    .stSelectbox > div > div > div,
    .stAlert {
        border-radius: var(--radius-sm);
        border: 1px solid var(--border-color);
        background: var(--bg-primary);
        color: var(--text-primary);
        transition: var(--transition-base);
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, var(--primary-color), var(--primary-dark));
        color: white;
        font-weight: 500;
        padding: var(--spacing-md) var(--spacing-lg);
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px var(--shadow-light);
    }
    
    /* Accessibility */
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
    
    button:focus, input:focus, select:focus {
        outline: 2px solid var(--primary-color);
        outline-offset: 2px;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        :root {
            --spacing-lg: 1rem;
            --spacing-md: 0.75rem;
            --spacing-sm: 0.375rem;
        }
        
        .main-header h1 { font-size: 1.5rem; }
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
        # Ensure DEFAULT_INGREDIENT_CONFIG is available
        from callback import DEFAULT_INGREDIENT_CONFIG

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
            /* Base container styling */
            .vertical-slider-container {
                background: linear-gradient(145deg, #f8fafc, #e2e8f0);
                border-radius: 16px;
                padding: 24px;
                margin: 16px 0;
                box-shadow: 0 10px 25px rgba(0,0,0,0.1), 0 4px 10px rgba(0,0,0,0.05);
                border: 1px solid rgba(255,255,255,0.8);
            }
            
            /* Slider channel styling */
            .slider-channel {
                background: linear-gradient(145deg, #ffffff, #f1f5f9);
                border-radius: 12px;
                padding: 20px 16px;
                margin: 0 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                border: 1px solid rgba(226,232,240,0.8);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
                overflow: hidden;
            }
            
            .slider-channel:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.12);
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
            
            /* Text elements */
            .slider-label {
                font-weight: 600;
                font-size: 16px;
                color: #1e293b;
                margin-bottom: 12px;
                text-align: center;
                letter-spacing: 0.5px;
            }
            
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
            }
            
            /* Vertical slider specifics */
            .vertical-slider-wrapper {
                display: flex;
                flex-direction: column;
                align-items: center;
                height: 300px;
                margin: 0 auto;
            }
            
            iframe[title="streamlit_vertical_slider.vertical_slider"] {
                border: none !important;
                background: transparent !important;
                width: 100% !important;
                height: 280px !important;
                margin: 10px 0 !important;
            }
            
            /* Dark mode */
            @media (prefers-color-scheme: dark), [data-theme="dark"] {
                .vertical-slider-container {
                    background: linear-gradient(145deg, #1e293b, #0f172a);
                    border-color: rgba(71, 85, 105, 0.5);
                }
                
                .slider-channel {
                    background: linear-gradient(145deg, #334155, #1e293b);
                    border-color: rgba(100, 116, 139, 0.3);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                }
                
                .slider-channel:hover {
                    background: linear-gradient(145deg, #3f4b5c, #2a3441);
                }
                
                .slider-label {
                    color: #e2e8f0;
                }
                
                .slider-value {
                    background: linear-gradient(145deg, #1e293b, #0f172a);
                    border-color: rgba(71, 85, 105, 0.5);
                    color: #cbd5e1;
                }
            }
            
            /* Button styling */
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
                box-shadow: 0 4px 12px rgba(16,185,129,0.3);
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
                text-transform: uppercase !important;
                letter-spacing: 1px !important;
            }
            
            .stButton > button:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 20px rgba(16,185,129,0.4) !important;
                background: linear-gradient(145deg, #059669, #047857) !important;
            }
            
            .stButton > button:active {
                transform: translateY(0px) !important;
                box-shadow: 0 2px 8px rgba(16,185,129,0.3) !important;
            }
            </style>
            """,
                unsafe_allow_html=True,
            )

            # Get current slider values from session state
            # Priority: current_slider_values > random_slider_values > defaults
            if hasattr(st.session_state, "current_slider_values"):
                current_slider_values = st.session_state.current_slider_values
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

                    # Slider label - show generic label for blinding
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
                    method="slider_based",
                    interface_type="slider_based",
                    ingredient_concentrations=ingredient_concentrations,
                    reaction_time_ms=reaction_time_ms,
                    questionnaire_response=None,  # Will be updated in questionnaire phase
                    is_final_response=False,  # Not final until questionnaire completed
                    extra_data={
                        "concentrations_summary": concentrations,
                        "slider_interface": True,
                        "finish_button_clicked": True,
                        "ingredient_mapping": {
                            f"Ingredient_{chr(65+i)}": ingredient["name"]
                            for i, ingredient in enumerate(
                                experiment_config["ingredients"]
                            )
                        },
                        "selected_ingredients": [
                            ing["name"] for ing in experiment_config["ingredients"]
                        ],
                    },
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

                        # Get experiment config from session state
                        experiment_config = st.session_state.get(
                            "experiment_config", {}
                        )

                        # Build extra data with ingredient mapping
                        extra_data = {
                            "concentrations_summary": slider_data["concentrations"],
                            "slider_interface": True,
                            "final_submission": True,
                        }

                        # Add ingredient mapping if experiment config is available
                        if experiment_config and "ingredients" in experiment_config:
                            extra_data["ingredient_mapping"] = {
                                f"Ingredient_{chr(65+i)}": ingredient["name"]
                                for i, ingredient in enumerate(
                                    experiment_config["ingredients"]
                                )
                            }
                            extra_data["selected_ingredients"] = [
                                ing["name"] for ing in experiment_config["ingredients"]
                            ]

                        # Save final response with questionnaire data
                        success = save_multi_ingredient_response(
                            participant_id=st.session_state.participant,
                            session_id=st.session_state.get(
                                "session_code", "default_session"
                            ),
                            method="slider_based",
                            interface_type="slider_based",
                            ingredient_concentrations=ingredient_concentrations,
                            reaction_time_ms=reaction_time_ms,
                            questionnaire_response=responses,  # Include questionnaire responses
                            is_final_response=True,  # Mark as final
                            extra_data=extra_data,
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

    # ===== SUBJECT CONNECTION & ACCESS SECTION =====
    st.markdown("---")

    # Connection status and QR code section
    if not connection_status["subject_connected"]:

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

    # Main Dashboard Tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["🎮 Control Panel", "📊 Live Monitor", "📈 Analytics", "⚙️ Settings"]
    )

    with tab1:
        st.markdown("### 🚀 Experiment Control")

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

        # Auto-determine number of ingredients from selection
        num_ingredients = len(selected_ingredients)

        # ===== CONCENTRATION CONTROLS SECTION =====
        st.markdown("### 🎛️ Ingredient Concentration Controls")

        # Initialize concentration ranges in session state if not exists
        if "ingredient_concentration_ranges" not in st.session_state:
            st.session_state.ingredient_concentration_ranges = {}

        # Display concentration controls for selected ingredients
        if selected_ingredients:
            st.info(
                f"Configure concentration ranges for {len(selected_ingredients)} selected ingredients:"
            )

            for i, ingredient_name in enumerate(selected_ingredients):
                # Find the default concentration range for this ingredient
                ingredient_config = next(
                    (
                        ing
                        for ing in DEFAULT_INGREDIENT_CONFIG
                        if ing["name"] == ingredient_name
                    ),
                    None,
                )

                if ingredient_config:
                    # Default min/max from config
                    default_min = ingredient_config.get("min_concentration", 0.0)
                    default_max = ingredient_config.get("max_concentration", 100.0)

                    # Get current values from session state or use defaults
                    current_ranges = (
                        st.session_state.ingredient_concentration_ranges.get(
                            ingredient_name, {"min": default_min, "max": default_max}
                        )
                    )

                    # Calculate dynamic step size (1% of total range)
                    total_range = default_max - default_min
                    step_size = max(0.001, total_range * 0.01)  # Min step of 0.001

                    # Compact single-row layout with label and side-by-side inputs
                    col_label, col_min, col_max = st.columns([2.5, 1.25, 1.25])

                    with col_label:
                        st.markdown(f"**{ingredient_name}**")

                    with col_min:
                        min_conc = st.number_input(
                            "Min (mM)",
                            value=current_ranges["min"],
                            min_value=0.0,
                            max_value=1000.0,
                            step=step_size,
                            format="%.3f",
                            key=f"min_conc_{ingredient_name}_{i}",
                            help=f"Minimum concentration for {ingredient_name}",
                            label_visibility="collapsed",
                        )
                        st.caption("Min (mM)")

                    with col_max:
                        max_conc = st.number_input(
                            "Max (mM)",
                            value=current_ranges["max"],
                            min_value=min_conc,
                            max_value=1000.0,
                            step=step_size,
                            format="%.3f",
                            key=f"max_conc_{ingredient_name}_{i}",
                            help=f"Maximum concentration for {ingredient_name}",
                            label_visibility="collapsed",
                        )
                        st.caption("Max (mM)")

                    # Update session state with new ranges
                    st.session_state.ingredient_concentration_ranges[
                        ingredient_name
                    ] = {"min": min_conc, "max": max_conc}

            # Apply changes button
            if st.button(
                "✅ Apply Concentration Changes",
                type="secondary",
                use_container_width=True,
            ):
                st.success("Concentration ranges updated!")
                # Here you could update the database or configuration as needed
        else:
            st.warning(
                "Please select ingredients above to configure concentration ranges."
            )

        # Mathematical mapping selector for 2-ingredient case (2D Grid)
        if num_ingredients == 2:
            st.markdown("### 📐 Concentration Mapping Method")
            st.info(
                "Configure how X-Y grid coordinates map to ingredient concentrations:"
            )

            # Initialize mapping method in session state if not exists
            if "mapping_method" not in st.session_state:
                st.session_state.mapping_method = "linear"

            mapping_method = st.selectbox(
                "Select mapping method:",
                options=["linear", "logarithmic", "exponential"],
                index=["linear", "logarithmic", "exponential"].index(
                    st.session_state.mapping_method
                ),
                help="How grid positions translate to actual concentrations",
                key="moderator_mapping_method_selector",
            )

            # Update session state
            st.session_state.mapping_method = mapping_method
            st.session_state.method = mapping_method  # For compatibility

            # Show mapping method description
            mapping_descriptions = {
                "linear": "**Linear**: Equal grid steps = equal concentration steps. Good for uniform exploration.",
                "logarithmic": "**Logarithmic**: Smaller steps at low concentrations, larger at high. Good for wide ranges.",
                "exponential": "**Exponential**: Larger steps at low concentrations, smaller at high. Good for sensitivity analysis.",
            }
            st.markdown(mapping_descriptions[mapping_method])

        # Show current selection info
        st.info(
            f"📊 Selected: {num_ingredients} ingredients → {', '.join(selected_ingredients)}"
            + (
                f" | Mapping: {st.session_state.get('mapping_method', 'linear').title()}"
                if num_ingredients == 2
                else ""
            )
        )

        # Build selected ingredients configuration
        selected_ingredient_configs = []
        for ingredient_name in selected_ingredients:
            # Find the ingredient config from the master list
            ingredient_config = next(
                (
                    ing
                    for ing in DEFAULT_INGREDIENT_CONFIG
                    if ing["name"] == ingredient_name
                ),
                None,
            )
            if ingredient_config:
                selected_ingredient_configs.append(ingredient_config)

        # Initialize or update experiment configuration in session state
        if (
            "experiment_config" not in st.session_state
            or st.session_state.experiment_config.get("num_ingredients")
            != num_ingredients
            or [
                ing["name"]
                for ing in st.session_state.experiment_config.get("ingredients", [])
            ]
            != selected_ingredients
        ):

            st.session_state.experiment_config = {
                "num_ingredients": num_ingredients,
                "ingredients": selected_ingredient_configs,
                "selected_ingredient_names": selected_ingredients,
            }

        # Create mixture handler
        mixture = MultiComponentMixture(
            st.session_state.experiment_config["ingredients"]
        )

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

    with tab2:
        st.markdown("### 📊 Live Monitor")

        # Connection status indicator
        connection_status = get_connection_status(st.session_state.session_code)
        if connection_status.get("subject_connected", False):
            st.success("🟢 Subject Connected - Monitoring Active")
        else:
            st.warning("🟡 Waiting for Subject Connection")

        # Real-time recipe display
        st.markdown("#### 🧪 Current Recipe/Formula")

        # Get latest subject position/selections
        live_position = get_live_subject_position(st.session_state.participant)

        if live_position:
            # Display current recipe based on interface type
            experiment_config = st.session_state.get("experiment_config", {})
            num_ingredients = experiment_config.get("num_ingredients", 2)

            if num_ingredients == 2:
                # 2D Grid interface - show X,Y coordinates and concentrations
                st.markdown(
                    f"**Position:** X: {live_position.get('x', 0):.1f}, Y: {live_position.get('y', 0):.1f}"
                )

                # Calculate concentrations from position
                try:
                    from callback import ConcentrationMapper

                    mapper = ConcentrationMapper(live_position.get("method", "linear"))
                    sugar_conc, salt_conc = mapper.calculate_concentrations(
                        live_position.get("x", 0), live_position.get("y", 0)
                    )
                    st.markdown(
                        f"**Current Recipe:** Sugar: {sugar_conc:.2f} mM, Salt: {salt_conc:.2f} mM"
                    )
                except Exception as e:
                    st.error(f"Error calculating concentrations: {e}")

            else:
                # Multi-ingredient slider interface
                if live_position.get("ingredient_concentrations"):
                    concentrations = live_position["ingredient_concentrations"]
                    recipe_parts = []
                    for ingredient, conc in concentrations.items():
                        recipe_parts.append(f"{ingredient}: {conc:.2f} mM")
                    st.markdown(f"**Current Recipe:** {', '.join(recipe_parts)}")
                else:
                    st.info("No ingredient selections made yet")

            # Show last update time
            if live_position.get("last_updated"):
                st.caption(f"Last updated: {live_position['last_updated']}")

        else:
            st.info(
                "No current position data available - subject has not made selections yet"
            )

        # Real-time updates section
        st.markdown("#### 📈 Subject Progress")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Total responses count
            responses = get_participant_responses(st.session_state.participant)
            total_responses = (
                len(responses) if responses is not None and len(responses) > 0 else 0
            )
            st.metric("Total Responses", total_responses)

        with col2:
            # Current session duration
            session_info = get_session_info(st.session_state.session_code)
            if session_info:
                from datetime import datetime

                try:
                    start_time = datetime.fromisoformat(session_info["created_at"])
                    duration = datetime.now() - start_time
                    duration_minutes = duration.total_seconds() / 60
                    st.metric("Session Duration", f"{duration_minutes:.1f} min")
                except:
                    st.metric("Session Duration", "N/A")

        with col3:
            # Connection status
            status_text = (
                "Connected"
                if connection_status.get("subject_connected", False)
                else "Disconnected"
            )
            st.metric("Connection Status", status_text)

        # Auto-refresh control
        auto_refresh = st.checkbox(
            "🔄 Auto-refresh (every 3 seconds)",
            value=True,
            key="live_monitor_auto_refresh",
        )

        if auto_refresh:
            # Add auto-refresh placeholder
            import time

            time.sleep(0.1)  # Small delay to prevent too aggressive refreshing
            st.rerun()

    with tab3:
        st.markdown("### 📈 Analytics")

        # Session metadata section
        st.markdown("#### 📋 Session Metadata")

        session_info = get_session_info(st.session_state.session_code)
        responses = get_participant_responses(st.session_state.participant)

        col1, col2 = st.columns(2)

        with col1:
            # Basic session stats
            total_responses = (
                len(responses) if responses is not None and len(responses) > 0 else 0
            )
            st.metric("Total Responses", total_responses)

            if session_info:
                from datetime import datetime

                try:
                    start_time = datetime.fromisoformat(session_info["created_at"])
                    duration = datetime.now() - start_time
                    duration_minutes = duration.total_seconds() / 60
                    st.metric("Session Duration", f"{duration_minutes:.1f} min")
                    st.metric("Start Time", start_time.strftime("%Y-%m-%d %H:%M:%S"))
                except:
                    st.metric("Session Duration", "N/A")
                    st.metric("Start Time", "N/A")

        with col2:
            # Connection and progress
            connection_status = get_connection_status(st.session_state.session_code)
            status_text = (
                "Connected"
                if connection_status.get("subject_connected", False)
                else "Disconnected"
            )
            st.metric("Subject Status", status_text)

            # Calculate current vs total progress (if we had target responses)
            target_responses = 10  # Default target
            progress_pct = min(100, (total_responses / target_responses) * 100)
            st.metric("Progress", f"{progress_pct:.1f}%")

        # Debug tools section
        st.markdown("#### 🛠️ Debug Tools")

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📊 Show Database Responses", use_container_width=True):
                if responses is not None and len(responses) > 0:
                    st.markdown("**Raw Database Responses:**")
                    import pandas as pd

                    st.dataframe(pd.DataFrame(responses))
                else:
                    st.info("No responses found in database")

        with col2:
            if st.button("💾 Export Session Data", use_container_width=True):
                if responses is not None and len(responses) > 0:
                    # Create export data
                    export_data = {
                        "session_info": session_info,
                        "responses": responses,
                        "export_timestamp": datetime.now().isoformat(),
                    }
                    import pandas as pd

                    st.download_button(
                        "⬇️ Download JSON",
                        data=pd.json_normalize(export_data).to_json(orient="records"),
                        file_name=f"session_{st.session_state.session_code}_data.json",
                        mime="application/json",
                    )
                else:
                    st.warning("No data to export")

        with col3:
            if st.button("🗑️ Clear Session Data", use_container_width=True):
                # Confirmation dialog
                if st.session_state.get("confirm_clear_data", False):
                    clear_participant_session(st.session_state.participant)
                    st.success("Session data cleared!")
                    st.session_state.confirm_clear_data = False
                    st.rerun()
                else:
                    st.session_state.confirm_clear_data = True
                    st.warning("⚠️ Click again to confirm data deletion")

    with tab4:
        st.markdown("### ⚙️ Settings")

        # Session controls section
        st.markdown("#### 🎮 Session Controls")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "🔄 Restart Session", use_container_width=True, type="secondary"
            ):
                # Reset subject to beginning phase
                if st.session_state.get("confirm_restart", False):
                    clear_participant_session(st.session_state.participant)
                    # Reset session state
                    if hasattr(st.session_state, "phase"):
                        st.session_state.phase = "welcome"
                    st.success(
                        "Session restarted! Subject will begin from welcome phase."
                    )
                    st.session_state.confirm_restart = False
                    st.rerun()
                else:
                    st.session_state.confirm_restart = True
                    st.warning("⚠️ Click again to confirm session restart")

            if st.button(
                "🔀 Reset Random Start", use_container_width=True, type="secondary"
            ):
                # Generate new random starting positions
                try:
                    from callback import start_trial

                    success = start_trial(
                        st.session_state.participant,
                        method=st.session_state.get("method", "linear"),
                        reset_random=True,
                    )
                    if success:
                        st.success("New random starting positions generated!")
                    else:
                        st.error("Failed to generate new random positions")
                except Exception as e:
                    st.error(f"Error generating random positions: {e}")

        with col2:
            if st.button("⛔ End Session", use_container_width=True, type="primary"):
                # End session gracefully
                if st.session_state.get("confirm_end", False):
                    from session_manager import end_session

                    if end_session(st.session_state.session_code):
                        st.success("Session ended successfully!")
                        st.session_state.session_code = None
                        st.session_state.device_role = None
                        st.query_params.clear()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Failed to end session")
                    st.session_state.confirm_end = False
                else:
                    st.session_state.confirm_end = True
                    st.warning("⚠️ Click again to confirm session end")

        # Configuration controls section
        st.markdown("#### ⚙️ Configuration Controls")

        # Random start toggle
        enable_random_start = st.checkbox(
            "🎲 Enable Random Start Positions",
            value=st.session_state.get("enable_random_start", True),
            help="When enabled, subjects start with random positions instead of center",
        )
        st.session_state.enable_random_start = enable_random_start

        # Interface method selection (for 2D grid)
        if st.session_state.get("experiment_config", {}).get("num_ingredients", 2) == 2:
            mapping_method = st.selectbox(
                "📐 Concentration Mapping Method",
                options=["linear", "logarithmic", "exponential"],
                index=["linear", "logarithmic", "exponential"].index(
                    st.session_state.get("method", "linear")
                ),
                help="Method for mapping X,Y coordinates to concentrations",
            )
            st.session_state.method = mapping_method

        # Modify ingredient ranges mid-session
        st.markdown("#### 🧪 Mid-Session Range Modification")

        if st.session_state.get("selected_ingredients"):
            st.info("Modify concentration ranges for active experiment:")

            for ingredient_name in st.session_state.selected_ingredients:
                current_ranges = st.session_state.ingredient_concentration_ranges.get(
                    ingredient_name, {"min": 0.0, "max": 100.0}
                )

                col_name, col_min, col_max = st.columns([2, 1, 1])

                with col_name:
                    st.write(f"**{ingredient_name}**")

                with col_min:
                    # Calculate dynamic step size for settings too
                    ingredient_config = next(
                        (
                            ing
                            for ing in DEFAULT_INGREDIENT_CONFIG
                            if ing["name"] == ingredient_name
                        ),
                        None,
                    )
                    if ingredient_config:
                        total_range = ingredient_config.get(
                            "max_concentration", 100.0
                        ) - ingredient_config.get("min_concentration", 0.0)
                        step_size = max(0.001, total_range * 0.01)
                    else:
                        step_size = 0.1

                    new_min = st.number_input(
                        "Min",
                        value=current_ranges["min"],
                        min_value=0.0,
                        step=step_size,
                        format="%.3f",
                        key=f"settings_min_{ingredient_name}",
                    )

                with col_max:
                    new_max = st.number_input(
                        "Max",
                        value=current_ranges["max"],
                        min_value=new_min,
                        step=step_size,
                        format="%.3f",
                        key=f"settings_max_{ingredient_name}",
                    )

                # Update ranges
                st.session_state.ingredient_concentration_ranges[ingredient_name] = {
                    "min": new_min,
                    "max": new_max,
                }

            if st.button("✅ Apply Range Changes", use_container_width=True):
                st.success("Concentration ranges updated for active session!")
        else:
            st.warning("No active experiment configuration found")


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
