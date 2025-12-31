from robotaste.components.canvas import (
    CANVAS_SIZE,
    get_canvas_size,
    create_canvas_drawing,
)
from robotaste.core.calculations import (
    INTERFACE_2D_GRID,
    INTERFACE_SINGLE_INGREDIENT,
    MultiComponentMixture,
)
from robotaste.utils.ui_helpers import (
    cleanup_pending_results,
    render_loading_spinner,
)
from robotaste.views.questionnaire import render_questionnaire
from robotaste.core.trials import save_intermediate_click
from robotaste.core.bo_integration import get_bo_suggestion_for_session
from robotaste.core.calculations import ConcentrationMapper
from robotaste.config.defaults import DEFAULT_INGREDIENT_CONFIG
from robotaste.data.session_repo import (
    get_session_info,
    join_session,
    sync_session_state_to_streamlit as sync_session_state,
)
from robotaste.data.database import (
    get_current_cycle,
    get_session_samples,
    increment_cycle,
    save_sample_cycle,
)
from robotaste.core.state_machine import ExperimentPhase
from robotaste.core import state_helpers
from robotaste.config.questionnaire import get_default_questionnaire_type


import streamlit as st
from streamlit_drawable_canvas import st_canvas
import time
import logging
import json
from datetime import datetime

from robotaste.data.database import update_user_profile, create_user


logger = logging.getLogger(__name__)


def render_registration_screen():
    """Renders the user registration screen."""
    st.header("Personal Information")
    st.write("Please provide some basic information to begin.")

    with st.form("registration_form"):
        name = st.text_input("Name")
        age = st.number_input("Age", min_value=18, max_value=100, step=1)
        gender = st.radio("Gender", ("Male", "Female", "Other", "Prefer not to say"))

        submitted = st.form_submit_button("Continue")

        if submitted:
            if not name:
                st.warning("Please enter your name.")
            else:
                user_id = st.session_state.get("participant")
                if user_id:
                    if create_user(user_id) and update_user_profile(user_id, name, gender, age):
                        st.success("Information saved!")
                        state_helpers.transition(
                            state_helpers.get_current_phase(),
                            new_phase=ExperimentPhase.INSTRUCTIONS,
                            session_id=st.session_state.session_id,
                        )
                        st.rerun()
                    else:
                        st.error("Failed to save your information. Please try again.")
                else:
                    st.error("User ID not found in session. Cannot save profile.")


def render_instructions_screen():
    """Renders the instructions screen."""
    st.header("Instructions")
    
    # Placeholder for instructions text
    st.markdown(
        """
        **Welcome to the RoboTaste Experiment!**

        Here's what to expect:
        1.  The robot will prepare a liquid sample for you.
        2.  You will be prompted to taste the sample.
        3.  After tasting, you will answer a few questions about its taste.
        4.  You will then use an interface to select your preference for the next sample.
        5.  The process will repeat for several cycles.

        Please rinse your mouth with water between samples.
        """
    )
    
    st.info("Text (TBD)")

    understand_checkbox = st.checkbox("I understand the instructions.")

    if st.button("Start Tasting", disabled=not understand_checkbox):
        state_helpers.transition(
            state_helpers.get_current_phase(),
            new_phase=ExperimentPhase.LOADING,
            session_id=st.session_state.session_id,
        )
        st.rerun()


