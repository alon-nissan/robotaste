from callback import (
    CANVAS_SIZE,
    INTERFACE_2D_GRID,
    INTERFACE_SLIDERS,
    MultiComponentMixture,
    cleanup_pending_results,
    create_canvas_drawing,
    render_questionnaire,
    save_intermediate_click,
    show_preparation_message,
)
from ui_components import create_header, display_phase_status
from session_manager import (
    get_session_info,
    join_session,
    sync_session_state,
)
from sql_handler import (
    get_initial_slider_positions,
    is_participant_activated,
    get_current_cycle,
    increment_cycle,
    save_sample_cycle,
)
from state_machine import ExperimentStateMachine, ExperimentPhase, initialize_phase
from questionnaire_config import get_default_questionnaire_type


import streamlit as st
import streamlit_vertical_slider as svs
from streamlit_drawable_canvas import st_canvas
import time
import logging

logger = logging.getLogger(__name__)


def get_questionnaire_type_from_config() -> str:
    """
    Retrieve the questionnaire type from the current experiment configuration.

    Returns:
        Questionnaire type string (defaults to 'hedonic_preference' if not found)
    """
    # Try to get from session state's experiment_config
    if hasattr(st.session_state, "experiment_config") and isinstance(
        st.session_state.experiment_config, dict
    ):
        questionnaire_type = st.session_state.experiment_config.get(
            "questionnaire_type"
        )
        if questionnaire_type:
            return questionnaire_type

    # Try to get from session state directly
    if hasattr(st.session_state, "selected_questionnaire_type"):
        return st.session_state.selected_questionnaire_type

    # Fallback to default
    return get_default_questionnaire_type()


