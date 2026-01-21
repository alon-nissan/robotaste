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
from robotaste.core.trials import save_click, prepare_cycle_sample
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
    get_session,
    get_session_samples,
    increment_cycle,
    save_sample_cycle,
)
from robotaste.core.state_machine import ExperimentPhase, ExperimentStateMachine
from robotaste.core import state_helpers
from robotaste.config.questionnaire import get_default_questionnaire_type
from robotaste.core.phase_engine import PhaseEngine
from robotaste.views.custom_phases import render_custom_phase, enter_custom_phase
from robotaste.data.database import get_session_protocol


import streamlit as st
from streamlit_drawable_canvas import st_canvas
import time
import logging
import json
from datetime import datetime

from robotaste.data.database import update_user_profile, create_user


logger = logging.getLogger(__name__)


def get_next_phase_after_selection(session_id: str) -> ExperimentPhase:
    """
    Determine next phase after selection based on pump configuration.

    Args:
        session_id: Session identifier

    Returns:
        ExperimentPhase.ROBOT_PREPARING if pumps are enabled,
        ExperimentPhase.LOADING otherwise
    """
    protocol = get_session_protocol(session_id)
    pump_config = protocol.get("pump_config", {}) if protocol else {}
    pump_enabled = pump_config.get("enabled", False)

    return ExperimentPhase.ROBOT_PREPARING if pump_enabled else ExperimentPhase.LOADING