def get_questionnaire_type_from_config() -> str:
    """
    Retrieve the questionnaire type from the current experiment configuration.

    Returns:
        Questionnaire type string (defaults to 'hedonic' if not found)
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


def grid_interface():
    # SELECTION phase: Show grid and handle selections
    # Sync session state from database for multi-device coordination
    sync_session_state(st.session_state.session_id, "subject")

    # Validate session configuration
    if not st.session_state.get("session_code"):
        st.error("No session found. Please rejoin the session.")
        return

    # Check if moderator has configured the experiment
    if not st.session_state.get("num_ingredients") or not st.session_state.get(
        "interface_type"
    ):
        st.warning(
            "Session not fully configured. Waiting for moderator to start the trial..."
        )
        time.sleep(2)
        st.rerun()
        return

    # Get experiment settings from session state
    num_ingredients = st.session_state.get("num_ingredients", 2)
    interface_type = st.session_state.get("interface_type", INTERFACE_2D_GRID)

    # Get ingredient configuration (preserving moderator's selection)
    if hasattr(st.session_state, "ingredients") and st.session_state.ingredients:
        ingredients = st.session_state.ingredients
    elif (
        hasattr(st.session_state, "experiment_config")
        and "ingredients" in st.session_state.experiment_config
    ):
        ingredients = st.session_state.experiment_config["ingredients"]
    else:
        # Fallback to defaults (backward compatibility)
        ingredients = DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
        st.warning("Using default ingredients - moderator selection not found")

    # Create mixture configuration
    experiment_config = {
        "num_ingredients": num_ingredients,
        "ingredients": ingredients,
    }

    mixture = MultiComponentMixture(experiment_config["ingredients"])

    # Verify interface type matches ingredients
    calculated_interface = mixture.get_interface_type()
    if calculated_interface != interface_type:
        st.warning(
            f"Interface type mismatch. Using calculated: {calculated_interface}"
        )
        interface_type = calculated_interface

    if interface_type == INTERFACE_2D_GRID:
        # Check if Bayesian Optimization should be used

        bo_suggestion = get_bo_suggestion_for_session(
            session_id=st.session_state.session_id,
            participant_id=st.session_state.participant,
        )

        if bo_suggestion:
            # BO MODE: Display read-only canvas with BO marker
            st.markdown("### Next Sample Selected by Optimization")
            st.info(
                "The system has automatically selected your next sample based on "
                "your previous responses to find your optimal taste preference."
            )

            # Create canvas with BO marker (different color)
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.markdown(
                    '<div class="canvas-container">', unsafe_allow_html=True
                )

                # Get BO coordinates
                bo_x = bo_suggestion["grid_coordinates"]["x"]
                bo_y = bo_suggestion["grid_coordinates"]["y"]

                # Get selection history for persistent visualization
                selection_history = getattr(
                    st.session_state, "selection_history", None
                )

                # Store initial position if not set
                if not hasattr(st.session_state, "initial_grid_position"):
                    initial_conc = st.session_state.get("current_tasted_sample", {})
                    if (
                        initial_conc
                        and "Sugar" in initial_conc
                        and "Salt" in initial_conc
                    ):

                        method = st.session_state.get("method", "linear")
                        x, y = (
                            ConcentrationMapper.map_concentrations_to_coordinates(
                                sugar_mm=initial_conc["Sugar"],
                                salt_mm=initial_conc["Salt"],
                                method=method,
                            )
                        )
                        st.session_state.initial_grid_position = {"x": x, "y": y}
                    else:
                        st.session_state.initial_grid_position = {
                            "x": 250,
                            "y": 250,
                        }

                initial_drawing = create_canvas_drawing(
                    st.session_state.initial_grid_position["x"],
                    st.session_state.initial_grid_position["y"],
                    selection_history,  # type: ignore
                )

                # Add BO marker to initial drawing (blue circle)
                if initial_drawing and "objects" in initial_drawing:
                    # Add a blue circle for BO suggestion
                    initial_drawing["objects"].append(
                        {
                            "type": "circle",
                            "left": bo_x,
                            "top": bo_y,
                            "fill": "#8B5CF6",  # Purple for BO marker
                            "stroke": "#6D28D9",
                            "radius": 10,
                            "strokeWidth": 2,
                        }
                    )

                # Display read-only canvas with responsive sizing
                canvas_size = get_canvas_size()

                st_canvas(
                    fill_color="#8B5CF6",
                    stroke_width=2,
                    stroke_color="#6D28D9",
                    background_color="white",
                    update_streamlit=False,  # Read-only
                    height=canvas_size,
                    width=canvas_size,
                    drawing_mode="transform",  # No drawing allowed
                    display_toolbar=False,
                    initial_drawing=initial_drawing,
                    key=f"bo_canvas_{st.session_state.participant}_{st.session_state.session_code}_{canvas_size}",
                )

                st.markdown("</div>", unsafe_allow_html=True)

            # Show BO position
            st.write(f"**Selected Position:** X: {bo_x:.0f}, Y: {bo_y:.0f}")

            # Auto-proceed button
            st.markdown("---")
            if st.button(
                "Proceed to Next Sample",
                type="primary",
                help="Continue with the automatically selected sample",
                key="bo_proceed_button",
            ):
                import uuid

                sample_id = str(uuid.uuid4())
                st.session_state.current_sample_id = sample_id

                # Store BO selection data
                method = st.session_state.get("method", "linear")
                ingredient_concentrations = bo_suggestion["concentrations"]

                # Add BO selection to history for persistent visualization
                if not hasattr(st.session_state, "selection_history"):
                    st.session_state.selection_history = []

                selection_number = len(st.session_state.selection_history) + 1
                st.session_state.selection_history.append(
                    {
                        "x": bo_x,
                        "y": bo_y,
                        "sample_id": sample_id,
                        "order": selection_number,
                        "timestamp": time.time(),
                        "is_bo_suggestion": True,  # Flag to distinguish BO from manual
                    }
                )

                # Prepare selection data with BO metadata
                st.session_state.next_selection_data = {
                    "interface_type": INTERFACE_2D_GRID,
                    "method": "bayesian_optimization",  # Mark as BO-driven
                    "original_method": method,  # Store original mapping method
                    "x_position": bo_x,
                    "y_position": bo_y,
                    "ingredient_concentrations": ingredient_concentrations,
                    "predicted_value": bo_suggestion.get("predicted_value"),
                    "uncertainty": bo_suggestion.get("uncertainty"),
                    "acquisition_value": bo_suggestion.get("acquisition_value"),
                    "acquisition_function": bo_suggestion.get(
                        "acquisition_function"
                    ),
                    "acquisition_params": bo_suggestion.get(
                        "acquisition_params", {}
                    ),
                    "mode": "bayesian_optimization",
                    "sample_id": sample_id,
                }

                # Transition to LOADING
                state_helpers.transition(state_helpers.get_current_phase(),
                    new_phase=ExperimentPhase.LOADING,
                    session_id=st.session_state.session_id,
                )

                # Update current_tasted_sample for next cycle
                st.session_state.current_tasted_sample = (
                    ingredient_concentrations.copy()
                )

                # Clear trajectory
                st.session_state.trajectory_clicks = []

                current_cycle = get_current_cycle(st.session_state.session_id)
                st.success(f"Selection saved! Starting cycle {current_cycle}")
                st.rerun()

        else:
            # MANUAL MODE: Traditional 2D grid interface
            st.markdown("### Make Your Selection")
            st.write(
                "Click anywhere on the grid below to indicate your taste preference."
            )

            # Create canvas with grid and starting position
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.markdown(
                    '<div class="canvas-container">', unsafe_allow_html=True
                )

                # Get selection history for persistent visualization
                selection_history = getattr(
                    st.session_state, "selection_history", None
                )

                # Store initial position permanently (only set once)
                # This ensures the grey dot stays at the original position throughout the session
                if not hasattr(st.session_state, "initial_grid_position"):

                    # Get initial concentrations from database (synced by session_manager)
                    initial_conc = st.session_state.get("current_tasted_sample", {})

                    if (
                        initial_conc
                        and "Sugar" in initial_conc
                        and "Salt" in initial_conc
                    ):
                        # Convert concentrations back to grid coordinates
                        method = st.session_state.get("method", "linear")
                        x, y = (
                            ConcentrationMapper.map_concentrations_to_coordinates(
                                sugar_mm=initial_conc["Sugar"],
                                salt_mm=initial_conc["Salt"],
                                method=method,
                            )
                        )
                        st.session_state.initial_grid_position = {"x": x, "y": y}
                    else:
                        # Fallback to center only if no initial concentrations exist
                        st.session_state.initial_grid_position = {
                            "x": 250,
                            "y": 250,
                        }

                # Always use the stored initial position for grey dot
                x = st.session_state.initial_grid_position["x"]
                y = st.session_state.initial_grid_position["y"]

                initial_drawing = create_canvas_drawing(
                    x,  # Derived from concentrations
                    y,  # Derived from concentrations
                    selection_history,  # type: ignore
                )

                # Get responsive canvas size
                canvas_size = get_canvas_size()
                # Scale point radius proportionally to canvas size
                point_radius = max(5, int(canvas_size / 62.5))

                canvas_result = st_canvas(
                    fill_color=(
                        "#14B8A6"
                        if not st.session_state.get("high_contrast", False)
                        else "#FF0000"
                    ),
                    stroke_width=2,
                    stroke_color=(
                        "#0D9488"
                        if not st.session_state.get("high_contrast", False)
                        else "#000000"
                    ),
                    background_color="white",
                    update_streamlit=True,
                    height=canvas_size,
                    width=canvas_size,
                    drawing_mode="point",
                    point_display_radius=point_radius,
                    display_toolbar=False,
                    initial_drawing=initial_drawing,
                    key=f"subject_canvas_{st.session_state.participant}_{st.session_state.session_code}_{canvas_size}",
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
                                if not hasattr(
                                    st.session_state, "selection_history"
                                ):
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
                                st.session_state.pending_canvas_result = (
                                    canvas_result
                                )
                                st.session_state.pending_method = method

                                # Prepare selection data for next cycle
    
                                sugar_mm, salt_mm = (
                                    ConcentrationMapper.map_coordinates_to_concentrations(
                                        x, y, method=method
                                    )
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
                                    "trajectory": (
                                        st.session_state.trajectory_clicks.copy()
                                        if hasattr(
                                            st.session_state, "trajectory_clicks"
                                        )
                                        else []
                                    ),
                                    "sample_id": sample_id,
                                }

                                # Get current cycle (already incremented in QUESTIONNAIRE phase)
                                current_cycle = get_current_cycle(
                                    st.session_state.session_id
                                )

                                # Transition to LOADING for all selections (cycle 1+)
                                # Note: Cycle 0 has no SELECTION phase - it ends at QUESTIONNAIRE
                                state_helpers.transition(state_helpers.get_current_phase(),
                                    new_phase=ExperimentPhase.LOADING,
                                    session_id=st.session_state.session_id,
                                )

                                # Update current_tasted_sample for next cycle
                                st.session_state.current_tasted_sample = (
                                    ingredient_concentrations.copy()
                                )

                                # Clear trajectory for new cycle
                                st.session_state.trajectory_clicks = []

                                st.success(
                                    f"Selection saved! Starting cycle {current_cycle}"
                                )
                                st.rerun()

                            # Display current position and selection history
                            st.write(
                                f"**Current Position:** X: {x:.0f}, Y: {y:.0f}"
                            )
                            if hasattr(st.session_state, "selection_history"):
                                st.write(
                                    f"**Selections made:** {len(st.session_state.selection_history)}"
                                )
                            break

                except Exception as e:
                    st.error(f"Error processing selection: {e}")

            # Add "Complete Experiment" button for grid interface
            st.markdown("---")
            st.markdown("### Finish Experiment")
            if st.button(
                "Complete Experiment",
                type="secondary",
                help="Mark this as your final selection and end the experiment",
                key="grid_complete_experiment_button",
            ):
                try:
                    # Save final selection data
                    import uuid

                    sample_id = str(uuid.uuid4())
                    st.session_state.current_sample_id = sample_id

                    # Get current grid position and method
                    x = st.session_state.get("x", 50)
                    y = st.session_state.get("y", 50)
                    method = st.session_state.get("method", "linear")

                    # Calculate concentrations for final selection
                    sugar_mm, salt_mm = (
                        ConcentrationMapper.map_coordinates_to_concentrations(
                            x, y, method=method
                        )
                    )
                    ingredient_concentrations = {
                        "Sugar": round(sugar_mm, 3),
                        "Salt": round(salt_mm, 3),
                    }

                    # Prepare final selection data
                    st.session_state.next_selection_data = {
                        "interface_type": INTERFACE_2D_GRID,
                        "method": method,
                        "x_position": x,
                        "y_position": y,
                        "ingredient_concentrations": ingredient_concentrations,
                        "trajectory": (
                            st.session_state.trajectory_clicks.copy()
                            if hasattr(st.session_state, "trajectory_clicks")
                            else []
                        ),
                        "sample_id": sample_id,
                    }

                    # Transition to COMPLETE phase
                    state_helpers.transition(state_helpers.get_current_phase(),
                        new_phase=ExperimentPhase.COMPLETE,
                        session_id=st.session_state.session_id,
                    )

                    st.success("Experiment completed! Thank you for participating.")
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"Error completing experiment: {e}")
                    logger.error(f"Grid interface - Complete experiment error: {e}")

    else:
        # Interface type is not 2D grid - this shouldn't happen in grid_interface
        st.error(
            f"Grid interface called with incorrect interface type: {interface_type}"
        )


def single_variable_interface():
    # SELECTION phase: Show slider and handle selections
    # Sync session state from database for multi-device coordination
    sync_session_state(st.session_state.session_id, "subject")

    # Validate session configuration
    if not st.session_state.get("session_code"):
        st.error("No session found. Please rejoin the session.")
        return

    # Check if moderator has configured the experiment
    if not st.session_state.get("num_ingredients") or not st.session_state.get(
        "interface_type"
    ):
        st.warning(
            "Session not fully configured. Waiting for moderator to start the trial..."
        )
        time.sleep(2)
        st.rerun()
        return

    # Get experiment settings from session state
    num_ingredients = st.session_state.get("num_ingredients", 1)
    interface_type = st.session_state.get(
        "interface_type", INTERFACE_SINGLE_INGREDIENT
    )

    # Validate single ingredient configuration
    if num_ingredients != 1:
        st.error(
            f"Single variable interface requires exactly 1 ingredient, but found {num_ingredients}"
        )
        return

    # Get ingredient configuration
    if hasattr(st.session_state, "ingredients") and st.session_state.ingredients:
        ingredients = st.session_state.ingredients
    elif (
        hasattr(st.session_state, "experiment_config")
        and "ingredients" in st.session_state.experiment_config
    ):
        ingredients = st.session_state.experiment_config["ingredients"]
    else:
        # Fallback to defaults (backward compatibility)
        ingredients = DEFAULT_INGREDIENT_CONFIG[:1]
        st.warning("Using default ingredient - moderator selection not found")

    if not ingredients or len(ingredients) != 1:
        st.error("Single variable interface requires exactly 1 ingredient")
        return

    ingredient = ingredients[0]
    ingredient_name = ingredient["name"]

    # Check if Bayesian Optimization should be used
    bo_suggestion = get_bo_suggestion_for_session(
        session_id=st.session_state.session_id,
        participant_id=st.session_state.participant,
    )

    if bo_suggestion:
        # BO MODE: Display read-only slider with BO marker
        st.markdown("### Next Sample Selected by Optimization")
        st.info(
            "The system has automatically selected your next sample based on "
            "your previous responses to find your optimal taste preference."
        )
        # ... (rest of BO logic)
    else:
        # MANUAL MODE: Traditional slider interface
        st.markdown("### Adjust Concentration")

        # Get initial slider value based on cycle
        initial_value = None
        current_cycle = get_current_cycle(st.session_state.session_id)

        # Load last tasted sample from database for all cycles
        try:
            samples = get_session_samples(st.session_state.session_id)
            if samples:
                last_sample = samples[-1]  # Most recent sample
                selection_data = last_sample.get("selection_data")
                if selection_data:
                    if isinstance(selection_data, str):
                        selection_data = json.loads(selection_data)
                    slider_values = selection_data.get("slider_values", {})
                    if ingredient_name in slider_values:
                        initial_value = slider_values[ingredient_name]
                        logger.info(
                            f"Loaded last sample slider value for cycle {current_cycle}: {initial_value}%"
                        )
        except Exception as e:
            logger.error(f"Error loading last sample from database: {e}")

        # Fallback to session state if database load fails or no samples found
        if initial_value is None:
            if current_cycle == 0 and hasattr(
                st.session_state, "random_slider_values"
            ):
                initial_value = st.session_state.random_slider_values.get(
                    ingredient_name
                )
                if initial_value is not None:
                    logger.info(f"Using random slider value for cycle 0: {initial_value}")
                else:
                    logger.warning("Could not find random slider value for cycle 0")

            elif hasattr(st.session_state, "current_slider_values"):
                initial_value = st.session_state.current_slider_values.get(
                    ingredient_name
                )
                if initial_value is not None:
                    logger.info(f"Using current slider value from session: {initial_value}")
                else:
                    logger.warning("Could not find current slider value in session")

        # If still no value, default to center and log a warning
        if initial_value is None:
            initial_value = 50.0
            logger.warning(
                f"Could not determine initial slider value. Defaulting to {initial_value}."
            )

        # Create interactive slider
        slider_value = st.slider(
            label="Use the slider below to adjust the ingredient concentration.",
            min_value=0,
            max_value=100,
            value=int(initial_value),
            step=1,
            format="",
            key=f"single_slider_{ingredient_name}_{st.session_state.participant}",
        )

        # Update session state
        if not hasattr(st.session_state, "current_slider_values"):
            st.session_state.current_slider_values = {}
        st.session_state.current_slider_values[ingredient_name] = float(
            slider_value
        )

        # Finish Selection button
        st.markdown("---")
        if st.button(
            "Finish Selection",
            type="primary",
            help="Confirm your selection and proceed to the next cycle",
            key="slider_finish_selection_button",
        ):
            import uuid

            sample_id = str(uuid.uuid4())
            st.session_state.current_sample_id = sample_id

            # Calculate concentration from slider value
            mixture = MultiComponentMixture(ingredients)
            concentrations = mixture.calculate_concentrations_from_sliders(
                {ingredient_name: float(slider_value)}
            )

            ingredient_concentrations = {
                ingredient_name: round(
                    concentrations[ingredient_name]["actual_concentration_mM"], 3
                )
            }

            # Add to selection history for visualization
            if not hasattr(st.session_state, "slider_selection_history"):
                st.session_state.slider_selection_history = []

            current_cycle = get_current_cycle(st.session_state.session_id)
            selection_number = len(st.session_state.slider_selection_history) + 1

            st.session_state.slider_selection_history.append(
                {
                    "slider_value": float(slider_value),
                    "cycle": current_cycle,
                    "order": selection_number,
                    "timestamp": time.time(),
                    "sample_id": sample_id,
                }
            )

            # Prepare selection data
            st.session_state.next_selection_data = {
                "interface_type": INTERFACE_SINGLE_INGREDIENT,
                "method": "linear",
                "slider_values": {ingredient_name: float(slider_value)},
                "ingredient_concentrations": ingredient_concentrations,
                "sample_id": sample_id,
            }

            # Transition to LOADING
            state_helpers.transition(
                state_helpers.get_current_phase(),
                new_phase=ExperimentPhase.LOADING,
                session_id=st.session_state.session_id,
            )

            # Update current_tasted_sample for next cycle
            st.session_state.current_tasted_sample = (
                ingredient_concentrations.copy()
            )

            current_cycle = get_current_cycle(st.session_state.session_id)
            st.success(f"Selection saved! Starting cycle {current_cycle}")
            st.rerun()


def init_session_state():
    # Initialize session from URL parameters if not in session state
    if not st.session_state.get("session_id"):
        url_session_code = st.query_params.get("session", "")
        url_role = st.query_params.get("role", "")

        if url_session_code and url_role == "subject":
            # join_session now returns session_id (UUID) if successful
            session_id = join_session(url_session_code)
            if session_id:
                # Store both identifiers in session state
                st.session_state.session_id = session_id
                st.session_state.session_code = url_session_code
                sync_session_state(session_id, "subject")
            else:
                st.error(f"Invalid or expired session code: {url_session_code}")
                if st.button("Return to Home", key="invalid_session_return"):
                    st.query_params.clear()
                    st.rerun()
                return


def subject_interface():
    init_session_state()

    # Get current phase
    current_phase_str = st.session_state.get("phase")
    if not current_phase_str:
        st.warning("Waiting for session to start...")
        sync_session_state(st.session_state.session_id, "subject")
        time.sleep(2)
        st.rerun()
        return

    # Add custom CSS for subject interface
    st.markdown(
        """
        <style>
        /* Enlarge loading spinner - MUCH LARGER */
        .stSpinner {
            text-align: center !important;
        }

        .stSpinner > div {
            font-size: 5rem !important;
            font-weight: 600 !important;
        }

        .stSpinner > div > div {
            font-size: 3.5rem !important;
            margin-top: 2rem !important;
            font-weight: 500 !import
        }

        .stSpinner svg {
            width: 200px !important;
            height: 200px !important;
            display: block !important;
            margin: 0 auto !important;
        }

        /* Enlarge questionnaire fonts */
        div[data-testid="stForm"] {
            font-size: 1.5rem !important;
        }

        div[data-testid="stForm"] h3 {
            font-size: 2.5rem !important;
        }

        div[data-testid="stForm"] strong {
            font-size: 2rem !important;
        }

        div[data-testid="stForm"] .stCaption {
            font-size: 1.5rem !important;
        }

        div[data-testid="stForm"] .stSlider label {
            font-size: 1.8rem !important;
        }

        div[data-testid="stForm"] button[type="submit"] {
            font-size: 2rem !important;
            padding: 1rem 2rem !important;
            min-height: 60px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Central Phase Handling ---

    if current_phase_str == ExperimentPhase.WAITING.value:
        st.info("Waiting for moderator to start the experiment...")
        st.write("The experiment will begin shortly. Please be patient.")
        sync_session_state(st.session_state.session_id, "subject")
        time.sleep(2)
        st.rerun()

    elif current_phase_str == ExperimentPhase.REGISTRATION.value:
        render_registration_screen()

    elif current_phase_str == ExperimentPhase.INSTRUCTIONS.value:
        render_instructions_screen()

    elif current_phase_str in [ExperimentPhase.LOADING.value, ExperimentPhase.ROBOT_PREPARING.value]:
        cycle_num = get_current_cycle(st.session_state.session_id)
        render_loading_spinner(
            message=f"Cycle {cycle_num}: Rinse your mouth while the robot prepares the next sample.",
            load_time=5
        )
        state_helpers.transition(
            state_helpers.get_current_phase(),
            new_phase=ExperimentPhase.QUESTIONNAIRE,
            session_id=st.session_state.session_id,
        )
        st.rerun()

    elif current_phase_str == ExperimentPhase.QUESTIONNAIRE.value:
        cycle_num = get_current_cycle(st.session_state.session_id)
        st.info(f"Cycle {cycle_num}: Please answer the questionnaire about the sample you just tasted")

        questionnaire_type = get_questionnaire_type_from_config()
        responses = render_questionnaire(questionnaire_type, st.session_state.participant)

        if responses:
            st.session_state.questionnaire_responses = responses
            current_cycle = get_current_cycle(st.session_state.session_id)
            ingredient_concentrations = st.session_state.get("current_tasted_sample", {})
            selection_data = st.session_state.get("next_selection_data", {})

            try:
                save_sample_cycle(
                    session_id=st.session_state.session_id,
                    cycle_number=current_cycle,
                    ingredient_concentration=ingredient_concentrations,
                    selection_data=selection_data,
                    questionnaire_answer=responses,
                    is_final=False,
                )
                increment_cycle(st.session_state.session_id)
                state_helpers.transition(
                    state_helpers.get_current_phase(),
                    new_phase=ExperimentPhase.SELECTION,
                    session_id=st.session_state.session_id,
                )
                st.success("Questionnaire saved! Now make your selection for the next cycle.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save questionnaire: {e}")
                logger.error(f"Questionnaire save error: {e}")

    elif current_phase_str == ExperimentPhase.SELECTION.value:
        ingredient_num = st.session_state.get("num_ingredients", None)
        if ingredient_num == 2:
            grid_interface()
        elif ingredient_num == 1:
            single_variable_interface()
        else:
            # Fallback or error for selection phase if ingredient num is not set
            st.warning("Waiting for experiment configuration...")
            sync_session_state(st.session_state.session_id, "subject")
            time.sleep(2)
            st.rerun()
    
    elif current_phase_str == ExperimentPhase.COMPLETE.value:
        from robotaste.views.completion import show_subject_completion_screen
        show_subject_completion_screen()

    else:
        st.error(f"Unknown phase: {current_phase_str}. Returning to waiting.")
        state_helpers.transition(
            state_helpers.get_current_phase(),
            new_phase=ExperimentPhase.WAITING,
            session_id=st.session_state.session_id,
        )
        st.rerun()
