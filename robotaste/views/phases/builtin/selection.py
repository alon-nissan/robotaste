"""
Selection Phase Renderer

Displays selection interface based on experiment configuration.
Supports 2D grid (binary mixtures) and 1D slider (single ingredient).
Handles user selection, predetermined, and BO-selected modes.

Author: AI Agent (extracted from robotaste/views/subject.py)
Date: 2026-01-27
"""

import streamlit as st
from streamlit_drawable_canvas import st_canvas
import time
import logging
import json
import uuid
from typing import Dict, Any
from robotaste.data.database import get_current_cycle, get_session_samples
from robotaste.data.session_repo import sync_session_state_to_streamlit as sync_session_state
from robotaste.core.trials import save_click
from robotaste.core.calculations import (
    INTERFACE_2D_GRID,
    INTERFACE_SINGLE_INGREDIENT,
    MultiComponentMixture,
    ConcentrationMapper,
)
from robotaste.components.canvas import (
    get_canvas_size,
    create_canvas_drawing,
)
from robotaste.config.defaults import DEFAULT_INGREDIENT_CONFIG

logger = logging.getLogger(__name__)


def render_selection(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render selection interface.
    
    Displays appropriate UI based on experiment configuration:
    - 2D grid for binary mixtures
    - 1D slider for single ingredient
    
    Handles three selection modes:
    - user_selected: Manual selection by participant
    - predetermined: Pre-configured concentration from protocol
    - bo_selected: Bayesian optimization suggestion
    
    Sets phase_complete when selection is made.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    # Sync session state from database for multi-device coordination
    sync_session_state(session_id, "subject")
    
    # Validate session configuration
    if not st.session_state.get("session_code"):
        st.error("No session found. Please rejoin the session.")
        return
    
    # Check if moderator has configured the experiment
    if not st.session_state.get("num_ingredients") or not st.session_state.get("interface_type"):
        st.warning(
            "Session not fully configured. Waiting for moderator to start the trial..."
        )
        time.sleep(2)
        st.rerun()
        return
    
    # Get experiment settings
    num_ingredients = st.session_state.get("num_ingredients", 2)
    interface_type = st.session_state.get("interface_type", INTERFACE_2D_GRID)
    
    # Get current cycle and prepare cycle data
    current_cycle = get_current_cycle(session_id)
    
    # Get cycle data (selection mode and suggestions)
    # This would normally come from trials.py prepare_cycle_sample()
    from robotaste.core.trials import prepare_cycle_sample
    cycle_data = prepare_cycle_sample(session_id, current_cycle)
    
    # Route to appropriate interface
    if interface_type == INTERFACE_2D_GRID:
        _render_grid_interface(session_id, protocol, cycle_data)
    elif interface_type == INTERFACE_SINGLE_INGREDIENT:
        _render_single_variable_interface(session_id, protocol, cycle_data)
    else:
        st.error(f"Unknown interface type: {interface_type}")
        logger.error(f"Session {session_id}: Unknown interface type: {interface_type}")


def _render_grid_interface(session_id: str, protocol: Dict[str, Any], cycle_data: dict) -> None:
    """Render 2D grid interface for binary mixtures."""
    # Get experiment settings from session state
    num_ingredients = st.session_state.get("num_ingredients", 2)
    interface_type = st.session_state.get("interface_type", INTERFACE_2D_GRID)
    
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
        ingredients = DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
        st.warning("Using default ingredients - moderator selection not found")
    
    mixture = MultiComponentMixture(ingredients)
    
    # Verify interface type matches ingredients
    calculated_interface = mixture.get_interface_type()
    if calculated_interface != interface_type:
        st.warning(f"Interface type mismatch. Using calculated: {calculated_interface}")
        interface_type = calculated_interface
    
    if interface_type != INTERFACE_2D_GRID:
        st.error(f"Grid interface called with incorrect interface type: {interface_type}")
        return
    
    selection_mode = cycle_data.get("mode", "user_selected")
    
    # PREDETERMINED MODE
    if selection_mode in ["predetermined", "predetermined_absolute", "predetermined_randomized"]:
        st.markdown("### Predetermined Sample")
        st.info("This sample was predetermined by the experiment protocol.")
        # Automatically proceed
        time.sleep(3)  # Give user time to read the message
        
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
        st.session_state.current_tasted_sample = predetermined_concentrations.copy()
        
        # Mark phase as complete
        st.session_state.phase_complete = True
        current_cycle = get_current_cycle(session_id)
        st.success(f"Proceeding with predetermined sample for cycle {current_cycle}")
        logger.info(
            f"Session {session_id}: Predetermined selection for cycle {current_cycle}"
        )
        return
    
    # Handle override state
    if "override_bo" not in st.session_state:
        st.session_state.override_bo = False
    
    def handle_override():
        st.session_state.override_bo = True
    
    # BO SELECTED MODE
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
                            "fill": "#fda50f",
                            "stroke": "#521924",
                            "radius": 10,
                            "strokeWidth": 2,
                        }
                    )
                
                canvas_size = get_canvas_size()
                st_canvas(
                    fill_color="#fda50f",
                    stroke_width=2,
                    stroke_color="#521924",
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
                        "acquisition_function": bo_suggestion.get("acquisition_function"),
                        "acquisition_params": bo_suggestion.get("acquisition_params", {}),
                        "sample_id": sample_id,
                    }
                    st.session_state.current_tasted_sample = ingredient_concentrations.copy()
                    st.session_state.override_bo = False  # Reset for next cycle
                    
                    # Mark phase as complete
                    st.session_state.phase_complete = True
                    logger.info(
                        f"Session {session_id}: BO selection accepted "
                        f"(cycle {get_current_cycle(session_id)})"
                    )
                    # Don't call st.rerun() - let PhaseRouter handle navigation
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
                    "#14B8A6" if not st.session_state.get("high_contrast", False) else "#FF0000"
                ),
                stroke_width=2,
                stroke_color=(
                    "#0D9488" if not st.session_state.get("high_contrast", False) else "#000000"
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
                    if obj.get("type") == "circle" and obj.get("fill") in ["#EF4444", "#FF0000"]:
                        x, y = obj.get("left", 0), obj.get("top", 0)
                        if not hasattr(st.session_state, "last_saved_position") or st.session_state.last_saved_position != (x, y):
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
                            st.session_state.current_tasted_sample = ingredient_concentrations.copy()
                            st.session_state.override_bo = False  # Reset for next cycle
                            
                            # Mark phase as complete
                            st.session_state.phase_complete = True
                            logger.info(
                                f"Session {session_id}: User selection made "
                                f"(cycle {get_current_cycle(session_id)}, x={x}, y={y})"
                            )
                            # Don't call st.rerun() - let PhaseRouter handle navigation
                        break
            except Exception as e:
                st.error(f"Error processing selection: {e}")
                logger.error(f"Session {session_id}: Error processing selection: {e}")


def _render_single_variable_interface(session_id: str, protocol: Dict[str, Any], cycle_data: dict) -> None:
    """Render 1D slider interface for single ingredient."""
    # Get experiment settings from session state
    num_ingredients = st.session_state.get("num_ingredients", 1)
    
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
    
    # PREDETERMINED MODE
    if selection_mode in ["predetermined", "predetermined_absolute", "predetermined_randomized"]:
        st.markdown("### Predetermined Sample")
        st.info("This sample was predetermined by the experiment protocol.")
        time.sleep(3)
        
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
        st.session_state.current_tasted_sample = predetermined_concentrations.copy()
        
        # Mark phase as complete
        st.session_state.phase_complete = True
        logger.info(
            f"Session {session_id}: Predetermined single-var selection "
            f"(cycle {get_current_cycle(session_id)})"
        )
        return
    
    if "override_bo" not in st.session_state:
        st.session_state.override_bo = False
    
    def handle_override():
        st.session_state.override_bo = True
    
    # BO SELECTED MODE
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
                    st.session_state.current_tasted_sample = ingredient_concentrations.copy()
                    st.session_state.override_bo = False
                    
                    # Mark phase as complete
                    st.session_state.phase_complete = True
                    logger.info(
                        f"Session {session_id}: BO single-var selection accepted "
                        f"(cycle {get_current_cycle(session_id)})"
                    )
                    # Don't call st.rerun() - let PhaseRouter handle navigation
            with col2:
                st.button("Override and Select Manually", on_click=handle_override)
            return
    
    # MANUAL MODE
    if selection_mode == "user_selected" or st.session_state.override_bo:
        st.markdown("### Adjust Concentration")
        if selection_mode == "user_selected":
            st.session_state.override_bo = False
        
        initial_value = 50.0  # Default
        current_cycle = get_current_cycle(session_id)
        try:
            samples = get_session_samples(session_id)
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
            logger.error(f"Session {session_id}: Error loading last sample: {e}")
        
        slider_value = st.slider(
            label="Use the slider below to adjust the ingredient concentration.",
            min_value=0,
            max_value=100,
            value=int(initial_value),
            step=1,
            key=f"single_slider_{ingredient_name}_{st.session_state.participant}",
        )
        
        if st.button("Finish Selection", type="primary"):
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
            st.session_state.current_tasted_sample = ingredient_concentrations.copy()
            st.session_state.override_bo = False
            
            # Mark phase as complete
            st.session_state.phase_complete = True
            logger.info(
                f"Session {session_id}: User single-var selection made "
                f"(cycle {current_cycle}, slider={slider_value})"
            )
            # Don't call st.rerun() - let PhaseRouter handle navigation