def transition_to_next_phase(
    current_phase_str: str,
    default_next_phase: ExperimentPhase,
    session_id: str,
    current_cycle: int = None,  # type: ignore
) -> None:
    """
    Transition to next phase using PhaseEngine if available, otherwise use default.

    Args:
        current_phase_str: Current phase as string
        default_next_phase: Default next phase (fallback if no protocol)
        session_id: Session ID
        current_cycle: Current cycle number (optional, for loop logic)
    """
    # Try to load protocol and use PhaseEngine
    protocol = get_session_protocol(session_id)

    if protocol and "phase_sequence" in protocol:
        try:
            phase_engine = PhaseEngine(protocol, session_id)
            next_phase_str = phase_engine.get_next_phase(
                current_phase_str, current_cycle=current_cycle
            )
            next_phase = ExperimentPhase(next_phase_str)
            logger.info(
                f"PhaseEngine transition: {current_phase_str} → {next_phase_str}"
            )
        except Exception as e:
            logger.error(f"PhaseEngine transition failed: {e}, using default")
            next_phase = default_next_phase
    else:
        next_phase = default_next_phase

    # Execute transition
    state_helpers.transition(
        state_helpers.get_current_phase(),
        new_phase=next_phase,
        session_id=session_id,
    )


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
                    if create_user(user_id) and update_user_profile(
                        user_id, name, gender, age
                    ):
                        st.success("Information saved!")
                        transition_to_next_phase(
                            current_phase_str=ExperimentPhase.REGISTRATION.value,
                            default_next_phase=ExperimentPhase.INSTRUCTIONS,
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
        next_phase = get_next_phase_after_selection(st.session_state.session_id)
        transition_to_next_phase(
            current_phase_str=ExperimentPhase.INSTRUCTIONS.value,
            default_next_phase=next_phase,
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


def grid_interface(cycle_data: dict):
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
        st.warning(f"Interface type mismatch. Using calculated: {calculated_interface}")
        interface_type = calculated_interface

    if interface_type != INTERFACE_2D_GRID:
        st.error(
            f"Grid interface called with incorrect interface type: {interface_type}"
        )
        return

    selection_mode = cycle_data.get("mode", "user_selected")

    if selection_mode == "predetermined":
        st.markdown("### Predetermined Sample")
        st.info("This sample was predetermined by the experiment protocol.")
        # Automatically proceed
        time.sleep(3)  # Give user time to read the message
        import uuid

        sample_id = str(uuid.uuid4())
        st.session_state.current_sample_id = sample_id

        predetermined_concentrations = cycle_data.get("concentrations", {})

        st.session_state.next_selection_data = {
            "interface_type": INTERFACE_2D_GRID,
            "method": "predetermined",
            "ingredient_concentrations": predetermined_concentrations,
            "selection_mode": "predetermined",
            "sample_id": sample_id,
        }

        next_phase = get_next_phase_after_selection(st.session_state.session_id)
        state_helpers.transition(
            state_helpers.get_current_phase(),
            new_phase=next_phase,
            session_id=st.session_state.session_id,
        )
        st.session_state.current_tasted_sample = predetermined_concentrations.copy()
        current_cycle = get_current_cycle(st.session_state.session_id)
        st.success(f"Proceeding with predetermined sample for cycle {current_cycle}")
        st.rerun()
        return

    # Handle override state
    if "override_bo" not in st.session_state:
        st.session_state.override_bo = False

    def handle_override():
        st.session_state.override_bo = True

    if selection_mode == "bo_selected" and not st.session_state.override_bo:
        bo_suggestion = cycle_data.get("suggestion")
        if bo_suggestion:
            st.markdown("### Next Sample Selected by Optimization")
            st.info("The system has automatically selected your next sample.")

            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    "Predicted Liking", f"{bo_suggestion.get('predicted_value', 0):.2f}"
                )
            with col2:
                st.metric("Uncertainty", f"{bo_suggestion.get('uncertainty', 0):.2f}")

            # Create canvas with BO marker
            col1, col2, col3 = st.columns([1, 3, 1])
            with col2:
                st.markdown('<div class="canvas-container">', unsafe_allow_html=True)
                bo_x = bo_suggestion["grid_coordinates"]["x"]
                bo_y = bo_suggestion["grid_coordinates"]["y"]
                selection_history = getattr(st.session_state, "selection_history", None)
                if not hasattr(st.session_state, "initial_grid_position"):
                    initial_conc = st.session_state.get("current_tasted_sample", {})
                    if (
                        initial_conc
                        and "Sugar" in initial_conc
                        and "Salt" in initial_conc
                    ):

                        method = st.session_state.get("method", "linear")
                        x, y = ConcentrationMapper.map_concentrations_to_coordinates(
                            sugar_mm=initial_conc["Sugar"],
                            salt_mm=initial_conc["Salt"],
                            method=method,
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
                if initial_drawing and "objects" in initial_drawing:
                    initial_drawing["objects"].append(
                        {
                            "type": "circle",
                            "left": bo_x,
                            "top": bo_y,
                            "fill": "#8B5CF6",
                            "stroke": "#6D28D9",
                            "radius": 10,
                            "strokeWidth": 2,
                        }
                    )

                canvas_size = get_canvas_size()
                st_canvas(
                    fill_color="#8B5CF6",
                    stroke_width=2,
                    stroke_color="#6D28D9",
                    background_color="white",
                    update_streamlit=False,
                    height=canvas_size,
                    width=canvas_size,
                    drawing_mode="transform",
                    display_toolbar=False,
                    initial_drawing=initial_drawing,
                    key=f"bo_canvas_{st.session_state.participant}_{st.session_state.session_code}_{canvas_size}",
                )
                st.markdown("</div>", unsafe_allow_html=True)

            st.write(f"**Selected Position:** X: {bo_x:.0f}, Y: {bo_y:.0f}")

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Proceed to Next Sample", type="primary"):
                    import uuid

                    sample_id = str(uuid.uuid4())
                    st.session_state.current_sample_id = sample_id
                    ingredient_concentrations = bo_suggestion["concentrations"]

                    st.session_state.next_selection_data = {
                        "interface_type": INTERFACE_2D_GRID,
                        "method": "bayesian_optimization",
                        "selection_mode": "bo_selected",
                        "original_method": st.session_state.get("method", "linear"),
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
                        "sample_id": sample_id,
                    }

                    next_phase = get_next_phase_after_selection(
                        st.session_state.session_id
                    )
                    state_helpers.transition(
                        state_helpers.get_current_phase(),
                        new_phase=next_phase,
                        session_id=st.session_state.session_id,
                    )
                    st.session_state.current_tasted_sample = (
                        ingredient_concentrations.copy()
                    )
                    st.session_state.override_bo = False  # Reset for next cycle
                    st.rerun()
            with col2:
                st.button("Override and Select Manually", on_click=handle_override)
            return

    # MANUAL MODE (USER_SELECTED or BO Override)
    if selection_mode == "user_selected" or st.session_state.override_bo:
        st.markdown("### Make Your Selection")
        st.write("Click anywhere on the grid below to indicate your taste preference.")

        # Reset override flag at the beginning of a new selection
        if selection_mode == "user_selected":
            st.session_state.override_bo = False

        col1, col2, col3 = st.columns([1, 3, 1])
        with col2:
            st.markdown('<div class="canvas-container">', unsafe_allow_html=True)
            selection_history = getattr(st.session_state, "selection_history", None)
            if not hasattr(st.session_state, "initial_grid_position"):
                initial_conc = st.session_state.get("current_tasted_sample", {})
                if initial_conc and "Sugar" in initial_conc and "Salt" in initial_conc:
                    method = st.session_state.get("method", "linear")
                    x, y = ConcentrationMapper.map_concentrations_to_coordinates(
                        sugar_mm=initial_conc["Sugar"],
                        salt_mm=initial_conc["Salt"],
                        method=method,
                    )
                    st.session_state.initial_grid_position = {"x": x, "y": y}
                else:
                    st.session_state.initial_grid_position = {"x": 250, "y": 250}

            x_init, y_init = (
                st.session_state.initial_grid_position["x"],
                st.session_state.initial_grid_position["y"],
            )
            initial_drawing = create_canvas_drawing(x_init, y_init, selection_history)  # type: ignore

            canvas_size = get_canvas_size()
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

        if canvas_result and canvas_result.json_data:
            try:
                objects = canvas_result.json_data.get("objects", [])
                for obj in reversed(objects):
                    if obj.get("type") == "circle" and obj.get("fill") in [
                        "#EF4444",
                        "#FF0000",
                    ]:
                        x, y = obj.get("left", 0), obj.get("top", 0)
                        if not hasattr(
                            st.session_state, "last_saved_position"
                        ) or st.session_state.last_saved_position != (x, y):
                            import uuid

                            sample_id = str(uuid.uuid4())
                            st.session_state.current_sample_id = sample_id

                            method = st.session_state.get("method", "linear")
                            save_click(
                                st.session_state.participant,
                                x,
                                y,
                                method,
                                sample_id=sample_id,
                            )
                            st.session_state.last_saved_position = (x, y)

                            sugar_mm, salt_mm = (
                                ConcentrationMapper.map_coordinates_to_concentrations(
                                    x, y, method=method
                                )
                            )
                            ingredient_concentrations = {
                                "Sugar": round(sugar_mm, 3),
                                "Salt": round(salt_mm, 3),
                            }

                            final_selection_mode = (
                                "user_selected_override"
                                if st.session_state.override_bo
                                else "user_selected"
                            )

                            st.session_state.next_selection_data = {
                                "interface_type": INTERFACE_2D_GRID,
                                "method": method,
                                "x_position": x,
                                "y_position": y,
                                "ingredient_concentrations": ingredient_concentrations,
                                "selection_mode": final_selection_mode,
                                "sample_id": sample_id,
                            }

                            next_phase = get_next_phase_after_selection(
                                st.session_state.session_id
                            )
                            state_helpers.transition(
                                state_helpers.get_current_phase(),
                                new_phase=next_phase,
                                session_id=st.session_state.session_id,
                            )
                            st.session_state.current_tasted_sample = (
                                ingredient_concentrations.copy()
                            )
                            st.session_state.override_bo = False  # Reset for next cycle
                            st.rerun()
                        break
            except Exception as e:
                st.error(f"Error processing selection: {e}")

        st.markdown("---")
        st.markdown("### Finish Experiment")
        if st.button(
            "Complete Experiment",
            type="secondary",
            help="Mark this as your final selection and end the experiment",
            key="grid_complete_experiment_button",
        ):
            # ... (code for completing experiment)
            pass


def single_variable_interface(cycle_data: dict):
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
    interface_type = st.session_state.get("interface_type", INTERFACE_SINGLE_INGREDIENT)

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

    selection_mode = cycle_data.get("mode", "user_selected")

    if selection_mode == "predetermined":
        st.markdown("### Predetermined Sample")
        st.info("This sample was predetermined by the experiment protocol.")
        time.sleep(3)
        import uuid

        sample_id = str(uuid.uuid4())
        st.session_state.current_sample_id = sample_id

        predetermined_concentrations = cycle_data.get("concentrations", {})

        st.session_state.next_selection_data = {
            "interface_type": INTERFACE_SINGLE_INGREDIENT,
            "method": "predetermined",
            "ingredient_concentrations": predetermined_concentrations,
            "selection_mode": "predetermined",
            "sample_id": sample_id,
        }

        next_phase = get_next_phase_after_selection(st.session_state.session_id)
        state_helpers.transition(
            state_helpers.get_current_phase(),
            new_phase=next_phase,
            session_id=st.session_state.session_id,
        )
        st.session_state.current_tasted_sample = predetermined_concentrations.copy()
        st.rerun()
        return

    if "override_bo" not in st.session_state:
        st.session_state.override_bo = False

    def handle_override():
        st.session_state.override_bo = True

    if selection_mode == "bo_selected" and not st.session_state.override_bo:
        bo_suggestion = cycle_data.get("suggestion")
        if bo_suggestion:
            st.markdown("### Next Sample Selected by Optimization")
            st.info("The system has automatically selected your next sample.")

            bo_value = bo_suggestion["slider_value"]
            st.slider(
                label="Optimized selection",
                min_value=0,
                max_value=100,
                value=int(bo_value),
                step=1,
                disabled=True,
            )

            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Proceed to Next Sample", type="primary"):
                    import uuid

                    sample_id = str(uuid.uuid4())
                    st.session_state.current_sample_id = sample_id
                    ingredient_concentrations = bo_suggestion["concentrations"]

                    st.session_state.next_selection_data = {
                        "interface_type": INTERFACE_SINGLE_INGREDIENT,
                        "method": "bayesian_optimization",
                        "selection_mode": "bo_selected",
                        "slider_values": {ingredient_name: float(bo_value)},
                        "ingredient_concentrations": ingredient_concentrations,
                        "sample_id": sample_id,
                    }

                    next_phase = get_next_phase_after_selection(
                        st.session_state.session_id
                    )
                    state_helpers.transition(
                        state_helpers.get_current_phase(),
                        new_phase=next_phase,
                        session_id=st.session_state.session_id,
                    )
                    st.session_state.current_tasted_sample = (
                        ingredient_concentrations.copy()
                    )
                    st.session_state.override_bo = False
                    st.rerun()
            with col2:
                st.button("Override and Select Manually", on_click=handle_override)
            return

    if selection_mode == "user_selected" or st.session_state.override_bo:
        st.markdown("### Adjust Concentration")
        if selection_mode == "user_selected":
            st.session_state.override_bo = False

        initial_value = 50.0  # Default
        current_cycle = get_current_cycle(st.session_state.session_id)
        try:
            samples = get_session_samples(st.session_state.session_id)
            if samples:
                last_sample = samples[-1]
                selection_data = last_sample.get("selection_data")
                if selection_data:
                    if isinstance(selection_data, str):
                        selection_data = json.loads(selection_data)
                    slider_values = selection_data.get("slider_values", {})
                    if ingredient_name in slider_values:
                        initial_value = slider_values[ingredient_name]
        except Exception as e:
            logger.error(f"Error loading last sample from database: {e}")

        slider_value = st.slider(
            label="Use the slider below to adjust the ingredient concentration.",
            min_value=0,
            max_value=100,
            value=int(initial_value),
            step=1,
            key=f"single_slider_{ingredient_name}_{st.session_state.participant}",
        )

        if st.button("Finish Selection", type="primary"):
            import uuid

            sample_id = str(uuid.uuid4())
            st.session_state.current_sample_id = sample_id

            mixture = MultiComponentMixture(ingredients)
            concentrations = mixture.calculate_concentrations_from_sliders(
                {ingredient_name: float(slider_value)}
            )
            ingredient_concentrations = {
                ingredient_name: round(
                    concentrations[ingredient_name]["actual_concentration_mM"], 3
                )
            }
            final_selection_mode = (
                "user_selected_override"
                if st.session_state.override_bo
                else "user_selected"
            )

            st.session_state.next_selection_data = {
                "interface_type": INTERFACE_SINGLE_INGREDIENT,
                "method": "linear",
                "slider_values": {ingredient_name: float(slider_value)},
                "ingredient_concentrations": ingredient_concentrations,
                "selection_mode": final_selection_mode,
                "sample_id": sample_id,
            }

            state_helpers.transition(
                state_helpers.get_current_phase(),
                new_phase=ExperimentPhase.LOADING,
                session_id=st.session_state.session_id,
            )
            st.session_state.current_tasted_sample = ingredient_concentrations.copy()
            st.session_state.override_bo = False
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

        /* Progress bar styling for loading screen */
        .stProgress > div > div {
            background-color: #1f77b4 !important;
            height: 20px !important;
            border-radius: 10px !important;
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

    # Load protocol and check for custom phase sequences
    session_id = st.session_state.get("session_id")
    protocol = None
    phase_engine = None

    if session_id:
        protocol = get_session_protocol(session_id)

        # Initialize PhaseEngine if protocol has custom phase_sequence
        if protocol and "phase_sequence" in protocol:
            phase_engine = PhaseEngine(protocol, session_id)

            # Check if current phase is a custom phase
            phase_content = phase_engine.get_phase_content(current_phase_str)

            if phase_content:
                # Render custom phase
                logger.info(f"Rendering custom phase: {current_phase_str}")
                render_custom_phase(current_phase_str, phase_content)

                # Handle phase completion and transition
                if st.session_state.get("phase_complete"):
                    # Check if auto-advance is enabled
                    should_advance, duration_ms = phase_engine.should_auto_advance(
                        current_phase_str
                    )

                    if should_advance and duration_ms:
                        logger.info(f"Auto-advancing after {duration_ms}ms")
                        time.sleep(duration_ms / 1000.0)

                    # Get next phase from engine
                    current_cycle = get_current_cycle(session_id)
                    next_phase_str = phase_engine.get_next_phase(
                        current_phase_str, current_cycle=current_cycle
                    )

                    logger.info(
                        f"Transitioning from {current_phase_str} to {next_phase_str}"
                    )

                    # Update phase in database
                    state_helpers.transition(
                        state_helpers.get_current_phase(),
                        new_phase=ExperimentPhase(next_phase_str),
                        session_id=session_id,
                    )

                    # Clear completion flag
                    st.session_state.phase_complete = False
                    st.rerun()

                return  # Exit early, custom phase handled

    # Fallback to builtin phase rendering
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

    elif current_phase_str == ExperimentPhase.ROBOT_PREPARING.value:
        # Get current cycle
        cycle_num = get_current_cycle(st.session_state.session_id)
        protocol = get_session_protocol(st.session_state.session_id)

        # Check if pump control is enabled
        pump_config = protocol.get("pump_config", {}) if protocol else {}
        pump_enabled = pump_config.get("enabled", False)

        if pump_enabled:
            # Check if pump operation already exists for this cycle (prevent duplicate execution on resume)
            from robotaste.core.pump_integration import get_pump_operation_for_cycle

            existing_operation = get_pump_operation_for_cycle(
                st.session_state.session_id, cycle_num
            )

            # Only execute if no existing operation (fresh entry to phase)
            if existing_operation is None:
                st.info("🤖 Robot is preparing your sample...")

                # Execute pumps synchronously
                from robotaste.core.pump_integration import execute_pumps_synchronously

                result = execute_pumps_synchronously(
                    session_id=st.session_state.session_id,
                    cycle_number=cycle_num,
                    streamlit_container=None,  # Disable UI logging
                )

                # Check result
                if result["success"]:
                    st.success(
                        f"✅ Sample prepared successfully in {result['duration']:.1f}s"
                    )

                    # Get loading screen configuration
                    from robotaste.utils.ui_helpers import (
                        get_loading_screen_config,
                        render_loading_screen,
                    )

                    loading_config = get_loading_screen_config(protocol)

                    # Get total cycles for display
                    total_cycles = None
                    if protocol:
                        stopping_criteria = protocol.get("stopping_criteria", {})
                        total_cycles = stopping_criteria.get("max_cycles")

                    # Determine loading duration
                    loading_screen_config = protocol.get("loading_screen", {}) if protocol else {}
                    use_dynamic = loading_screen_config.get("use_dynamic_duration", False)

                    if use_dynamic and result.get("duration"):
                        # Use pump duration + buffer as loading time
                        duration_seconds = int(result["duration"]) + 5  # Add 5s buffer for rinsing
                    else:
                        # Use configured duration
                        duration_seconds = loading_config.get("duration_seconds", 5)

                    # Show loading screen for participant preparation
                    render_loading_screen(
                        cycle_number=cycle_num,
                        total_cycles=total_cycles,
                        duration_seconds=duration_seconds,
                        **{k: v for k, v in loading_config.items() if k != "duration_seconds"},
                    )

                    # Transition to next phase
                    transition_to_next_phase(
                        current_phase_str=current_phase_str,
                        default_next_phase=ExperimentPhase.QUESTIONNAIRE,
                        session_id=st.session_state.session_id,
                        current_cycle=cycle_num,
                    )
                    st.rerun()

                else:
                    st.error(f"❌ Pump operation failed: {result['error']}")
                    st.stop()

            else:
                # Operation already exists (this is a resume)
                operation_status = existing_operation.get("status", "unknown")

                if operation_status == "completed":
                    st.success("✅ Sample already prepared (resumed session)")
                    # Auto-transition to next phase
                    transition_to_next_phase(
                        current_phase_str=current_phase_str,
                        default_next_phase=ExperimentPhase.QUESTIONNAIRE,
                        session_id=st.session_state.session_id,
                        current_cycle=cycle_num,
                    )
                    st.rerun()

                elif operation_status in ["pending", "in_progress"]:
                    st.warning("⏳ Pump operation in progress... Please wait.")
                    st.info("If this message persists, please contact the moderator.")
                    st.stop()

                elif operation_status == "failed":
                    error_msg = existing_operation.get("error_message", "Unknown error")
                    st.error(f"❌ Previous pump operation failed: {error_msg}")
                    st.error("Please contact the moderator to reset the session.")
                    st.stop()

                else:
                    st.warning(f"⚠️ Unknown pump operation status: {operation_status}")
                    st.error("Please contact the moderator.")
                    st.stop()

        else:
            # Pump control disabled, use standard loading screen
            # Get total cycles from protocol stopping criteria
            total_cycles = None
            if protocol:
                stopping_criteria = protocol.get("stopping_criteria", {})
                total_cycles = stopping_criteria.get("max_cycles")

            # Get loading screen configuration from protocol
            from robotaste.utils.ui_helpers import (
                get_loading_screen_config,
                render_loading_screen,
            )

            loading_config = get_loading_screen_config(protocol)

            # Render dedicated loading screen
            render_loading_screen(
                cycle_number=cycle_num, total_cycles=total_cycles, **loading_config
            )

            # Transition to next phase
            transition_to_next_phase(
                current_phase_str=current_phase_str,
                default_next_phase=ExperimentPhase.QUESTIONNAIRE,
                session_id=st.session_state.session_id,
                current_cycle=cycle_num,
            )
            st.rerun()

    elif current_phase_str == ExperimentPhase.LOADING.value:
        # Get current cycle and total cycles
        cycle_num = get_current_cycle(st.session_state.session_id)
        protocol = get_session_protocol(st.session_state.session_id)

        # Get total cycles from protocol stopping criteria
        total_cycles = None
        if protocol:
            stopping_criteria = protocol.get("stopping_criteria", {})
            total_cycles = stopping_criteria.get("max_cycles")

        # Get loading screen configuration from protocol
        from robotaste.utils.ui_helpers import (
            get_loading_screen_config,
            render_loading_screen,
        )

        loading_config = get_loading_screen_config(protocol)

        # Check if we should use dynamic pump time
        pump_config = protocol.get("pump_config", {}) if protocol else {}
        loading_screen_config = protocol.get("loading_screen", {}) if protocol else {}
        use_dynamic = loading_screen_config.get("use_dynamic_duration", False)

        if pump_config.get("enabled") and use_dynamic:
            # Use calculated pump time if available
            pump_time_key = f"pump_time_cycle_{cycle_num}"
            if pump_time_key in st.session_state:
                duration_seconds = (
                    int(st.session_state[pump_time_key]) + 2
                )  # Add 2s for safety
                logger.info(
                    f"Using dynamic loading duration: {duration_seconds}s (from pump time)"
                )
            else:
                duration_seconds = loading_config.get("duration_seconds", 5)
        else:
            duration_seconds = loading_config.get("duration_seconds", 5)

        # Render dedicated loading screen
        render_loading_screen(
            cycle_number=cycle_num,
            total_cycles=total_cycles,
            duration_seconds=duration_seconds,
            **{k: v for k, v in loading_config.items() if k != "duration_seconds"},
        )

        # Transition to next phase
        transition_to_next_phase(
            current_phase_str=current_phase_str,
            default_next_phase=ExperimentPhase.QUESTIONNAIRE,
            session_id=st.session_state.session_id,
            current_cycle=cycle_num,
        )
        st.rerun()

    elif current_phase_str == ExperimentPhase.QUESTIONNAIRE.value:
        cycle_num = get_current_cycle(st.session_state.session_id)
        st.info(
            f"Cycle {cycle_num}: Please answer the questionnaire about the sample you just tasted"
        )

        questionnaire_type = get_questionnaire_type_from_config()
        responses = render_questionnaire(
            questionnaire_type, st.session_state.participant
        )

        if responses:
            st.session_state.questionnaire_responses = responses
            current_cycle = get_current_cycle(st.session_state.session_id)
            ingredient_concentrations = st.session_state.get(
                "current_tasted_sample", {}
            )
            selection_data = st.session_state.get("next_selection_data", {})

            # GUARD: Don't save if sample is empty (not yet prepared)
            if not ingredient_concentrations:
                logger.warning(
                    f"Cycle {current_cycle}: Sample not prepared yet, skipping save"
                )
                st.warning("Please wait for sample to be prepared...")
                time.sleep(1)
                st.rerun()
                return

            try:
                # Extract selection mode from selection_data or determine from protocol
                selection_mode = selection_data.get("selection_mode", "user_selected")
                if not selection_mode or selection_mode == "unknown":
                    # Fall back to determining from protocol
                    from robotaste.core.trials import (
                        get_selection_mode_for_cycle_runtime,
                    )

                    selection_mode = get_selection_mode_for_cycle_runtime(
                        st.session_state.session_id, current_cycle
                    )

                # Save the questionnaire data for current cycle
                save_sample_cycle(
                    session_id=st.session_state.session_id,
                    cycle_number=current_cycle,
                    ingredient_concentration=ingredient_concentrations,
                    selection_data=selection_data,
                    questionnaire_answer=responses,
                    is_final=False,
                    selection_mode=selection_mode,
                )

                # Check if we should stop BEFORE incrementing
                session = get_session(st.session_state.session_id)
                if session:
                    protocol = session.get("experiment_config", {})
                    max_cycles = protocol.get("stopping_criteria", {}).get("max_cycles")

                    if max_cycles and current_cycle >= max_cycles:
                        # We've completed all required cycles - go to completion
                        logger.info(
                            f"Completed all {max_cycles} cycles. Transitioning to completion."
                        )
                        state_helpers.transition(
                            state_helpers.get_current_phase(),
                            new_phase=ExperimentPhase.COMPLETE,
                            session_id=st.session_state.session_id,
                        )
                        st.success(
                            f"Experiment complete! You have finished all {max_cycles} cycles."
                        )
                        st.rerun()
                        return

                # Not stopping - increment to next cycle
                increment_cycle(st.session_state.session_id)

                # Transition to next phase
                transition_to_next_phase(
                    current_phase_str=current_phase_str,
                    default_next_phase=ExperimentPhase.SELECTION,
                    session_id=st.session_state.session_id,
                    current_cycle=current_cycle + 1,  # Pass the NEW cycle number
                )
                st.success(
                    "Questionnaire saved! Now make your selection for the next cycle."
                )
                st.rerun()
            except Exception as e:
                st.error(f"Failed to save questionnaire: {e}")
                logger.error(f"Questionnaire save error: {e}")

    elif current_phase_str == ExperimentPhase.SELECTION.value:
        cycle_info = prepare_cycle_sample(
            st.session_state.session_id, get_current_cycle(st.session_state.session_id)
        )
        st.session_state.cycle_data = cycle_info

        # For predetermined/BO samples, populate current_tasted_sample and auto-advance
        if cycle_info.get("concentrations") and cycle_info["mode"] in [
            "predetermined",
            "bo_selected",
        ]:
            st.session_state.current_tasted_sample = cycle_info["concentrations"].copy()
            st.session_state.next_selection_data = {
                "mode": cycle_info["mode"],
                "timestamp": datetime.now().isoformat(),
            }

            # Check if pump control is enabled to determine next phase
            next_phase = get_next_phase_after_selection(st.session_state.session_id)
            logger.info(
                f"Auto-advancing to {next_phase.value} for {cycle_info['mode']} sample"
            )
            state_helpers.transition(
                state_helpers.get_current_phase(),
                new_phase=next_phase,
                session_id=st.session_state.session_id,
            )
            st.rerun()
            return

        # Otherwise show selection UI for user-selected mode
        ingredient_num = st.session_state.get("num_ingredients", None)
        if ingredient_num == 2:
            grid_interface(cycle_info)
        elif ingredient_num == 1:
            single_variable_interface(cycle_info)
        else:
            # Fallback or error for selection phase if ingredient num is not set
            st.warning("Waiting for experiment configuration...")
            sync_session_state(st.session_state.session_id, "subject")
            time.sleep(2)
            st.rerun()

    elif current_phase_str == ExperimentPhase.COMPLETE.value:
        # Cleanup pumps when session completes
        try:
            from robotaste.core.pump_manager import cleanup_pumps

            cleanup_pumps(st.session_state.session_id)
            logger.info(f"Cleaned up pumps for session {st.session_state.session_id}")
        except Exception as e:
            logger.warning(f"Error cleaning up pumps: {e}")

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
