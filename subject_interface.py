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
    sync_session_state,
    update_session_activity,
)
from sql_handler import (
    get_initial_slider_positions,
    get_moderator_settings,
    is_participant_activated,
    save_multi_ingredient_response,
    update_response_with_questionnaire,
    update_session_state,
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
    """Multi-device subject interface with session management."""
    # Check if we have a valid session
    if not st.session_state.session_code:
        st.error(
            "No active session. Please join a session using the code provided by your moderator."
        )
        if st.button("🏠 Return to Home", key="subject_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    session_info = get_session_info(st.session_state.session_code)
    if not session_info or not session_info["is_active"]:
        st.error("Session expired or invalid.")
        st.session_state.session_code = None
        if st.button("🏠 Return to Home", key="subject_return_home_invalid_session"):
            st.query_params.clear()
            st.rerun()
        return

    create_header(
        f"Session {st.session_state.session_code}", f"Taste Preference Experiment", ""
    )

    # Initialize phase if not set
    initialize_phase(default_phase="welcome")

    # Update session activity
    update_session_activity(st.session_state.session_code)

    # Get or set participant ID
    if st.session_state.phase == "welcome":
        # TODO: Remove unused col1, col3 variables
        col1, col2, col3 = st.columns([1, 2, 1])
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

                    # Use state machine for validated transition
                    try:
                        ExperimentStateMachine.transition(
                            new_phase=ExperimentPhase.PRE_QUESTIONNAIRE,
                            session_code=st.session_state.session_code,
                            participant_id=participant_id,
                            sync_to_database=True,
                        )
                    except Exception as e:
                        # Fallback: directly set phase if state machine fails
                        # (can happen if database phase doesn't match session state)
                        import logging

                        logging.warning(
                            f"State machine transition failed: {e}. Using direct assignment."
                        )
                        st.session_state.phase = "pre_questionnaire"

                    st.success("Ready to begin!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.warning("Waiting for moderator to start your session.")

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

        # Render initial impression questionnaire (using configured questionnaire type)
        # TODO: Remove unused col1, col3 variables for cleaner code
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.info(
                "Please provide your initial impression of the random starting solution shown on the canvas."
            )
            # Get questionnaire type from experiment configuration
            questionnaire_type = get_questionnaire_type_from_config()
            responses = render_questionnaire(
                questionnaire_type, st.session_state.participant
            )

            if responses:
                # Store questionnaire responses in session state for potential database storage
                st.session_state.initial_questionnaire_responses = responses

                # Save initial questionnaire to database (update is_initial=TRUE record)
                success, response_id = update_response_with_questionnaire(
                    participant_id=st.session_state.participant,
                    session_id=st.session_state.get("session_code", "default_session"),
                    questionnaire_response=responses,
                    sample_id=None,  # For initial, match by is_initial=True
                )

                if success and response_id:
                    # Extract and save target variable for Bayesian optimization
                    from sql_handler import extract_and_save_target_variable

                    questionnaire_type = get_questionnaire_type_from_config()
                    target_value = extract_and_save_target_variable(
                        response_id=response_id,
                        questionnaire_response=responses,
                        questionnaire_type=questionnaire_type,
                    )

                    if target_value is not None:
                        logger.info(
                            f"Initial target variable extracted: {target_value} for response_id={response_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to extract initial target variable for response_id={response_id}"
                        )

                if success:
                    # Move to respond phase using state machine
                    ExperimentStateMachine.transition(
                        new_phase=ExperimentPhase.TRIAL_ACTIVE,
                        session_code=st.session_state.session_code,
                        participant_id=st.session_state.participant,
                        sync_to_database=True,
                    )
                    st.rerun()
                else:
                    st.error("Failed to save initial questionnaire. Please try again.")

    elif st.session_state.phase == "respond":
        display_phase_status("respond", st.session_state.participant)

        # Get moderator settings
        mod_settings = get_moderator_settings(st.session_state.participant)
        if not mod_settings:
            st.error("No experiment settings found. Please contact the moderator.")
            return

        # Determine interface type based on session state set by start_trial
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
                                success = save_intermediate_click(
                                    st.session_state.participant,
                                    x,
                                    y,
                                    mod_settings["method"],
                                    sample_id=sample_id,
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
                                ExperimentStateMachine.transition(
                                    new_phase=ExperimentPhase.POST_QUESTIONNAIRE,
                                    session_code=st.session_state.session_code,
                                    participant_id=st.session_state.participant,
                                    sync_to_database=True,
                                )
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

                # Save to database with sample_id and is_final_response=False
                # This will be updated to is_final_response=True after questionnaire
                success = save_multi_ingredient_response(
                    participant_id=st.session_state.participant,
                    session_id=st.session_state.get("session_code", "default_session"),
                    method=INTERFACE_SLIDERS,
                    interface_type=INTERFACE_SLIDERS,
                    ingredient_concentrations=ingredient_concentrations,
                    reaction_time_ms=reaction_time_ms,
                    questionnaire_response={},  # Empty dict, will be updated in questionnaire phase
                    sample_id=sample_id,  # Link to this specific sample
                    is_final_response=False,  # Not final until questionnaire completed
                    is_initial=False,
                    extra_data={
                        "interface_type": INTERFACE_SLIDERS,
                        "method": INTERFACE_SLIDERS,
                        "response_metadata": {
                            "is_initial_random": False,
                            "is_finish_button": True,
                            "is_final_submission": False,
                        },
                        "ui_data": {
                            "grid_position": None,
                            "slider_percentages": {
                                ing: concentrations[ing]["slider_position"]
                                for ing in concentrations
                            },
                            "concentrations_summary": concentrations,
                        },
                        "ingredient_metadata": {
                            "ingredient_names": list(ingredient_concentrations.keys()),
                            "ingredient_order": list(
                                range(len(ingredient_concentrations))
                            ),
                            "ingredient_ranges": {
                                ing: {
                                    "min": concentrations[ing]["min_mM"],
                                    "max": concentrations[ing]["max_mM"],
                                    "unit": "mM",
                                    "molecular_weight": concentrations[ing][
                                        "molecular_weight"
                                    ],
                                }
                                for ing in concentrations
                            },
                        },
                    },
                )

                if success:
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

                    st.success("Slider selection recorded!")
                    # Go to questionnaire (will update the same record with questionnaire data)
                    ExperimentStateMachine.transition(
                        new_phase=ExperimentPhase.POST_QUESTIONNAIRE,
                        session_code=st.session_state.session_code,
                        participant_id=st.session_state.participant,
                        sync_to_database=True,
                    )
                    st.rerun()
                else:
                    st.error("Failed to save slider selection. Please try again.")

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
                ExperimentStateMachine.transition(
                    new_phase=ExperimentPhase.POST_QUESTIONNAIRE,
                    session_code=st.session_state.session_code,
                    participant_id=st.session_state.participant,
                    sync_to_database=True,
                )
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

            # Get questionnaire type from experiment configuration
            questionnaire_type = get_questionnaire_type_from_config()
            responses = render_questionnaire(
                questionnaire_type,
                st.session_state.participant,
                show_final_response=show_final,
            )

            if responses:
                # Store questionnaire responses
                st.session_state.post_questionnaire_responses = responses

                # ALWAYS save questionnaire response for every sample (not just final)
                # Get sample_id if available (for UUID-based linking)
                sample_id = st.session_state.get("current_sample_id", None)

                # Update the existing response with questionnaire data
                success, response_id = update_response_with_questionnaire(
                    participant_id=st.session_state.participant,
                    session_id=st.session_state.get("session_code", "default_session"),
                    questionnaire_response=responses,  # Add questionnaire to existing response
                    sample_id=sample_id,  # Link to specific sample via UUID
                )

                if success and response_id:
                    # Extract and save target variable for Bayesian optimization
                    from sql_handler import extract_and_save_target_variable

                    questionnaire_type = get_questionnaire_type_from_config()
                    target_value = extract_and_save_target_variable(
                        response_id=response_id,
                        questionnaire_response=responses,
                        questionnaire_type=questionnaire_type,
                    )

                    if target_value is not None:
                        logger.info(
                            f"Target variable extracted: {target_value} for response_id={response_id}"
                        )
                    else:
                        logger.warning(
                            f"Failed to extract target variable for response_id={response_id}"
                        )

                if success:
                    if responses.get("is_final", False):
                        # Complete the trial with final submission
                        ExperimentStateMachine.transition(
                            new_phase=ExperimentPhase.TRIAL_COMPLETE,
                            session_code=st.session_state.session_code,
                            participant_id=st.session_state.participant,
                            sync_to_database=True,
                        )
                        # Clean up temporary storage
                        cleanup_pending_results()
                        # Clear sample_id for next trial
                        if hasattr(st.session_state, "current_sample_id"):
                            del st.session_state.current_sample_id
                        st.rerun()
                    else:
                        # Intermediate save successful - allow another sample
                        # Clean up temporary storage
                        cleanup_pending_results()
                        # Clear sample_id so new click generates new UUID
                        if hasattr(st.session_state, "current_sample_id"):
                            del st.session_state.current_sample_id

                        ExperimentStateMachine.transition(
                            new_phase=ExperimentPhase.TRIAL_ACTIVE,
                            session_code=st.session_state.session_code,
                            participant_id=st.session_state.participant,
                            sync_to_database=True,
                        )
                        st.success(
                            "Questionnaire saved! You can test another sample or check the box above to submit your final response."
                        )
                        st.rerun()
                else:
                    st.error(
                        "Failed to save questionnaire response. Please contact the moderator."
                    )
                    st.rerun()

    elif st.session_state.phase == "done":
        display_phase_status("done", st.session_state.participant)

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🎉 Thank You!")
            st.success("Your response has been recorded successfully.")

            if hasattr(st.session_state, "last_response"):
                resp = st.session_state.last_response

                st.markdown("#### Your Selection:")
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Position", f"({resp['x']:.0f}, {resp['y']:.0f})")
                with col_b:
                    st.metric("Response Time", f"{resp.get('reaction_time_ms', 0)} ms")

            # Auto-refresh disabled to prevent blank screen issues
            st.info(
                "Waiting for next trial... (refresh browser to check for new trials)"
            )

            # Check if moderator started a new trial (only on user action, not automatic)
            if st.button("Check for New Trial", key="subject_check_new_trial"):
                if is_participant_activated(st.session_state.participant):
                    mod_settings = get_moderator_settings(st.session_state.participant)
                    if mod_settings and mod_settings["created_at"] != getattr(
                        st.session_state, "last_trial_time", None
                    ):
                        # Skip pre-questionnaire for subsequent trials
                        ExperimentStateMachine.transition(
                            new_phase=ExperimentPhase.TRIAL_ACTIVE,
                            session_code=st.session_state.session_code,
                            participant_id=st.session_state.participant,
                            sync_to_database=True,
                        )
                        st.session_state.last_trial_time = mod_settings["created_at"]
                        st.rerun()
                    else:
                        st.info("No new trials available yet.")
                else:
                    st.info("No new trials available yet.")