def subject_interface():
    """
    Multi-device subject interface with session management.

    NEW 6-PHASE WORKFLOW:
    =====================
    1. welcome (UI only) - Participant enters ID and waits for activation
    2. waiting - Activated, waiting for moderator to start first cycle
    3. robot_preparing - Robot is preparing the sample (auto-polling)
    4. tasting - Subject tastes sample and clicks "Done Tasting"
    5. questionnaire - Subject answers questionnaire about the sample
    6. selection - Subject makes selection for next cycle (grid/sliders)
    7. Repeat steps 3-6 for each cycle, or transition to:
    8. complete - Session finished

    Key Changes from Old Workflow:
    - No PRE/POST questionnaire distinction (single questionnaire after tasting)
    - Questionnaire comes BEFORE selection (not after)
    - Selection is for the NEXT cycle (not current)
    - Robot preparing phase added for better UX
    - Moderator controls cycle progression and completion
    """
    # Initialize session_code from URL parameters if not in session state
    if not st.session_state.get("session_code"):
        url_session = st.query_params.get("session", "")
        url_role = st.query_params.get("role", "")

        if url_session and url_role == "subject":
            if join_session(url_session):
                st.session_state.session_code = url_session
                sync_session_state(url_session, "subject")
            else:
                st.error(f"Invalid or expired session: {url_session}")
                if st.button("🏠 Return to Home", key="invalid_session_return"):
                    st.query_params.clear()
                    st.rerun()
                return

    # Check if we have a valid session
    st.write(st.session_state.session_code)
    if not st.session_state.session_code:
        st.error(
            "No active session. Please join a session using the code provided by your moderator."
        )
        if st.button("🏠 Return to Home", key="subject_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    session_info = get_session_info(st.session_state.session_code)
    if not session_info:
        # Check if this is a valid UUID but not yet in database (two-stage creation)
        if not st.session_state.get("session_created_in_db", True):
            st.info(
                "📋 Session created. Waiting for moderator to configure experiment..."
            )
            st.write(
                "Please wait while the moderator sets up the experiment parameters."
            )
            if st.button("🏠 Return to Home", key="subject_return_home_waiting_config"):
                st.query_params.clear()
                st.rerun()
        else:
            st.error("Session expired or invalid.")
            st.session_state.session_code = None
            if st.button(
                "🏠 Return to Home", key="subject_return_home_invalid_session"
            ):
                st.query_params.clear()
                st.rerun()
        return
    elif session_info.get("state") != "active":
        st.error("Session has ended.")
        st.session_state.session_code = None
        if st.button("🏠 Return to Home", key="subject_return_home_ended_session"):
            st.query_params.clear()
            st.rerun()
        return

    create_header(
        f"Session {st.session_state.session_code}", f"Taste Preference Experiment", ""
    )

    # Initialize phase if not set
    initialize_phase(default_phase="welcome")

    # Backward compatibility: map old phase names to new ones
    phase_mapping = {
        "pre_questionnaire": "waiting",  # Old pre-questionnaire -> waiting
        "respond": "selection",  # Old respond -> selection
        "post_response_message": "questionnaire",  # Old post_response_message -> questionnaire
        "post_questionnaire": "questionnaire",  # Old post_questionnaire -> questionnaire
        "done": "complete",  # Old done -> complete
    }
    if st.session_state.phase in phase_mapping:
        old_phase = st.session_state.phase
        st.session_state.phase = phase_mapping[old_phase]
        logger.info(
            f"Mapped old phase '{old_phase}' to new phase '{st.session_state.phase}'"
        )

    # Display current cycle number if in active phase
    if st.session_state.phase not in ["welcome", "waiting", "complete"]:
        cycle_num = get_current_cycle(st.session_state.session_code)
        if cycle_num > 0:
            st.markdown(f"**Current Cycle:** {cycle_num}")

    # Get or set participant ID
    if st.session_state.phase == "welcome":
        col2 = st.columns([1, 2, 1])[1]
        with col2:
            st.markdown("### Welcome!")
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
                "Check Status",
                type="primary",
                use_container_width=True,
                key="subject_check_status_button",
            ):
                if is_participant_activated(participant_id):
                    # Sync session state from database to get experiment configuration
                    sync_session_state(st.session_state.session_code, "subject")

                    # Transition to WAITING phase (new 6-phase workflow)
                    try:
                        ExperimentStateMachine.transition(
                            new_phase=ExperimentPhase.WAITING,
                            session_id=st.session_state.session_code,
                        )
                    except Exception as e:
                        # Fallback: directly set phase if state machine fails
                        logger.warning(
                            f"State machine transition failed: {e}. Using direct assignment."
                        )
                        st.session_state.phase = "waiting"

                    st.success(
                        "Ready to begin! Waiting for moderator to start the experiment."
                    )
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Waiting for moderator to activate your session.")

    elif st.session_state.phase == "waiting":
        display_phase_status("waiting", st.session_state.participant)

        col2 = st.columns([1, 2, 1])[1]
        with col2:
            st.info("Waiting for moderator to start the first cycle...")
            st.write("The experiment will begin shortly. Please be patient.")

        # Poll database for phase changes from moderator
        session_info = get_session_info(st.session_state.session_code)
        if session_info:
            phase_from_db = session_info.get("current_phase", "waiting")
            if phase_from_db != st.session_state.phase:
                logger.info(
                    f"Phase changed: {st.session_state.phase} -> {phase_from_db}"
                )
                st.session_state.phase = phase_from_db

        time.sleep(2)
        st.rerun()

    elif st.session_state.phase == "robot_preparing":
        display_phase_status("robot_preparing", st.session_state.participant)

        # Show cycle number
        cycle_num = get_current_cycle(st.session_state.session_code)
        st.info(f"Cycle {cycle_num}: Robot is preparing your sample, please wait...")

        # Poll database for phase changes from moderator
        session_info = get_session_info(st.session_state.session_code)
        if session_info:
            phase_from_db = session_info.get("current_phase", "robot_preparing")
            if phase_from_db != st.session_state.phase:
                logger.info(
                    f"Phase changed: {st.session_state.phase} -> {phase_from_db}"
                )
                st.session_state.phase = phase_from_db

        time.sleep(2)
        st.rerun()

    # TASTING phase removed - workflow now goes directly from ROBOT_PREPARING to QUESTIONNAIRE

    elif st.session_state.phase == "selection":
        display_phase_status("selection", st.session_state.participant)

        # Validate session is configured
        # Settings are already loaded by sync_session_state() into st.session_state
        if not st.session_state.get("session_code"):
            st.error("No session found. Please rejoin the session.")
            return

        # Verify session is fully configured (moderator has started trial)
        if not st.session_state.get("num_ingredients") or not st.session_state.get("interface_type"):
            st.warning("Session not fully configured. Waiting for moderator to start the trial...")
            time.sleep(2)
            st.rerun()
            return

        # Get settings from session state (already loaded by sync_session_state)
        num_ingredients = st.session_state.get("num_ingredients", 2)
        interface_type = st.session_state.get("interface_type", INTERFACE_2D_GRID)

        # FIXED: Get ingredient configuration from session state (set by start_trial)
        # This preserves the moderator's actual ingredient selection instead of using defaults
        if hasattr(st.session_state, "ingredients") and st.session_state.ingredients:
            # Use the ingredients from start_trial (correct moderator selection)
            ingredients = st.session_state.ingredients
        elif (
            hasattr(st.session_state, "experiment_config")
            and "ingredients" in st.session_state.experiment_config
        ):
            # Fallback: Try to get from experiment_config in session state
            ingredients = st.session_state.experiment_config["ingredients"]
        else:
            # Last resort: Use defaults (backward compatibility)
            from callback import DEFAULT_INGREDIENT_CONFIG

            ingredients = DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
            st.warning("Using default ingredients - moderator selection not found")

        experiment_config = {
            "num_ingredients": num_ingredients,
            "ingredients": ingredients,  # Now uses correct moderator selection!
        }

        mixture = MultiComponentMixture(experiment_config["ingredients"])

        # Verify interface type matches ingredients (safety check)
        calculated_interface = mixture.get_interface_type()
        if calculated_interface != interface_type:
            st.warning(
                f"Interface type mismatch. Using calculated: {calculated_interface}"
            )
            interface_type = calculated_interface

        if interface_type == INTERFACE_2D_GRID:
            # Traditional 2D grid interface
            st.markdown("### Make Your Selection")
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

                                # Generate unique sample ID for this selection
                                import uuid

                                sample_id = str(uuid.uuid4())
                                st.session_state.current_sample_id = sample_id

                                # Initialize selection history if it doesn't exist
                                if not hasattr(st.session_state, "selection_history"):
                                    st.session_state.selection_history = []

                                # Add selection to history with order number and sample_id
                                selection_number = (
                                    len(st.session_state.selection_history) + 1
                                )
                                st.session_state.selection_history.append(
                                    {
                                        "x": x,
                                        "y": y,
                                        "sample_id": sample_id,
                                        "order": selection_number,
                                        "timestamp": time.time(),
                                    }
                                )

                                # Save click to database with sample_id
                                method = st.session_state.get("method", "linear")
                                success = save_intermediate_click(
                                    st.session_state.participant,
                                    x,
                                    y,
                                    method,
                                    sample_id=sample_id,
                                )

                                if success:
                                    st.session_state.last_saved_position = (x, y)

                                # Store current canvas result for later submission
                                st.session_state.pending_canvas_result = canvas_result
                                st.session_state.pending_method = method

                                # Prepare selection data for next cycle
                                from callback import ConcentrationMapper
                                sugar_mm, salt_mm = ConcentrationMapper.map_coordinates_to_concentrations(
                                    x, y, method=method
                                )
                                ingredient_concentrations = {
                                    "Sugar": round(sugar_mm, 3),
                                    "Salt": round(salt_mm, 3),
                                }

                                st.session_state.next_selection_data = {
                                    "interface_type": INTERFACE_2D_GRID,
                                    "method": method,
                                    "x_position": x,
                                    "y_position": y,
                                    "ingredient_concentrations": ingredient_concentrations,
                                    "trajectory": st.session_state.trajectory_clicks.copy() if hasattr(st.session_state, "trajectory_clicks") else [],
                                    "sample_id": sample_id,
                                }

                                # Auto-transition to ROBOT_PREPARING for next cycle
                                ExperimentStateMachine.transition(
                                    new_phase=ExperimentPhase.ROBOT_PREPARING,
                                    session_id=st.session_state.session_code,
                                )

                                # Increment cycle counter
                                new_cycle = increment_cycle(st.session_state.session_code)
                                st.session_state.cycle_number = new_cycle

                                # Update current_tasted_sample for next cycle
                                st.session_state.current_tasted_sample = ingredient_concentrations.copy()

                                # Clear trajectory for new cycle
                                st.session_state.trajectory_clicks = []

                                st.success(f"Selection saved! Starting cycle {new_cycle}")
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
            st.markdown("### Adjust Ingredient Concentrations")
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

            # Store current slider values in session state (no database write until Finish clicked)
            if slider_changed:
                st.session_state.current_slider_values = slider_values
                # Real-time monitoring removed - was causing database lock errors
                # Future: implement proper real-time monitoring with v2 schema

            # Add Finish button with enhanced styling
            st.markdown('<div class="finish-button-container">', unsafe_allow_html=True)

            # Only show finish button if user has made some adjustments or show it by default
            finish_button_clicked = st.button(
                "Finish Selection",
                type="primary",
                use_container_width=False,
                help="Complete your mixture selection and proceed to the questionnaire",
                key="subject_finish_sliders_button",
            )

            st.markdown("</div>", unsafe_allow_html=True)

            # Handle finish button click
            if finish_button_clicked:
                # Generate unique sample ID for this selection
                import uuid

                sample_id = str(uuid.uuid4())
                st.session_state.current_sample_id = sample_id

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

                # Calculate reaction time from trial start
                reaction_time_ms = None
                if hasattr(st.session_state, "trial_start_time"):
                    reaction_time_ms = int(
                        (time.perf_counter() - st.session_state.trial_start_time) * 1000
                    )

                # Extract actual mM concentrations for database storage
                ingredient_concentrations = {}
                for ingredient_name, conc_data in concentrations.items():
                    ingredient_concentrations[ingredient_name] = round(
                        conc_data["actual_concentration_mM"], 3
                    )

                # Store selection data for next cycle (will be saved after questionnaire)
                st.session_state.next_selection_data = {
                    "interface_type": INTERFACE_SLIDERS,
                    "method": INTERFACE_SLIDERS,
                    "ingredient_concentrations": ingredient_concentrations,
                    "slider_values": final_slider_values.copy(),
                    "sample_id": sample_id,
                }

                # Initialize selection history if it doesn't exist
                if not hasattr(st.session_state, "selection_history"):
                    st.session_state.selection_history = []

                # Add final selection to history for display
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

                # Store final values in session state for questionnaire phase
                st.session_state.current_slider_values = final_slider_values
                st.session_state.pending_slider_result = {
                    "slider_values": final_slider_values,
                    "concentrations": concentrations,
                }
                st.session_state.pending_method = INTERFACE_SLIDERS

                # Auto-transition to ROBOT_PREPARING for next cycle
                ExperimentStateMachine.transition(
                    new_phase=ExperimentPhase.ROBOT_PREPARING,
                    session_id=st.session_state.session_code,
                )

                # Increment cycle counter
                new_cycle = increment_cycle(st.session_state.session_code)
                st.session_state.cycle_number = new_cycle

                # Update current_tasted_sample for next cycle
                if "ingredient_concentrations" in st.session_state.next_selection_data:
                    st.session_state.current_tasted_sample = st.session_state.next_selection_data["ingredient_concentrations"].copy()

                st.success(
                    f"Slider selection recorded! Starting cycle {new_cycle}"
                )
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

    elif st.session_state.phase == "questionnaire":
        display_phase_status("questionnaire", st.session_state.participant)

        # Show cycle number
        cycle_num = get_current_cycle(st.session_state.session_code)
        st.info(
            f"Cycle {cycle_num}: Please answer the questionnaire about the sample you just tasted"
        )

        col2 = st.columns([1, 2, 1])[1]
        with col2:
            # Get questionnaire type from experiment configuration
            questionnaire_type = get_questionnaire_type_from_config()
            responses = render_questionnaire(
                questionnaire_type,
                st.session_state.participant,
            )

            if responses:
                # Store questionnaire responses
                st.session_state.questionnaire_responses = responses

                # Get current cycle number
                current_cycle = get_current_cycle(st.session_state.session_code)

                # Get what they TASTED (current cycle's sample)
                # This comes from the previous cycle's selection (stored when transitioning to ROBOT_PREPARING)
                # or from initial random position for cycle 1
                ingredient_concentrations = st.session_state.get(
                    "current_tasted_sample", {}
                )

                # Get selection data for NEXT cycle (if it exists - won't exist during questionnaire)
                # This will be filled in during SELECTION phase
                selection_data = st.session_state.get("next_selection_data", {})

                # Include trajectory data if available (for grid interface)
                if hasattr(st.session_state, "trajectory_clicks"):
                    if not selection_data:
                        selection_data = {}
                    selection_data["trajectory"] = st.session_state.trajectory_clicks

                # Save complete cycle data to database
                try:
                    sample_id = save_sample_cycle(
                        session_id=st.session_state.session_code,
                        cycle_number=current_cycle,
                        ingredient_concentration=ingredient_concentrations,
                        selection_data=selection_data,
                        questionnaire_answer=responses,
                        is_final=False,
                    )
                    success = True
                    logger.info(
                        f"Saved complete cycle {current_cycle} with sample_id: {sample_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to save cycle data: {e}")
                    success = False

                if success:
                    # Transition to SELECTION phase (new 6-phase workflow)
                    ExperimentStateMachine.transition(
                        new_phase=ExperimentPhase.SELECTION,
                        session_id=st.session_state.session_code,
                    )
                    st.success(
                        "Questionnaire saved! Now make your selection for the next cycle."
                    )
                    st.rerun()
                else:
                    st.error(
                        "Failed to save questionnaire response. Please contact the moderator."
                    )

    elif st.session_state.phase == "complete":
        display_phase_status("complete", st.session_state.participant)

        col2 = st.columns([1, 2, 1])[1]
        with col2:
            st.markdown("### Thank You!")
            st.success("The experiment session has been completed successfully.")

            # Show session summary
            cycle_num = get_current_cycle(st.session_state.session_code)
            st.info(f"Total cycles completed: {cycle_num}")

            st.write("Thank you for your participation!")
            st.write(
                "You may now close this window or wait for further instructions from the moderator."
            )
