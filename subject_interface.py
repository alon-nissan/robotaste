from callback import (
    CANVAS_SIZE,
    INTERFACE_2D_GRID,
    INTERFACE_SINGLE_INGREDIENT,
    MultiComponentMixture,
    cleanup_pending_results,
    create_canvas_drawing,
    render_questionnaire,
    save_intermediate_click,
    render_loading_spinner,
)
from session_manager import (
    get_session_info,
    join_session,
    sync_session_state,
)
from sql_handler import (
    get_current_cycle,
    get_session_samples,
    increment_cycle,
    save_sample_cycle,
)
from state_machine import ExperimentStateMachine, ExperimentPhase, initialize_phase
from questionnaire_config import get_default_questionnaire_type


import streamlit as st
from streamlit_drawable_canvas import st_canvas
import time
import logging
import json
from datetime import datetime

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


def grid_interface():
    # WAITING phase: Poll database for moderator to start trial
    if st.session_state.phase == "waiting":
        st.info("Waiting for moderator to start the experiment...")
        st.write("The experiment will begin shortly. Please be patient.")

        # Poll database for phase changes from moderator
        sync_session_state(st.session_state.session_id, "subject")
        time.sleep(2)
        st.rerun()
        return

    # LOADING phase: Show spinner and transition to QUESTIONNAIRE
    elif (
        st.session_state.phase == "loading"
        or st.session_state.phase == "robot_preparing"
    ):
        # Show cycle number
        cycle_num = get_current_cycle(st.session_state.session_id)
        render_loading_spinner(
            message=f"Cycle {cycle_num}: Robot is preparing your sample...", load_time=5
        )

        # Transition to QUESTIONNAIRE using state machine
        ExperimentStateMachine.transition(
            new_phase=ExperimentPhase.QUESTIONNAIRE,
            session_id=st.session_state.session_id,
        )
        st.rerun()
        return

    # QUESTIONNAIRE phase: Show questionnaire and transition to SELECTION
    elif st.session_state.phase == "questionnaire":
        # Show cycle number
        cycle_num = get_current_cycle(st.session_state.session_id)
        st.info(
            f"Cycle {cycle_num}: Please answer the questionnaire about the sample you just tasted"
        )

        questionnaire_type = get_questionnaire_type_from_config()
        responses = render_questionnaire(
            questionnaire_type, st.session_state.participant
        )

        if responses:  # Questionnaire submitted
            # Store responses
            st.session_state.questionnaire_responses = responses

            # Get current cycle and sample data
            current_cycle = get_current_cycle(st.session_state.session_id)
            ingredient_concentrations = st.session_state.get(
                "current_tasted_sample", {}
            )
            selection_data = st.session_state.get("next_selection_data", {})

            # Save cycle data to database
            try:
                sample_id = save_sample_cycle(
                    session_id=st.session_state.session_id,
                    cycle_number=current_cycle,
                    ingredient_concentration=ingredient_concentrations,
                    selection_data=selection_data,
                    questionnaire_answer=responses,
                    is_final=False,
                )

                # Increment cycle counter
                new_cycle = increment_cycle(st.session_state.session_id)
                st.session_state.cycle_number = new_cycle

                # Check convergence and potentially show stopping dialog
                try:
                    from bayesian_optimizer import check_convergence
                    from sql_handler import get_session

                    session = get_session(st.session_state.session_id)
                    if session:
                        experiment_config = session.get("experiment_config", {})
                        bo_config = experiment_config.get("bayesian_optimization", {})
                        stopping_criteria = bo_config.get("stopping_criteria", {})
                        stopping_mode = stopping_criteria.get("stopping_mode", "manual_only")

                        # Only check if convergence detection is enabled and mode is not manual_only
                        if stopping_criteria.get("enabled", True) and stopping_mode != "manual_only":
                            convergence = check_convergence(st.session_state.session_id, stopping_criteria)

                            # Track consecutive converged cycles
                            if "consecutive_converged" not in st.session_state:
                                st.session_state.consecutive_converged = 0

                            consecutive_required = stopping_criteria.get("consecutive_required", 2)

                            if convergence.get("converged", False):
                                st.session_state.consecutive_converged += 1
                            else:
                                st.session_state.consecutive_converged = 0

                            # Check if we should suggest stopping
                            if st.session_state.consecutive_converged >= consecutive_required or \
                               convergence.get("recommendation") == "stop_recommended":

                                # Show stopping dialog (only if in suggest_auto mode)
                                if stopping_mode == "suggest_auto":
                                    st.balloons()
                                    st.success("🎉 Optimal preference found!")
                                    st.info(f"**{convergence.get('reason', 'Session converged')}**")

                                    # Show metrics
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Cycles Completed", convergence["metrics"].get("current_cycle", 0))
                                    with col2:
                                        best_values = convergence["metrics"].get("best_values", [])
                                        if best_values:
                                            st.metric("Best Rating", f"{max(best_values):.2f}")
                                    with col3:
                                        st.metric("Confidence", f"{convergence.get('confidence', 0)*100:.0f}%")

                                    st.markdown("---")
                                    st.markdown("### Would you like to end the session now?")
                                    st.caption("You've reached the optimal taste preference with high confidence.")

                                    col_end, col_continue = st.columns(2)

                                    with col_end:
                                        if st.button("🛑 End Session Now", type="primary", key="end_session_subject", use_container_width=True):
                                            # Transition to COMPLETE phase
                                            if ExperimentStateMachine.transition(
                                                new_phase=ExperimentPhase.COMPLETE,
                                                session_id=st.session_state.session_id,
                                            ):
                                                st.success("✅ Session ended successfully! Thank you for participating.")
                                                time.sleep(2)
                                                st.rerun()
                                            else:
                                                st.error("Failed to end session")
                                                # Proceed normally if ending fails
                                                ExperimentStateMachine.transition(
                                                    new_phase=ExperimentPhase.SELECTION,
                                                    session_id=st.session_state.session_id,
                                                )
                                                st.rerun()

                                    with col_continue:
                                        if st.button("➡️ Continue Exploring", key="continue_session_subject", use_container_width=True):
                                            # Reset consecutive counter and proceed normally
                                            st.session_state.consecutive_converged = 0
                                            ExperimentStateMachine.transition(
                                                new_phase=ExperimentPhase.SELECTION,
                                                session_id=st.session_state.session_id,
                                            )
                                            st.rerun()

                                    # Don't proceed automatically - wait for user choice
                                    return

                                # Auto-end mode
                                elif stopping_mode == "auto_with_minimum":
                                    st.balloons()
                                    st.success("🎉 Optimal preference found! Session ending automatically...")
                                    time.sleep(2)
                                    if ExperimentStateMachine.transition(
                                        new_phase=ExperimentPhase.COMPLETE,
                                        session_id=st.session_state.session_id,
                                    ):
                                        st.success("✅ Session ended successfully! Thank you for participating.")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error("Failed to end session, continuing...")

                except Exception as e:
                    logger.warning(f"Error checking convergence for stopping dialog: {e}")
                    # Continue normally if convergence check fails

                # Transition to SELECTION using state machine
                ExperimentStateMachine.transition(
                    new_phase=ExperimentPhase.SELECTION,
                    session_id=st.session_state.session_id,
                )
                st.success(
                    "Questionnaire saved! Now make your selection for the next cycle."
                )
                st.rerun()

            except Exception as e:
                st.error(f"Failed to save questionnaire: {e}")
                logger.error(f"Questionnaire save error: {e}")
        return

    # SELECTION phase: Show grid and handle selections
    elif st.session_state.phase == "selection":
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
            from callback import DEFAULT_INGREDIENT_CONFIG

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
            from callback import get_bo_suggestion_for_session

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
                            from callback import ConcentrationMapper

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
                                "fill": "#3B82F6",  # Blue for BO marker
                                "stroke": "#1D4ED8",
                                "radius": 10,
                                "strokeWidth": 2,
                            }
                        )

                    # Display read-only canvas
                    st_canvas(
                        fill_color="#3B82F6",
                        stroke_width=2,
                        stroke_color="#1D4ED8",
                        background_color="white",
                        update_streamlit=False,  # Read-only
                        height=CANVAS_SIZE,
                        width=CANVAS_SIZE,
                        drawing_mode="transform",  # No drawing allowed
                        display_toolbar=False,
                        initial_drawing=initial_drawing,
                        key=f"bo_canvas_{st.session_state.participant}_{st.session_state.session_code}",
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
                        "mode": "bayesian_optimization",
                        "sample_id": sample_id,
                    }

                    # Transition to LOADING
                    ExperimentStateMachine.transition(
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
                        from callback import ConcentrationMapper

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
                                    from callback import ConcentrationMapper

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
                                    ExperimentStateMachine.transition(
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
                        from callback import ConcentrationMapper
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
                        ExperimentStateMachine.transition(
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
    # WAITING phase: Poll database for moderator to start trial
    if st.session_state.phase == "waiting":
        st.info("Waiting for moderator to start the experiment...")
        st.write("The experiment will begin shortly. Please be patient.")

        # Poll database for phase changes from moderator
        sync_session_state(st.session_state.session_id, "subject")
        time.sleep(2)
        st.rerun()
        return

    # LOADING phase: Show spinner and transition to QUESTIONNAIRE
    elif (
        st.session_state.phase == "loading"
        or st.session_state.phase == "robot_preparing"
    ):
        # Show cycle number
        cycle_num = get_current_cycle(st.session_state.session_id)
        render_loading_spinner(
            message=f"Cycle {cycle_num}: Robot is preparing your sample...", load_time=5
        )

        # Transition to QUESTIONNAIRE using state machine
        ExperimentStateMachine.transition(
            new_phase=ExperimentPhase.QUESTIONNAIRE,
            session_id=st.session_state.session_id,
        )
        st.rerun()
        return

    # QUESTIONNAIRE phase: Show questionnaire and transition to SELECTION
    elif st.session_state.phase == "questionnaire":
        # Show cycle number
        cycle_num = get_current_cycle(st.session_state.session_id)
        st.info(
            f"Cycle {cycle_num}: Please answer the questionnaire about the sample you just tasted"
        )

        questionnaire_type = get_questionnaire_type_from_config()
        responses = render_questionnaire(
            questionnaire_type, st.session_state.participant
        )

        if responses:  # Questionnaire submitted
            # Store responses
            st.session_state.questionnaire_responses = responses

            # Get current cycle and sample data
            current_cycle = get_current_cycle(st.session_state.session_id)
            ingredient_concentrations = st.session_state.get(
                "current_tasted_sample", {}
            )
            selection_data = st.session_state.get("next_selection_data", {})

            # For cycle 0, populate selection_data with initial random position
            if current_cycle == 0 and not selection_data:
                # Get ingredient info
                ingredients = st.session_state.get("ingredients", [])
                if ingredients and len(ingredients) == 1:
                    ingredient = ingredients[0]
                    ingredient_name = ingredient["name"]

                    # Get initial random slider value
                    random_slider_values = st.session_state.get(
                        "random_slider_values", {}
                    )
                    initial_slider_value = random_slider_values.get(
                        ingredient_name, 50.0
                    )

                    # Create selection data for initial position
                    selection_data = {
                        "interface_type": INTERFACE_SINGLE_INGREDIENT,
                        "method": "initial_random",
                        "slider_values": {ingredient_name: initial_slider_value},
                        "ingredient_concentrations": ingredient_concentrations.copy(),
                        "is_initial_position": True,
                    }
                    st.session_state.next_selection_data = selection_data

            # Save cycle data to database
            try:
                sample_id = save_sample_cycle(
                    session_id=st.session_state.session_id,
                    cycle_number=current_cycle,
                    ingredient_concentration=ingredient_concentrations,
                    selection_data=selection_data,
                    questionnaire_answer=responses,
                    is_final=False,
                )

                # Increment cycle counter
                new_cycle = increment_cycle(st.session_state.session_id)
                st.session_state.cycle_number = new_cycle

                # Check convergence and potentially show stopping dialog
                try:
                    from bayesian_optimizer import check_convergence
                    from sql_handler import get_session

                    session = get_session(st.session_state.session_id)
                    if session:
                        experiment_config = session.get("experiment_config", {})
                        bo_config = experiment_config.get("bayesian_optimization", {})
                        stopping_criteria = bo_config.get("stopping_criteria", {})
                        stopping_mode = stopping_criteria.get("stopping_mode", "manual_only")

                        # Only check if convergence detection is enabled and mode is not manual_only
                        if stopping_criteria.get("enabled", True) and stopping_mode != "manual_only":
                            convergence = check_convergence(st.session_state.session_id, stopping_criteria)

                            # Track consecutive converged cycles
                            if "consecutive_converged" not in st.session_state:
                                st.session_state.consecutive_converged = 0

                            consecutive_required = stopping_criteria.get("consecutive_required", 2)

                            if convergence.get("converged", False):
                                st.session_state.consecutive_converged += 1
                            else:
                                st.session_state.consecutive_converged = 0

                            # Check if we should suggest stopping
                            if st.session_state.consecutive_converged >= consecutive_required or \
                               convergence.get("recommendation") == "stop_recommended":

                                # Show stopping dialog (only if in suggest_auto mode)
                                if stopping_mode == "suggest_auto":
                                    st.balloons()
                                    st.success("🎉 Optimal preference found!")
                                    st.info(f"**{convergence.get('reason', 'Session converged')}**")

                                    # Show metrics
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Cycles Completed", convergence["metrics"].get("current_cycle", 0))
                                    with col2:
                                        best_values = convergence["metrics"].get("best_values", [])
                                        if best_values:
                                            st.metric("Best Rating", f"{max(best_values):.2f}")
                                    with col3:
                                        st.metric("Confidence", f"{convergence.get('confidence', 0)*100:.0f}%")

                                    st.markdown("---")
                                    st.markdown("### Would you like to end the session now?")
                                    st.caption("You've reached the optimal taste preference with high confidence.")

                                    col_end, col_continue = st.columns(2)

                                    with col_end:
                                        if st.button("🛑 End Session Now", type="primary", key="end_session_subject", use_container_width=True):
                                            # Transition to COMPLETE phase
                                            if ExperimentStateMachine.transition(
                                                new_phase=ExperimentPhase.COMPLETE,
                                                session_id=st.session_state.session_id,
                                            ):
                                                st.success("✅ Session ended successfully! Thank you for participating.")
                                                time.sleep(2)
                                                st.rerun()
                                            else:
                                                st.error("Failed to end session")
                                                # Proceed normally if ending fails
                                                ExperimentStateMachine.transition(
                                                    new_phase=ExperimentPhase.SELECTION,
                                                    session_id=st.session_state.session_id,
                                                )
                                                st.rerun()

                                    with col_continue:
                                        if st.button("➡️ Continue Exploring", key="continue_session_subject", use_container_width=True):
                                            # Reset consecutive counter and proceed normally
                                            st.session_state.consecutive_converged = 0
                                            ExperimentStateMachine.transition(
                                                new_phase=ExperimentPhase.SELECTION,
                                                session_id=st.session_state.session_id,
                                            )
                                            st.rerun()

                                    # Don't proceed automatically - wait for user choice
                                    return

                                # Auto-end mode
                                elif stopping_mode == "auto_with_minimum":
                                    st.balloons()
                                    st.success("🎉 Optimal preference found! Session ending automatically...")
                                    time.sleep(2)
                                    if ExperimentStateMachine.transition(
                                        new_phase=ExperimentPhase.COMPLETE,
                                        session_id=st.session_state.session_id,
                                    ):
                                        st.success("✅ Session ended successfully! Thank you for participating.")
                                        time.sleep(2)
                                        st.rerun()
                                    else:
                                        st.error("Failed to end session, continuing...")

                except Exception as e:
                    logger.warning(f"Error checking convergence for stopping dialog: {e}")
                    # Continue normally if convergence check fails

                # Transition to SELECTION using state machine
                ExperimentStateMachine.transition(
                    new_phase=ExperimentPhase.SELECTION,
                    session_id=st.session_state.session_id,
                )
                st.success(
                    "Questionnaire saved! Now make your selection for the next cycle."
                )
                st.rerun()

            except Exception as e:
                st.error(f"Failed to save questionnaire: {e}")
                logger.error(f"Questionnaire save error: {e}")
        return

    # SELECTION phase: Show slider and handle selections
    elif st.session_state.phase == "selection":
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
            from callback import DEFAULT_INGREDIENT_CONFIG

            ingredients = DEFAULT_INGREDIENT_CONFIG[:1]
            st.warning("Using default ingredient - moderator selection not found")

        if not ingredients or len(ingredients) != 1:
            st.error("Single variable interface requires exactly 1 ingredient")
            return

        ingredient = ingredients[0]
        ingredient_name = ingredient["name"]

        # Check if Bayesian Optimization should be used
        from callback import get_bo_suggestion_for_session

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

            # Get BO slider value
            bo_slider_value = bo_suggestion.get("slider_values", {}).get(
                ingredient_name, 50.0
            )

            # Display read-only slider
            st.slider(
                label=f"Suggested Concentration",
                min_value=0,
                max_value=100,
                value=int(bo_slider_value),
                step=1,
                disabled=True,
                format="",
                key=f"bo_slider_{ingredient_name}_{st.session_state.participant}",
            )

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
                ingredient_concentrations = bo_suggestion["concentrations"]

                # Add to selection history for visualization
                if not hasattr(st.session_state, "slider_selection_history"):
                    st.session_state.slider_selection_history = []

                current_cycle = get_current_cycle(st.session_state.session_id)
                selection_number = len(st.session_state.slider_selection_history) + 1

                st.session_state.slider_selection_history.append(
                    {
                        "slider_value": float(bo_slider_value),
                        "cycle": current_cycle,
                        "order": selection_number,
                        "timestamp": time.time(),
                        "sample_id": sample_id,
                        "is_bo_suggestion": True,
                    }
                )

                # Prepare selection data with BO metadata
                st.session_state.next_selection_data = {
                    "interface_type": INTERFACE_SINGLE_INGREDIENT,
                    "method": "bayesian_optimization",  # Mark as BO-driven
                    "slider_values": {ingredient_name: bo_slider_value},
                    "ingredient_concentrations": ingredient_concentrations,
                    "predicted_value": bo_suggestion.get("predicted_value"),
                    "uncertainty": bo_suggestion.get("uncertainty"),
                    "acquisition_value": bo_suggestion.get("acquisition_value"),
                    "mode": "bayesian_optimization",
                    "sample_id": sample_id,
                }

                # Transition to LOADING
                ExperimentStateMachine.transition(
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

        else:
            # MANUAL MODE: Traditional slider interface
            st.markdown("### Adjust Concentration")
            st.write(f"Use the slider below to adjust the ingredient concentration.")

            # Get initial slider value based on cycle
            # ALL Cycles 0-2: Load LAST SAMPLE from database (what they tasted)
            # Cycle 3+: Handled by BO mode above
            initial_value = 50.0
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
                # Fall back to session state if database load fails
                if current_cycle == 0 and hasattr(
                    st.session_state, "random_slider_values"
                ):
                    initial_value = st.session_state.random_slider_values.get(
                        ingredient_name, 50.0
                    )
                elif hasattr(st.session_state, "current_slider_values"):
                    initial_value = st.session_state.current_slider_values.get(
                        ingredient_name, initial_value
                    )

            # Create interactive slider
            slider_value = st.slider(
                label=f"Choose your next sample",
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
                ExperimentStateMachine.transition(
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

            # Complete Experiment button
            st.markdown("---")
            st.markdown("### Finish Experiment")
            if st.button(
                "Complete Experiment",
                type="secondary",
                help="Mark this as your final selection and end the experiment",
                key="slider_complete_experiment_button",
            ):
                try:
                    # Save final selection data
                    import uuid

                    sample_id = str(uuid.uuid4())
                    st.session_state.current_sample_id = sample_id

                    # Get current slider value
                    slider_value = st.session_state.current_slider_values.get(
                        ingredient_name, 50.0
                    )

                    # Calculate concentrations for final selection
                    mixture = MultiComponentMixture(ingredients)
                    concentrations = mixture.calculate_concentrations_from_sliders(
                        {ingredient_name: float(slider_value)}
                    )

                    ingredient_concentrations = {
                        ingredient_name: round(
                            concentrations[ingredient_name]["actual_concentration_mM"],
                            3,
                        )
                    }

                    # Prepare final selection data
                    st.session_state.next_selection_data = {
                        "interface_type": INTERFACE_SINGLE_INGREDIENT,
                        "method": "linear",
                        "slider_values": {ingredient_name: float(slider_value)},
                        "ingredient_concentrations": ingredient_concentrations,
                        "sample_id": sample_id,
                    }

                    # Transition to COMPLETE phase
                    ExperimentStateMachine.transition(
                        new_phase=ExperimentPhase.COMPLETE,
                        session_id=st.session_state.session_id,
                    )

                    st.success("Experiment completed! Thank you for participating.")
                    time.sleep(2)
                    st.rerun()

                except Exception as e:
                    st.error(f"Error completing experiment: {e}")
                    logger.error(
                        f"Single variable interface - Complete experiment error: {e}"
                    )


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

    # Sync phase from database on every load (handles st.rerun() race condition)
    if st.session_state.get("session_id"):
        sync_session_state(st.session_state.session_id, "subject")

    # Check for COMPLETE phase and show completion screen
    if st.session_state.get("phase") == "complete":
        from completion_screens import show_subject_completion_screen
        show_subject_completion_screen()
        return

    ingredient_num = st.session_state.get("num_ingredients", None)
    if ingredient_num == 2:
        grid_interface()
    elif ingredient_num == 1:
        single_variable_interface()
    else:
        st.error(f"Unsupported ingredient number: {ingredient_num}")
