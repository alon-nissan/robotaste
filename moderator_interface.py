from callback import (
    INTERFACE_2D_GRID,
    INTERFACE_SINGLE_INGREDIENT,
    MultiComponentMixture,
    clear_canvas_state,
    start_trial,
    calculate_stock_volumes,
)
from session_manager import (
    display_session_qr_code,
    get_session_info,
)
from sql_handler import (
    create_session,
    get_session,
    update_current_phase,
    get_current_cycle,
    get_session_samples,
    export_session_csv,
    get_session_stats,
    get_bo_config,
    update_session_state,
    get_latest_sample_concentrations,
    get_database_connection,
    get_training_data,
    get_questionnaire_type_id,
)
from state_machine import (
    ExperimentPhase,
    ExperimentStateMachine,
    InvalidTransitionError,
    initialize_phase,
    recover_phase_from_database,
)
from bayesian_optimizer import get_default_bo_config, validate_bo_config

from questionnaire_config import (
    list_available_questionnaires,
    get_default_questionnaire_type,
    get_questionnaire_config,
)

import streamlit as st
import pandas as pd
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def _render_bo_config(key_prefix: str):
    """
    Render Bayesian Optimization configuration UI (shared by single and binary setups).

    Args:
        key_prefix: Unique prefix for widget keys (e.g., "single_" or "binary_")
    """
    # Initialize BO config in session state
    if "bo_config" not in st.session_state:
        st.session_state.bo_config = get_default_bo_config()

    st.markdown("#### Bayesian Optimization Settings")

    # Enable/disable BO
    bo_enabled = st.checkbox(
        "Enable Bayesian Optimization",
        value=st.session_state.bo_config.get("enabled", True),
        help="Use machine learning to guide participants toward optimal preferences after initial exploration",
        key=f"{key_prefix}bo_enabled",
    )
    st.session_state.bo_config["enabled"] = bo_enabled

    if bo_enabled:
        col1, col2 = st.columns(2)

        with col1:
            # Acquisition function selector
            acq_func = st.selectbox(
                "Acquisition Function:",
                options=["ei", "ucb"],
                index=(
                    0
                    if st.session_state.bo_config["acquisition_function"] == "ei"
                    else 1
                ),
                format_func=lambda x: (
                    "Expected Improvement (EI) - Recommended"
                    if x == "ei"
                    else "Upper Confidence Bound (UCB)"
                ),
                help="EI: Balanced exploration-exploitation. UCB: More exploration of uncertain regions",
                key=f"{key_prefix}bo_acq_func",
            )
            st.session_state.bo_config["acquisition_function"] = acq_func

            # Minimum samples before BO activates
            min_samples = st.number_input(
                "Min Samples Before BO:",
                min_value=2,
                max_value=10,
                value=st.session_state.bo_config["min_samples_for_bo"],
                step=1,
                help="Number of random exploration samples before BO starts making intelligent suggestions. Default: 3",
                key=f"{key_prefix}bo_min_samples",
            )
            st.session_state.bo_config["min_samples_for_bo"] = min_samples

        with col2:
            # Dynamic exploration parameter (changes based on acquisition function)
            if acq_func == "ei":
                xi = st.slider(
                    "Exploration Parameter (xi):",
                    min_value=0.0,
                    max_value=0.1,
                    value=st.session_state.bo_config["ei_xi"],
                    step=0.01,
                    format="%.3f",
                    help="Controls exploration vs exploitation. Higher = more exploration. Default: 0.01",
                    key=f"{key_prefix}bo_xi",
                )
                st.session_state.bo_config["ei_xi"] = xi
            else:  # UCB
                kappa = st.slider(
                    "Exploration Parameter (kappa):",
                    min_value=0.1,
                    max_value=5.0,
                    value=st.session_state.bo_config["ucb_kappa"],
                    step=0.1,
                    help="Controls exploration vs exploitation. Higher = more exploration. Default: 2.0",
                    key=f"{key_prefix}bo_kappa",
                )
                st.session_state.bo_config["ucb_kappa"] = kappa

            # Kernel smoothness (ν parameter)
            kernel_options = {
                0.5: "0.5 - Rough (for noisy data)",
                1.5: "1.5 - Moderate (threshold effects)",
                2.5: "2.5 - Smooth (recommended)",
                float("inf"): "∞ - Very Smooth (theoretical)",
            }
            current_nu = st.session_state.bo_config["kernel_nu"]
            nu_index = (
                list(kernel_options.keys()).index(current_nu)
                if current_nu in kernel_options
                else 2
            )

            kernel_nu = st.selectbox(
                "Kernel Smoothness (ν):",
                options=list(kernel_options.keys()),
                index=nu_index,
                format_func=lambda x: kernel_options[x],
                help="How smooth taste preferences are assumed to be. See docs/bayesian_optimization_kernel_guide.md",
                key=f"{key_prefix}bo_kernel_nu",
            )
            st.session_state.bo_config["kernel_nu"] = kernel_nu

        # Advanced settings expander
        with st.expander("Advanced BO Settings", expanded=False):
            st.caption(
                "For expert users. Leave at defaults unless you understand these parameters."
            )

            adv_col1, adv_col2 = st.columns(2)

            with adv_col1:
                # Noise/regularization parameter
                alpha = st.number_input(
                    "Noise/Regularization (alpha):",
                    min_value=1e-6,
                    max_value=1.0,
                    value=float(st.session_state.bo_config["alpha"]),
                    format="%.6f",
                    help="Higher = more noise tolerance. Use higher values for untrained consumer panels. Default: 0.001",
                    key=f"{key_prefix}bo_alpha",
                )
                st.session_state.bo_config["alpha"] = alpha

                # Only use final responses
                only_final = st.checkbox(
                    "Only Use Final Responses",
                    value=st.session_state.bo_config["only_final_responses"],
                    help="Train BO only on participants' final choices (recommended)",
                    key=f"{key_prefix}bo_only_final",
                )
                st.session_state.bo_config["only_final_responses"] = only_final

            with adv_col2:
                # Optimizer restarts
                n_restarts = st.number_input(
                    "Hyperparameter Optimizer Restarts:",
                    min_value=1,
                    max_value=50,
                    value=st.session_state.bo_config["n_restarts_optimizer"],
                    step=1,
                    help="More restarts = better hyperparameter optimization but slower. Default: 10",
                    key=f"{key_prefix}bo_restarts",
                )
                st.session_state.bo_config["n_restarts_optimizer"] = n_restarts

                # Random seed
                random_state = st.number_input(
                    "Random Seed:",
                    min_value=0,
                    max_value=9999,
                    value=st.session_state.bo_config["random_state"],
                    step=1,
                    help="For reproducibility. Default: 42",
                    key=f"{key_prefix}bo_seed",
                )
                st.session_state.bo_config["random_state"] = random_state

        # Stopping Criteria Configuration
        with st.expander("Session Ending / Stopping Criteria", expanded=False):
            st.caption(
                "Configure when the session should end based on convergence detection"
            )

            # Initialize stopping criteria if not present
            if "stopping_criteria" not in st.session_state.bo_config:
                default_config = get_default_bo_config()
                st.session_state.bo_config["stopping_criteria"] = default_config[
                    "stopping_criteria"
                ].copy()

            stop_criteria = st.session_state.bo_config["stopping_criteria"]

            # Enable/disable convergence detection
            stop_enabled = st.checkbox(
                "Enable Automatic Convergence Detection",
                value=stop_criteria.get("enabled", True),
                help="Automatically detect when BO has converged and suggest ending the session",
                key=f"{key_prefix}stop_enabled",
            )
            stop_criteria["enabled"] = stop_enabled

            if stop_enabled:
                # Determine current number of ingredients from session state
                n_ingredients = 1  # Default assumption
                if "ingredients" in st.session_state:
                    n_ingredients = len(st.session_state.get("ingredients", []))
                elif "num_ingredients" in st.session_state:
                    n_ingredients = st.session_state.get("num_ingredients", 1)

                # Stopping mode
                mode_options = {
                    "manual_only": "Manual Only - Show status but don't suggest stopping",
                    "suggest_auto": "Semi-Automatic - Show dialog when converged (Recommended)",
                    "auto_with_minimum": "Automatic - Auto-end after minimum samples IF converged",
                }
                current_mode = stop_criteria.get("stopping_mode", "suggest_auto")
                mode_index = (
                    list(mode_options.keys()).index(current_mode)
                    if current_mode in mode_options
                    else 1
                )

                stopping_mode = st.selectbox(
                    "Stopping Mode:",
                    options=list(mode_options.keys()),
                    index=mode_index,
                    format_func=lambda x: mode_options[x],
                    help="How the system should behave when convergence is detected",
                    key=f"{key_prefix}stop_mode",
                )
                stop_criteria["stopping_mode"] = stopping_mode

                st.markdown("**Sample Limits:**")

                stop_col1, stop_col2 = st.columns(2)

                with stop_col1:
                    # Min cycles (dimension-specific)
                    if n_ingredients == 1:
                        min_cycles = st.number_input(
                            "Minimum Cycles (1D):",
                            min_value=5,
                            max_value=50,
                            value=stop_criteria.get("min_cycles_1d", 10),
                            step=1,
                            help="Minimum samples before considering convergence. Research recommends: 10-15 for single ingredient",
                            key=f"{key_prefix}stop_min_1d",
                        )
                        stop_criteria["min_cycles_1d"] = min_cycles
                    else:
                        min_cycles = st.number_input(
                            "Minimum Cycles (2D+):",
                            min_value=10,
                            max_value=100,
                            value=stop_criteria.get("min_cycles_2d", 15),
                            step=1,
                            help="Minimum samples before considering convergence. Research recommends: 15-20 for binary mixtures",
                            key=f"{key_prefix}stop_min_2d",
                        )
                        stop_criteria["min_cycles_2d"] = min_cycles

                with stop_col2:
                    # Max cycles (dimension-specific)
                    if n_ingredients == 1:
                        max_cycles = st.number_input(
                            "Maximum Cycles (1D):",
                            min_value=min_cycles + 5,
                            max_value=100,
                            value=stop_criteria.get("max_cycles_1d", 30),
                            step=1,
                            help="Hard stop - end session at this many samples even if not converged. Research recommends: 30 for single ingredient",
                            key=f"{key_prefix}stop_max_1d",
                        )
                        stop_criteria["max_cycles_1d"] = max_cycles
                    else:
                        max_cycles = st.number_input(
                            "Maximum Cycles (2D+):",
                            min_value=min_cycles + 10,
                            max_value=200,
                            value=stop_criteria.get("max_cycles_2d", 50),
                            step=1,
                            help="Hard stop - end session at this many samples even if not converged. Research recommends: 50 for binary mixtures",
                            key=f"{key_prefix}stop_max_2d",
                        )
                        stop_criteria["max_cycles_2d"] = max_cycles

                st.markdown("**Convergence Thresholds:**")

                thresh_col1, thresh_col2 = st.columns(2)

                with thresh_col1:
                    # EI threshold
                    ei_thresh = st.number_input(
                        "Expected Improvement Threshold:",
                        min_value=0.0001,
                        max_value=0.1,
                        value=stop_criteria.get("ei_threshold", 0.001),
                        step=0.0001,
                        format="%.4f",
                        help="EI below this value indicates convergence (little expected gain from next sample). Lower = stop sooner. Research default: 0.001",
                        key=f"{key_prefix}stop_ei",
                    )
                    stop_criteria["ei_threshold"] = ei_thresh

                    # Stability window
                    stab_window = st.number_input(
                        "Stability Window:",
                        min_value=3,
                        max_value=10,
                        value=stop_criteria.get("stability_window", 5),
                        step=1,
                        help="Number of recent cycles to check for stability. Default: 5",
                        key=f"{key_prefix}stop_window",
                    )
                    stop_criteria["stability_window"] = stab_window

                with thresh_col2:
                    # Stability threshold
                    stab_thresh = st.number_input(
                        "Stability Threshold (std dev):",
                        min_value=0.01,
                        max_value=0.5,
                        value=stop_criteria.get("stability_threshold", 0.05),
                        step=0.01,
                        format="%.2f",
                        help="Standard deviation of recent best values below this indicates stable optimum. Lower = stricter. Default: 0.05",
                        key=f"{key_prefix}stop_stab",
                    )
                    stop_criteria["stability_threshold"] = stab_thresh

                    # Consecutive required
                    consec = st.number_input(
                        "Consecutive Converged Cycles:",
                        min_value=1,
                        max_value=5,
                        value=stop_criteria.get("consecutive_required", 2),
                        step=1,
                        help="Require convergence criteria to be met for N consecutive cycles (prevents false positives). Default: 2",
                        key=f"{key_prefix}stop_consec",
                    )
                    stop_criteria["consecutive_required"] = consec

                # Use recommended defaults button
                if st.button(
                    "Reset to Research-Based Defaults", key=f"{key_prefix}stop_defaults"
                ):
                    default_config = get_default_bo_config()
                    st.session_state.bo_config["stopping_criteria"] = default_config[
                        "stopping_criteria"
                    ].copy()
                    st.rerun()

                st.info(
                    f"**Current Settings:** "
                    f"Session will run {min_cycles}-{max_cycles} cycles. "
                    f"Convergence detected when EI < {ei_thresh:.4f} AND "
                    f"stability σ < {stab_thresh:.2f} for {consec} consecutive cycles."
                )

        st.caption(
            "For detailed guidance on kernel selection and BO parameters, see `docs/bayesian_optimization_kernel_guide.md`"
        )


def show_single_ingredient_setup():
    """Single ingredient setup with compact vertical layout."""
    from callback import DEFAULT_INGREDIENT_CONFIG
    from questionnaire_config import (
        list_available_questionnaires,
        get_default_questionnaire_type,
        get_questionnaire_config,
    )
    from sql_handler import update_session_with_config

    st.markdown("### Single Ingredient Setup")

    # ===== INGREDIENT SELECTION =====
    available_ingredients = [ing["name"] for ing in DEFAULT_INGREDIENT_CONFIG]

    # Initialize selected ingredient in session state
    if "selected_ingredients" not in st.session_state:
        st.session_state.selected_ingredients = [available_ingredients[0]]

    selected_ingredient = st.selectbox(
        "Ingredient:",
        options=available_ingredients,
        index=(
            available_ingredients.index(st.session_state.selected_ingredients[0])
            if st.session_state.selected_ingredients
            else 0
        ),
        help="Select the ingredient to explore",
        key="single_ingredient_selector",
    )

    # Update session state
    st.session_state.selected_ingredients = [selected_ingredient]

    # ===== CONCENTRATION RANGE =====
    st.markdown("**Concentration Range**")

    # Initialize ingredient ranges in session state
    if "ingredient_ranges" not in st.session_state:
        st.session_state.ingredient_ranges = {}

    # Get default ranges from DEFAULT_INGREDIENT_CONFIG
    default_ingredient = next(
        (
            ing
            for ing in DEFAULT_INGREDIENT_CONFIG
            if ing["name"] == selected_ingredient
        ),
        None,
    )
    default_min = (
        default_ingredient.get("min_concentration", 0.0) if default_ingredient else 0.0
    )
    default_max = (
        default_ingredient.get("max_concentration", 20.0)
        if default_ingredient
        else 20.0
    )

    # Initialize with defaults if not set
    if selected_ingredient not in st.session_state.ingredient_ranges:
        st.session_state.ingredient_ranges[selected_ingredient] = {
            "min": default_min,
            "max": default_max,
        }

    current_range = st.session_state.ingredient_ranges[selected_ingredient]

    # Create input fields for min and max
    min_col, max_col = st.columns(2)
    with min_col:
        min_val = st.number_input(
            "Min (mM)",
            min_value=0.0,
            max_value=1000.0,
            value=current_range["min"],
            step=0.1,
            key="single_min_concentration",
            help=f"Minimum concentration for {selected_ingredient}",
        )
    with max_col:
        max_val = st.number_input(
            "Max (mM)",
            min_value=0.1,
            max_value=1000.0,
            value=current_range["max"],
            step=0.1,
            key="single_max_concentration",
            help=f"Maximum concentration for {selected_ingredient}",
        )

    # Validation: ensure min < max
    if min_val >= max_val:
        st.error(f"Min must be less than Max for {selected_ingredient}")
    else:
        # Update session state
        st.session_state.ingredient_ranges[selected_ingredient] = {
            "min": min_val,
            "max": max_val,
        }

    st.markdown("---")

    # ===== STARTING POSITION CONFIGURATION =====
    st.markdown("**Starting Position**")
    use_random_start = st.checkbox(
        "Randomize starting position",
        value=True,
        help="Start slider at random position (10-90%) instead of center (50%)",
    )
    st.session_state.use_random_start = use_random_start

    st.markdown("---")

    # ===== QUESTIONNAIRE CONFIGURATION =====
    st.markdown("**Questionnaire**")

    # Get available questionnaires
    available_questionnaires = list_available_questionnaires()
    questionnaire_options = {q[0]: f"{q[1]} - {q[2]}" for q in available_questionnaires}

    # Initialize questionnaire type in session state
    if "selected_questionnaire_type" not in st.session_state:
        st.session_state.selected_questionnaire_type = get_default_questionnaire_type()

    # Questionnaire selector
    selected_questionnaire_type = st.selectbox(
        "Type:",
        options=list(questionnaire_options.keys()),
        format_func=lambda x: questionnaire_options[x],
        index=list(questionnaire_options.keys()).index(
            st.session_state.selected_questionnaire_type
        ),
        help="Select the type of questionnaire participants will complete",
        key="single_questionnaire_selector",
    )

    # Update session state
    st.session_state.selected_questionnaire_type = selected_questionnaire_type

    # Show questionnaire preview
    questionnaire_config = get_questionnaire_config(selected_questionnaire_type)  # type: ignore
    if questionnaire_config:
        with st.expander("Preview Questionnaire Questions", expanded=False):
            st.markdown(f"**{questionnaire_config['name']}**")
            st.caption(questionnaire_config.get("description", ""))

            for i, question in enumerate(questionnaire_config.get("questions", []), 1):
                st.markdown(f"{i}. **{question['label']}**")
                st.caption(f"   Type: {question['type'].title()}")
                if question["type"] == "slider":
                    st.caption(f"   Range: {question['min']} - {question['max']}")
                    if "scale_labels" in question:
                        st.caption(
                            f"   Labels: {question['min']}=\"{question['scale_labels'].get(question['min'], '')}\" ... {question['max']}=\"{question['scale_labels'].get(question['max'], '')}\""
                        )
                elif question["type"] == "dropdown":
                    st.caption(f"   Options: {', '.join(question.get('options', []))}")

            # Show Bayesian optimization target
            if "bayesian_target" in questionnaire_config:
                st.markdown("---")
                st.markdown("**Bayesian Optimization Target:**")
                target = questionnaire_config["bayesian_target"]
                st.caption(f"Variable: {target['variable']}")
                st.caption(f"Goal: {target['description']}")

    st.markdown("---")

    # ===== BAYESIAN OPTIMIZATION CONFIGURATION =====
    with st.expander("Bayesian Optimization", expanded=False):
        _render_bo_config("single_")

    st.markdown("---")

    # ===== START TRIAL BUTTON =====
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Show current participant
        participant_display = st.session_state.get("participant", "None selected")
        st.caption(f"**Participant:** {participant_display}")
        if st.button(
            "Start Trial",
            type="primary",
            width="stretch",
            key="single_start_trial_button",
        ):
            # Validation
            if min_val >= max_val:
                st.error("Please fix the concentration range (min must be < max)")
                st.stop()

            # Save full session configuration to database if not already saved
            if not st.session_state.get("session_config_saved", False):
                # Build ingredient list for database
                ingredients_for_db = [
                    {
                        "position": 0,
                        "name": selected_ingredient,
                        "min": min_val,
                        "max": max_val,
                        "unit": "mM",
                    }
                ]

                # Get BO config or use defaults
                bo_config = st.session_state.get("bo_config", get_default_bo_config())

                # Build full experiment config
                full_experiment_config = {
                    "num_ingredients": 1,
                    "interface_type": "sliders",
                    "moderator_name": st.session_state.get(
                        "moderator_name", "Moderator"
                    ),
                    "selected_ingredients": st.session_state.selected_ingredients,
                    "ingredient_ranges": st.session_state.ingredient_ranges,
                }

                # Create/update session in database
                # Convert questionnaire type name to integer ID
                questionnaire_name = st.session_state.get(
                    "selected_questionnaire_type", "hedonic_preference"
                )
                question_type_id = get_questionnaire_type_id(questionnaire_name)
                if question_type_id is None:
                    st.error(f"Invalid questionnaire type: {questionnaire_name}")
                    st.stop()

                success_db = update_session_with_config(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.get(
                        "participant", None
                    ),  # Use None if not set
                    num_ingredients=1,
                    interface_type="sliders",
                    method="linear",  # Sliders always use linear mapping
                    ingredients=ingredients_for_db,
                    question_type_id=question_type_id,
                    bo_config=bo_config,
                    experiment_config=full_experiment_config,
                )

                if success_db:
                    st.session_state.session_config_saved = True
                    st.success("Session configured and saved to database")
                else:
                    st.error("Failed to save session configuration. Please try again.")
                    st.stop()

            # Build ingredient configs with custom ranges
            ingredient_configs = []
            base_config = next(
                (
                    ing
                    for ing in DEFAULT_INGREDIENT_CONFIG
                    if ing["name"] == selected_ingredient
                ),
                None,
            )

            if not base_config:
                st.error(
                    f"Ingredient '{selected_ingredient}' not found in configuration"
                )
                st.stop()

            # Create a copy and apply custom ranges
            custom_config = base_config.copy()
            custom_config["min_concentration"] = min_val
            custom_config["max_concentration"] = max_val
            ingredient_configs.append(custom_config)

            # Set method to linear (for sliders)
            st.session_state.selected_method = "linear"

            # Start trial
            success = start_trial(
                "mod",
                st.session_state.participant,
                "linear",  # Sliders use linear mapping
                1,  # num_ingredients
                selected_ingredients=st.session_state.selected_ingredients,
                ingredient_configs=ingredient_configs,
            )

            if success:
                clear_canvas_state()
                st.toast(f"Trial started for {st.session_state.participant}")
                time.sleep(1)
                st.rerun()


def show_binary_mixture_setup():
    """Binary mixture setup with 2-column symmetrical layout."""
    from callback import DEFAULT_INGREDIENT_CONFIG
    from questionnaire_config import (
        list_available_questionnaires,
        get_default_questionnaire_type,
        get_questionnaire_config,
    )
    from sql_handler import update_session_with_config

    st.markdown("### Binary Mixture Setup")

    # ===== INGREDIENT SELECTION (2-COLUMN LAYOUT) =====
    available_ingredients = [ing["name"] for ing in DEFAULT_INGREDIENT_CONFIG]

    # Initialize selected ingredients in session state
    if (
        "selected_ingredients" not in st.session_state
        or len(st.session_state.selected_ingredients) != 2
    ):
        st.session_state.selected_ingredients = [
            available_ingredients[0],
            available_ingredients[1],
        ]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Ingredient 1**")
        ingredient_1 = st.selectbox(
            "Select:",
            options=available_ingredients,
            index=available_ingredients.index(st.session_state.selected_ingredients[0]),
            help="First ingredient in binary mixture",
            key="binary_ingredient_1_selector",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown("**Ingredient 2**")
        ingredient_2 = st.selectbox(
            "Select:",
            options=available_ingredients,
            index=available_ingredients.index(st.session_state.selected_ingredients[1]),
            help="Second ingredient in binary mixture",
            key="binary_ingredient_2_selector",
            label_visibility="collapsed",
        )

    # Validation: ingredients must be different
    if ingredient_1 == ingredient_2:
        st.error("Please select two different ingredients")
    else:
        st.session_state.selected_ingredients = [ingredient_1, ingredient_2]

    # ===== CONCENTRATION RANGES (2-COLUMN LAYOUT) =====
    # Initialize ingredient ranges in session state
    if "ingredient_ranges" not in st.session_state:
        st.session_state.ingredient_ranges = {}

    col1, col2 = st.columns(2)

    # Ingredient 1 range
    with col1:
        st.markdown("**Range (mM)**")
        default_ing_1 = next(
            (ing for ing in DEFAULT_INGREDIENT_CONFIG if ing["name"] == ingredient_1),
            None,
        )
        default_min_1 = (
            default_ing_1.get("min_concentration", 0.0) if default_ing_1 else 0.0
        )
        default_max_1 = (
            default_ing_1.get("max_concentration", 20.0) if default_ing_1 else 20.0
        )

        if ingredient_1 not in st.session_state.ingredient_ranges:
            st.session_state.ingredient_ranges[ingredient_1] = {
                "min": default_min_1,
                "max": default_max_1,
            }

        current_range_1 = st.session_state.ingredient_ranges[ingredient_1]

        min_col1, max_col1 = st.columns(2)
        with min_col1:
            min_val_1 = st.number_input(
                "Min",
                min_value=0.0,
                max_value=1000.0,
                value=current_range_1["min"],
                step=0.1,
                key="binary_min_1",
            )
        with max_col1:
            max_val_1 = st.number_input(
                "Max",
                min_value=0.1,
                max_value=1000.0,
                value=current_range_1["max"],
                step=0.1,
                key="binary_max_1",
            )

        if min_val_1 >= max_val_1:
            st.error(f"Min < Max required")
        else:
            st.session_state.ingredient_ranges[ingredient_1] = {
                "min": min_val_1,
                "max": max_val_1,
            }

    # Ingredient 2 range
    with col2:
        st.markdown("**Range (mM)**")
        default_ing_2 = next(
            (ing for ing in DEFAULT_INGREDIENT_CONFIG if ing["name"] == ingredient_2),
            None,
        )
        default_min_2 = (
            default_ing_2.get("min_concentration", 0.0) if default_ing_2 else 0.0
        )
        default_max_2 = (
            default_ing_2.get("max_concentration", 20.0) if default_ing_2 else 20.0
        )

        if ingredient_2 not in st.session_state.ingredient_ranges:
            st.session_state.ingredient_ranges[ingredient_2] = {
                "min": default_min_2,
                "max": default_max_2,
            }

        current_range_2 = st.session_state.ingredient_ranges[ingredient_2]

        min_col2, max_col2 = st.columns(2)
        with min_col2:
            min_val_2 = st.number_input(
                "Min",
                min_value=0.0,
                max_value=1000.0,
                value=current_range_2["min"],
                step=0.1,
                key="binary_min_2",
            )
        with max_col2:
            max_val_2 = st.number_input(
                "Max",
                min_value=0.1,
                max_value=1000.0,
                value=current_range_2["max"],
                step=0.1,
                key="binary_max_2",
            )

        if min_val_2 >= max_val_2:
            st.error(f"Min < Max required")
        else:
            st.session_state.ingredient_ranges[ingredient_2] = {
                "min": min_val_2,
                "max": max_val_2,
            }

    st.markdown("---")

    # ===== MAPPING METHOD =====
    method = st.selectbox(
        "Mapping Method:",
        options=["linear", "logarithmic", "exponential"],
        index=0,
        help="How 2D grid coordinates map to concentrations",
        key="binary_mapping_method",
    )
    st.session_state.selected_method = method

    st.markdown("---")

    # ===== QUESTIONNAIRE CONFIGURATION =====
    st.markdown("**Questionnaire**")

    # Get available questionnaires
    available_questionnaires = list_available_questionnaires()
    questionnaire_options = {q[0]: f"{q[1]} - {q[2]}" for q in available_questionnaires}

    # Initialize questionnaire type in session state
    if "selected_questionnaire_type" not in st.session_state:
        st.session_state.selected_questionnaire_type = get_default_questionnaire_type()

    # Questionnaire selector
    selected_questionnaire_type = st.selectbox(
        "Type:",
        options=list(questionnaire_options.keys()),
        format_func=lambda x: questionnaire_options[x],
        index=list(questionnaire_options.keys()).index(
            st.session_state.selected_questionnaire_type
        ),
        help="Select the type of questionnaire participants will complete",
        key="binary_questionnaire_selector",
    )

    # Update session state
    st.session_state.selected_questionnaire_type = selected_questionnaire_type

    # Show questionnaire preview
    questionnaire_config = get_questionnaire_config(selected_questionnaire_type)  # type: ignore
    if questionnaire_config:
        with st.expander("Preview Questionnaire Questions", expanded=False):
            st.markdown(f"**{questionnaire_config['name']}**")
            st.caption(questionnaire_config.get("description", ""))

            for i, question in enumerate(questionnaire_config.get("questions", []), 1):
                st.markdown(f"{i}. **{question['label']}**")
                st.caption(f"   Type: {question['type'].title()}")
                if question["type"] == "slider":
                    st.caption(f"   Range: {question['min']} - {question['max']}")
                    if "scale_labels" in question:
                        st.caption(
                            f"   Labels: {question['min']}=\"{question['scale_labels'].get(question['min'], '')}\" ... {question['max']}=\"{question['scale_labels'].get(question['max'], '')}\""
                        )
                elif question["type"] == "dropdown":
                    st.caption(f"   Options: {', '.join(question.get('options', []))}")

            # Show Bayesian optimization target
            if "bayesian_target" in questionnaire_config:
                st.markdown("---")
                st.markdown("**Bayesian Optimization Target:**")
                target = questionnaire_config["bayesian_target"]
                st.caption(f"Variable: {target['variable']}")
                st.caption(f"Goal: {target['description']}")

    st.markdown("---")

    # ===== BAYESIAN OPTIMIZATION CONFIGURATION =====
    with st.expander("Bayesian Optimization", expanded=False):
        _render_bo_config("binary_")

    st.markdown("---")

    # ===== START TRIAL BUTTON =====
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Show current participant
        participant_display = st.session_state.get("participant", "None selected")
        st.caption(f"**Participant:** {participant_display}")

        if st.button(
            "Start Trial",
            type="primary",
            width="stretch",
            key="binary_start_trial_button",
        ):
            # Validation
            if ingredient_1 == ingredient_2:
                st.error("Please select two different ingredients")
                st.stop()

            if min_val_1 >= max_val_1 or min_val_2 >= max_val_2:
                st.error("Please fix the concentration ranges (min must be < max)")
                st.stop()

            # Save full session configuration to database if not already saved
            if not st.session_state.get("session_config_saved", False):
                # Build ingredient list for database
                ingredients_for_db = [
                    {
                        "position": 0,
                        "name": ingredient_1,
                        "min": min_val_1,
                        "max": max_val_1,
                        "unit": "mM",
                    },
                    {
                        "position": 1,
                        "name": ingredient_2,
                        "min": min_val_2,
                        "max": max_val_2,
                        "unit": "mM",
                    },
                ]

                # Get BO config or use defaults
                bo_config = st.session_state.get("bo_config", get_default_bo_config())

                # Build full experiment config
                full_experiment_config = {
                    "num_ingredients": 2,
                    "interface_type": "2d_grid",
                    "moderator_name": st.session_state.get(
                        "moderator_name", "Moderator"
                    ),
                    "selected_ingredients": st.session_state.selected_ingredients,
                    "ingredient_ranges": st.session_state.ingredient_ranges,
                }

                # Create/update session in database
                # Convert questionnaire type name to integer ID
                questionnaire_name = st.session_state.get(
                    "selected_questionnaire_type", "hedonic_preference"
                )
                question_type_id = get_questionnaire_type_id(questionnaire_name)
                if question_type_id is None:
                    st.error(f"Invalid questionnaire type: {questionnaire_name}")
                    st.stop()

                success_db = update_session_with_config(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.get(
                        "participant", None
                    ),  # Use None if not set
                    num_ingredients=2,
                    interface_type="2d_grid",
                    method=method,
                    ingredients=ingredients_for_db,
                    question_type_id=question_type_id,
                    bo_config=bo_config,
                    experiment_config=full_experiment_config,
                )

                if success_db:
                    st.session_state.session_config_saved = True
                    st.success("Session configured and saved to database")
                else:
                    st.error("Failed to save session configuration. Please try again.")
                    st.stop()

            # Build ingredient configs with custom ranges
            ingredient_configs = []
            for ingredient_name in [ingredient_1, ingredient_2]:
                base_config = next(
                    (
                        ing
                        for ing in DEFAULT_INGREDIENT_CONFIG
                        if ing["name"] == ingredient_name
                    ),
                    None,
                )

                if not base_config:
                    st.error(
                        f"Ingredient '{ingredient_name}' not found in configuration"
                    )
                    st.stop()

                # Create a copy and apply custom ranges
                custom_config = base_config.copy()
                ranges = st.session_state.ingredient_ranges[ingredient_name]
                custom_config["min_concentration"] = ranges["min"]
                custom_config["max_concentration"] = ranges["max"]
                ingredient_configs.append(custom_config)

            # Start trial
            success = start_trial(
                "mod",
                st.session_state.participant,
                method,
                2,  # num_ingredients
                selected_ingredients=st.session_state.selected_ingredients,
                ingredient_configs=ingredient_configs,
            )

            if success:
                clear_canvas_state()
                st.toast(f"Trial started for {st.session_state.participant}")
                time.sleep(1)
                st.rerun()


def single_bo():
    """Single ingredient BO visualization with 1D Gaussian Process plots."""
    from bayesian_optimizer import train_bo_model_for_participant
    from questionnaire_config import get_questionnaire_config
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np

    # Get session and configuration
    session = get_session(st.session_state.session_id)
    if not session or "experiment_config" not in session:
        st.error("Could not load session configuration")
        return

    experiment_config = session["experiment_config"]
    ingredients = experiment_config.get("ingredients", [])

    if not ingredients or len(ingredients) != 1:
        st.error("Expected exactly 1 ingredient for single_bo visualization")
        return

    ingredient = ingredients[0]
    ingredient_name = ingredient["name"]
    min_concentration = ingredient["min_concentration"]
    max_concentration = ingredient["max_concentration"]

    # Get BO configuration
    bo_config = experiment_config.get("bayesian_optimization", {})
    min_samples_for_bo = bo_config.get("min_samples_for_bo", 3)

    # Get questionnaire config for target variable
    questionnaire_name = session.get("questionnaire_name", "hedonic_preference")
    questionnaire_config = get_questionnaire_config(questionnaire_name)
    target_variable = "overall_liking"  # Default
    if questionnaire_config and "bayesian_target" in questionnaire_config:
        target_variable = questionnaire_config["bayesian_target"]["variable"]

    # Get training data
    try:
        df = get_training_data(
            st.session_state.session_id,
            only_final=False,
        )
    except Exception as e:
        st.warning(f"Could not load training data: {e}")
        df = None

    # Check if enough data for BO
    if df is None or len(df) < min_samples_for_bo:
        current_samples = len(df) if df is not None else 0
        st.info(
            f"Bayesian Optimization not yet active. Need {min_samples_for_bo} samples, have {current_samples}."
        )
        st.write("Waiting for more participant responses...")
        return

    # Check if target variable exists in data
    if target_variable not in df.columns:
        st.error(
            f"Target variable '{target_variable}' not found in questionnaire responses"
        )
        st.write(f"Available columns: {list(df.columns)}")
        return

    # Train BO model
    try:
        st.markdown(f"#### {ingredient_name} Preference Landscape")
        st.caption(
            f"Based on {len(df)} observations | Target: {target_variable.replace('_', ' ').title()}"
        )

        bo_model = train_bo_model_for_participant(
            participant_id=st.session_state.participant,
            session_id=st.session_state.session_id,
            bo_config=bo_config,
        )

        # Safely handle cases where training failed or returned None
        if bo_model is None or not getattr(bo_model, "is_fitted", False):
            st.error("BO model training failed or returned no model")
            return

        # Get observed data
        X_observed = df[ingredient_name].values
        y_observed = df[target_variable].values

        # Generate candidates for prediction
        X_candidates = np.linspace(min_concentration, max_concentration, 1000).reshape(
            -1, 1
        )

        # GP predictions
        pred_mean, pred_sigma = bo_model.predict(X_candidates, return_std=True)

        # Acquisition function
        acq_func = bo_config.get("acquisition_function", "ei")
        if acq_func == "ei":
            ei_xi = bo_config.get("ei_xi", 0.01)
            acq_values = bo_model.expected_improvement(X_candidates, xi=ei_xi)
            acq_label = f"Expected Improvement (ξ={ei_xi})"
        else:  # ucb
            ucb_kappa = bo_config.get("ucb_kappa", 2.0)
            acq_values = bo_model.upper_confidence_bound(X_candidates, kappa=ucb_kappa)
            acq_label = f"Upper Confidence Bound (κ={ucb_kappa})"

        # Get next suggestion
        suggestion = bo_model.suggest_next_sample(X_candidates)
        next_x = suggestion["best_candidate"][0]
        next_pred = suggestion["predicted_value"]

        # Create subplot with dual y-axes
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Add GP mean prediction (red line)
        fig.add_trace(
            go.Scatter(
                x=X_candidates.ravel(),
                y=pred_mean,
                mode="lines",
                name="GP Mean",
                line=dict(color="red", width=2),
                showlegend=True,
            ),
            secondary_y=False,
        )

        # Add uncertainty band (±2σ shaded region)
        fig.add_trace(
            go.Scatter(
                x=X_candidates.ravel(),
                y=pred_mean + 2 * pred_sigma,
                mode="lines",
                line=dict(width=0),
                showlegend=False,
                hoverinfo="skip",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=X_candidates.ravel(),
                y=pred_mean - 2 * pred_sigma,
                mode="lines",
                fill="tonexty",
                fillcolor="rgba(255, 0, 0, 0.2)",
                line=dict(width=0),
                name="±2σ Uncertainty",
                showlegend=True,
            ),
            secondary_y=False,
        )

        # Add observed training data (red scatter)
        fig.add_trace(
            go.Scatter(
                x=X_observed,
                y=y_observed,
                mode="markers",
                name="Observed Data",
                marker=dict(
                    color="red",
                    size=10,
                    symbol="circle",
                    line=dict(width=2, color="darkred"),
                ),
                showlegend=True,
            ),
            secondary_y=False,
        )

        # Add next observation point (red triangle)
        fig.add_trace(
            go.Scatter(
                x=[next_x],
                y=[next_pred],
                mode="markers",
                name="Next Observation",
                marker=dict(
                    color="red",
                    size=15,
                    symbol="triangle-down",
                    line=dict(width=2, color="darkred"),
                ),
                showlegend=True,
                text=[f"Next: {next_x:.2f} mM<br>Predicted: {next_pred:.2f}"],
                hoverinfo="text",
            ),
            secondary_y=False,
        )

        # Add acquisition function (green dashed line, secondary y-axis)
        fig.add_trace(
            go.Scatter(
                x=X_candidates.ravel(),
                y=acq_values,
                mode="lines",
                name=acq_label,
                line=dict(color="green", width=2, dash="dash"),
                showlegend=True,
            ),
            secondary_y=True,
        )

        # Update layout
        fig.update_xaxes(
            title_text=f"{ingredient_name} Concentration (mM)",
            showgrid=True,
            gridcolor="lightgray",
        )
        fig.update_yaxes(
            title_text=target_variable.replace("_", " ").title(),
            secondary_y=False,
            showgrid=True,
            gridcolor="lightgray",
        )
        fig.update_yaxes(
            title_text=acq_label,
            secondary_y=True,
            showgrid=False,
        )

        fig.update_layout(
            height=500,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="center",
                x=0.5,
            ),
            margin=dict(l=60, r=60, t=40, b=100),
        )

        # Display plot
        st.plotly_chart(fig, width="stretch")

        # Show metrics below plot
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Observations", len(df))
        with col2:
            st.metric("Best Observed", f"{bo_model.best_observed_value:.2f}")
        with col3:
            st.metric("Next Suggestion", f"{next_x:.2f} mM")
        with col4:
            st.metric("Predicted Value", f"{next_pred:.2f}")

    except Exception as e:
        st.error(f"Error creating BO visualization: {e}")
        import traceback

        st.code(traceback.format_exc())


def binary_bo():
    """Binary mixture BO visualization with 2D Gaussian Process heatmaps."""
    from bayesian_optimizer import (
        train_bo_model_for_participant,
        generate_candidate_grid_2d,
    )
    from questionnaire_config import get_questionnaire_config
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import numpy as np

    # Get session and configuration
    session = get_session(st.session_state.session_id)
    if not session or "experiment_config" not in session:
        st.error("Could not load session configuration")
        return

    experiment_config = session["experiment_config"]
    ingredients = experiment_config.get("ingredients", [])

    if not ingredients or len(ingredients) != 2:
        st.error("Expected exactly 2 ingredients for binary_bo visualization")
        return

    ingredient_1 = ingredients[0]
    ingredient_2 = ingredients[1]
    ing1_name = ingredient_1["name"]
    ing2_name = ingredient_2["name"]
    ing1_range = (ingredient_1["min_concentration"], ingredient_1["max_concentration"])
    ing2_range = (ingredient_2["min_concentration"], ingredient_2["max_concentration"])

    # Get BO configuration
    bo_config = experiment_config.get("bayesian_optimization", {})
    min_samples_for_bo = bo_config.get("min_samples_for_bo", 3)

    # Get questionnaire config for target variable
    questionnaire_name = session.get("questionnaire_name", "hedonic_preference")
    questionnaire_config = get_questionnaire_config(questionnaire_name)
    target_variable = "overall_liking"  # Default
    if questionnaire_config and "bayesian_target" in questionnaire_config:
        target_variable = questionnaire_config["bayesian_target"]["variable"]

    # Get training data
    try:
        df = get_training_data(
            st.session_state.session_id,
            only_final=False,
        )
    except Exception as e:
        st.warning(f"Could not load training data: {e}")
        df = None

    # Check if enough data for BO
    if df is None or len(df) < min_samples_for_bo:
        current_samples = len(df) if df is not None else 0
        st.info(
            f"Bayesian Optimization not yet active. Need {min_samples_for_bo} samples, have {current_samples}."
        )
        st.write("Waiting for more participant responses...")
        return

    # Check if target variable exists in data
    if target_variable not in df.columns:
        st.error(
            f"Target variable '{target_variable}' not found in questionnaire responses"
        )
        st.write(f"Available columns: {list(df.columns)}")
        return

    # Train BO model
    try:
        st.markdown(f"#### {ing1_name} × {ing2_name} Preference Landscape")
        st.caption(
            f"Based on {len(df)} observations | Target: {target_variable.replace('_', ' ').title()}"
        )

        bo_model = train_bo_model_for_participant(
            participant_id=st.session_state.participant,
            session_id=st.session_state.session_id,
            bo_config=bo_config,
        )
        # Safely handle cases where training failed or returned None
        if bo_model is None or not getattr(bo_model, "is_fitted", False):
            st.error("BO model training failed or returned no model")
            return

        if not bo_model.is_fitted:
            st.error("BO model training failed")
            return

        # Get observed data
        X_observed = df[[ing1_name, ing2_name]].values
        y_observed = df[target_variable].values

        # Generate 2D grid candidates
        candidates = generate_candidate_grid_2d(ing1_range, ing2_range, n_points=50)
        X_grid_ing1 = candidates[:, 0].reshape(50, 50)
        X_grid_ing2 = candidates[:, 1].reshape(50, 50)

        # GP predictions
        pred_mean, pred_sigma = bo_model.predict(candidates, return_std=True)
        Z_mean = pred_mean.reshape(50, 50)
        Z_sigma = pred_sigma.reshape(50, 50)

        # Acquisition function
        acq_func = bo_config.get("acquisition_function", "ei")
        if acq_func == "ei":
            ei_xi = bo_config.get("ei_xi", 0.01)
            acq_values = bo_model.expected_improvement(candidates, xi=ei_xi)
            acq_label = f"Expected Improvement (ξ={ei_xi})"
        else:  # ucb
            ucb_kappa = bo_config.get("ucb_kappa", 2.0)
            acq_values = bo_model.upper_confidence_bound(candidates, kappa=ucb_kappa)
            acq_label = f"Upper Confidence Bound (κ={ucb_kappa})"

        Z_acq = acq_values.reshape(50, 50)

        # Get next suggestion
        suggestion = bo_model.suggest_next_sample(candidates)
        next_x = suggestion["best_candidate"]
        next_pred = suggestion["predicted_value"]

        # Create 3 subplots: GP Mean, Uncertainty, Acquisition
        fig = make_subplots(
            rows=1,
            cols=3,
            subplot_titles=("GP Mean Prediction", "Uncertainty (σ)", acq_label),
            specs=[[{"type": "contour"}, {"type": "contour"}, {"type": "contour"}]],
            horizontal_spacing=0.12,
        )

        # Plot 1: GP Mean with observations and next point
        fig.add_trace(
            go.Contour(
                x=X_grid_ing1[0, :],
                y=X_grid_ing2[:, 0],
                z=Z_mean,
                colorscale="RdYlGn",
                showscale=True,
                colorbar=dict(x=0.28, len=0.8),
                contours=dict(showlabels=True, labelfont=dict(size=8)),
                hovertemplate=f"{ing1_name}: %{{x:.2f}} mM<br>{ing2_name}: %{{y:.2f}} mM<br>Predicted: %{{z:.2f}}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        # Add observed points to GP Mean plot
        fig.add_trace(
            go.Scatter(
                x=X_observed[:, 0],
                y=X_observed[:, 1],
                mode="markers",
                name="Observed",
                marker=dict(
                    color="red",
                    size=8,
                    symbol="circle",
                    line=dict(width=1, color="darkred"),
                ),
                showlegend=True,
                hovertemplate=f"{ing1_name}: %{{x:.2f}} mM<br>{ing2_name}: %{{y:.2f}} mM<extra>Observed</extra>",
            ),
            row=1,
            col=1,
        )

        # Add next observation point to GP Mean plot
        fig.add_trace(
            go.Scatter(
                x=[next_x[0]],
                y=[next_x[1]],
                mode="markers",
                name="Next",
                marker=dict(
                    color="blue",
                    size=15,
                    symbol="star",
                    line=dict(width=2, color="darkblue"),
                ),
                showlegend=True,
                hovertemplate=f"{ing1_name}: %{{x:.2f}} mM<br>{ing2_name}: %{{y:.2f}} mM<br>Predicted: {next_pred:.2f}<extra>Next Suggestion</extra>",
            ),
            row=1,
            col=1,
        )

        # Plot 2: Uncertainty
        fig.add_trace(
            go.Contour(
                x=X_grid_ing1[0, :],
                y=X_grid_ing2[:, 0],
                z=Z_sigma,
                colorscale="Reds",
                showscale=True,
                colorbar=dict(x=0.63, len=0.8),
                contours=dict(showlabels=True, labelfont=dict(size=8)),
                hovertemplate=f"{ing1_name}: %{{x:.2f}} mM<br>{ing2_name}: %{{y:.2f}} mM<br>Uncertainty: %{{z:.2f}}<extra></extra>",
            ),
            row=1,
            col=2,
        )

        # Plot 3: Acquisition Function
        fig.add_trace(
            go.Contour(
                x=X_grid_ing1[0, :],
                y=X_grid_ing2[:, 0],
                z=Z_acq,
                colorscale="Greens",
                showscale=True,
                colorbar=dict(x=0.98, len=0.8),
                contours=dict(showlabels=True, labelfont=dict(size=8)),
                hovertemplate=f"{ing1_name}: %{{x:.2f}} mM<br>{ing2_name}: %{{y:.2f}} mM<br>{acq_label}: %{{z:.3f}}<extra></extra>",
            ),
            row=1,
            col=3,
        )

        # Add next point to acquisition plot
        fig.add_trace(
            go.Scatter(
                x=[next_x[0]],
                y=[next_x[1]],
                mode="markers",
                marker=dict(
                    color="blue",
                    size=15,
                    symbol="star",
                    line=dict(width=2, color="darkblue"),
                ),
                showlegend=False,
                hovertemplate=f"Max Acquisition<extra></extra>",
            ),
            row=1,
            col=3,
        )

        # Update axes
        for col in [1, 2, 3]:
            fig.update_xaxes(title_text=f"{ing1_name} (mM)", row=1, col=col)
            fig.update_yaxes(title_text=f"{ing2_name} (mM)", row=1, col=col)

        # Update layout
        fig.update_layout(
            height=450,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=0.98,
                xanchor="left",
                x=0.01,
            ),
            margin=dict(l=50, r=50, t=60, b=50),
        )

        # Display plot
        st.plotly_chart(fig, width="stretch")

        # Show metrics below plot
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Observations", len(df))
        with col2:
            st.metric("Best Observed", f"{bo_model.best_observed_value:.2f}")
        with col3:
            st.metric("Next Suggestion", f"({next_x[0]:.2f}, {next_x[1]:.2f}) mM")
        with col4:
            st.metric("Predicted Value", f"{next_pred:.2f}")

    except Exception as e:
        st.error(f"Error creating BO visualization: {e}")
        import traceback

        st.code(traceback.format_exc())


def show_moderator_monitoring():
    """Monitor active trial with tabbed interface."""
    tab_overview, tab_responses, tab_bo, tab_export = st.tabs(
        ["Overview", "Responses", "Bayesian Optimization", "Export Data"]
    )

    # ========== TAB 1: OVERVIEW ==========
    with tab_overview:
        st.markdown("### Session Overview")

        # Get session info
        session_info = get_session_info(st.session_state.session_id)
        if not session_info:
            st.error("Could not load session information")
            return

        # Session Info Card
        st.markdown("#### Session Information")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Session Code", st.session_state.get("session_code", "N/A"))
        with col2:
            st.metric("Participant", st.session_state.get("participant", "N/A"))
        with col3:
            created_at = session_info.get("created_at", "")
            created_date = created_at[:10] if created_at else "N/A"
            st.metric("Created", created_date)
        with col4:
            current_phase = session_info.get("current_phase", "unknown")
            st.metric("Phase", current_phase.replace("_", " ").title())

        st.markdown("---")

        # Progress Metrics
        st.markdown("#### Progress Metrics")
        try:
            stats = get_session_stats(st.session_state.session_id)
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Cycles", stats.get("total_cycles", 0))
            with col2:
                st.metric("Final Samples", stats.get("final_samples", 0))
            with col3:
                st.metric("Status", stats.get("state", "unknown").title())
        except Exception as e:
            st.warning(f"Could not load session stats: {e}")

        st.markdown("---")

        # Current Selection Display
        st.markdown("#### Current Selection")
        concentrations = get_latest_sample_concentrations(st.session_state.session_id)

        if not concentrations:
            st.info("No samples recorded yet. Waiting for participant to start...")
        else:
            # Get ingredient configs from session
            session = get_session(st.session_state.session_id)
            if session and "experiment_config" in session:
                experiment_config = session["experiment_config"]
                selected_ingredients = experiment_config.get("selected_ingredients", [])
                ingredient_ranges = experiment_config.get("ingredient_ranges", {})

                # Display each ingredient with progress bar
                for ingredient_name in selected_ingredients:
                    if ingredient_name in concentrations:
                        concentration_mM = concentrations[ingredient_name]

                        # Get min/max from ingredient_ranges
                        if ingredient_name in ingredient_ranges:
                            min_mM = ingredient_ranges[ingredient_name].get("min", 0)
                            max_mM = ingredient_ranges[ingredient_name].get("max", 100)
                        else:
                            min_mM, max_mM = 0, 100

                        # Calculate percentage
                        percentage = (
                            (concentration_mM - min_mM) / (max_mM - min_mM)
                        ) * 100
                        percentage = max(0, min(100, percentage))

                        # Display
                        st.markdown(f"**{ingredient_name}**")
                        st.progress(percentage / 100.0)

                        col_conc, col_pct = st.columns(2)
                        with col_conc:
                            st.caption(f"{concentration_mM:.3f} mM")
                        with col_pct:
                            st.caption(f"{percentage:.1f}% of scale")

                        st.markdown("")  # Spacing

    # ========== TAB 2: RESPONSES ==========
    with tab_responses:
        st.markdown("### Participant Responses")

        # Filter controls
        col1, col2 = st.columns([1, 3])
        with col1:
            show_only_final = st.checkbox(
                "Show Final Only", value=False, key="responses_filter"
            )
        with col2:
            if st.button("Refresh Data", key="responses_refresh"):
                st.rerun()

        st.markdown("---")

        # Get samples
        try:
            samples = get_session_samples(
                st.session_state.session_id, only_final=show_only_final
            )

            if not samples:
                st.info(
                    "No responses recorded yet"
                    + (" (with final=True)" if show_only_final else "")
                )
            else:
                # Build DataFrame
                rows = []
                for sample in samples:
                    row = {
                        "Cycle": sample.get("cycle_number", "?"),
                        "Timestamp": (
                            sample.get("created_at", "")[:19]
                            if sample.get("created_at")
                            else ""
                        ),
                        "Is Final": "✓" if sample.get("is_final") else "",
                    }

                    # Add ingredient concentrations
                    ingredient_conc = sample.get("ingredient_concentration", {})
                    for ing_name, conc in ingredient_conc.items():
                        row[f"{ing_name} (mM)"] = f"{conc:.2f}"

                    # Add questionnaire responses
                    questionnaire = sample.get("questionnaire_answer", {})
                    for q_key, q_val in questionnaire.items():
                        row[q_key.replace("_", " ").title()] = q_val

                    rows.append(row)

                df = pd.DataFrame(rows)

                # Display table
                st.dataframe(
                    df,
                    width="stretch",
                    hide_index=True,
                )

                st.caption(f"Showing {len(df)} response(s)")

                # Detailed view expander
                with st.expander("View Detailed Response Data", expanded=False):
                    for i, sample in enumerate(samples, 1):
                        st.markdown(
                            f"**Response {i} - Cycle {sample.get('cycle_number', '?')}**"
                        )
                        st.json(sample)
                        st.markdown("---")

        except Exception as e:
            st.error(f"Error loading responses: {e}")
            import traceback

            st.code(traceback.format_exc())

    # ========== TAB 3: BO VISUALIZATION ==========
    with tab_bo:
        st.markdown("### Bayesian Optimization Analysis")
        # Get session config to determine ingredient count
        session = get_session(st.session_state.session_id)
        if session and "experiment_config" in session:
            num_ingredients = session["experiment_config"].get("num_ingredients", 2)

            # Display BO config summary
            with st.expander("BO Configuration", expanded=False):
                try:
                    bo_config_db = get_bo_config(st.session_state.session_id)
                    if bo_config_db:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(
                                "Enabled",
                                "Yes" if bo_config_db.get("enabled") else "No",
                            )
                            st.metric(
                                "Min Samples", bo_config_db.get("min_samples_for_bo", 3)
                            )
                        with col2:
                            st.metric(
                                "Acquisition",
                                bo_config_db.get("acquisition_function", "ei").upper(),
                            )
                            st.metric("Kernel ν", bo_config_db.get("kernel_nu", 2.5))
                        with col3:
                            st.metric(
                                "Alpha", f"{bo_config_db.get('alpha', 0.001):.6f}"
                            )
                            st.metric(
                                "Random Seed", bo_config_db.get("random_state", 42)
                            )
                    else:
                        st.info("No BO configuration found")
                except Exception as e:
                    st.warning(f"Could not load BO config: {e}")

            st.markdown("---")

            # ========== CONVERGENCE STATUS PANEL ==========
            st.markdown("### Convergence Status")

            try:
                from bayesian_optimizer import (
                    check_convergence,
                    get_convergence_metrics,
                )

                # Get stopping criteria from session config
                experiment_config = session.get("experiment_config", {})
                bo_config_full = experiment_config.get("bayesian_optimization", {})
                stopping_criteria = bo_config_full.get("stopping_criteria")

                # Check convergence
                convergence = check_convergence(
                    st.session_state.session_id, stopping_criteria
                )
                metrics = convergence["metrics"]

                # Status header with emoji
                status_emoji = convergence["status_emoji"]
                recommendation = convergence["recommendation"]

                # Color coding
                if recommendation == "stop_recommended":
                    status_color = "🟢"
                    alert_type = "success"
                elif recommendation == "consider_stopping":
                    status_color = "🟡"
                    alert_type = "warning"
                else:
                    status_color = "🔴"
                    alert_type = "info"

                # Display status
                st.markdown(f"## {status_emoji} Status: {convergence['reason']}")

                # Metrics display
                metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

                with metric_col1:
                    st.metric("Current Cycle", metrics.get("current_cycle", 0))

                with metric_col2:
                    st.metric(
                        "Cycle Range",
                        f"{convergence['thresholds']['min_cycles']}-{convergence['thresholds']['max_cycles']}",
                    )

                with metric_col3:
                    acq_val = metrics.get("max_acquisition")
                    acq_thresh = convergence["thresholds"]["acquisition_threshold"]
                    if acq_val is not None:
                        st.metric(
                            "Acquisition (EI/UCB)",
                            f"{acq_val:.4f}",
                            delta=f"Threshold: {acq_thresh:.4f}",
                            delta_color="inverse",
                        )
                    else:
                        st.metric("Acquisition", "N/A")

                with metric_col4:
                    stability = metrics.get("recent_stability")
                    stab_thresh = convergence["thresholds"]["stability_threshold"]
                    if stability is not None:
                        st.metric(
                            "Stability (σ)",
                            f"{stability:.3f}",
                            delta=f"Threshold: {stab_thresh:.2f}",
                            delta_color="inverse",
                        )
                    else:
                        st.metric("Stability", "N/A (< 5 samples)")

                # Progress bar
                current = metrics.get("current_cycle", 0)
                max_cycles = convergence["thresholds"]["max_cycles"]
                progress = min(1.0, current / max_cycles) if max_cycles > 0 else 0
                st.progress(progress)
                st.caption(
                    f"Progress: {current}/{max_cycles} cycles ({progress*100:.1f}%)"
                )

                # Criteria checklist
                with st.expander("Convergence Criteria Details", expanded=False):
                    st.markdown("**Criteria Met:**")
                    for criterion in convergence.get("criteria_met", []):
                        st.markdown(f"- ✅ {criterion}")

                    if convergence.get("criteria_failed"):
                        st.markdown("**Criteria Not Met:**")
                        for criterion in convergence.get("criteria_failed", []):
                            st.markdown(f"- ❌ {criterion}")

                    st.markdown(
                        f"**Confidence:** {convergence.get('confidence', 0)*100:.1f}%"
                    )

                # Status message based on recommendation
                if recommendation == "stop_recommended":
                    st.success(
                        "✅ Session has converged! Consider ending the session to avoid participant fatigue."
                    )
                elif recommendation == "consider_stopping":
                    st.warning("⚠️ Session is nearing convergence. Monitor closely.")
                else:
                    st.info(
                        "📊 Session is still optimizing. Continue collecting samples."
                    )

                # End Session button - Always available to moderator
                st.markdown("---")
                if st.button(
                    "🛑 End Session Now", type="primary", key="end_session_manual"
                ):
                    # Transition to COMPLETE phase using proper state machine method
                    try:
                        # Use transition() which handles validation, DB updates, and session state
                        success = ExperimentStateMachine.transition(
                            ExperimentPhase.COMPLETE, st.session_state.session_id
                        )

                        if success:
                            st.success("Session ended successfully!")
                            st.rerun()
                        else:
                            logger.error(
                                f"Failed to end session {st.session_state.session_id}: transition returned False"
                            )
                            st.error("Failed to end session: Invalid state transition")

                    except InvalidTransitionError as e:
                        # Log the specific transition error
                        logger.error(
                            f"Invalid transition when ending session {st.session_state.session_id}: {e}"
                        )
                        st.error(f"Cannot end session from current phase. Details: {e}")

                    except Exception as e:
                        # Log unexpected errors with full traceback
                        logger.error(
                            f"Unexpected error ending session {st.session_state.session_id}: {e}",
                            exc_info=True,
                        )
                        st.error(f"Failed to end session: {e}")

                # Real-time metrics chart (if sufficient data)
                if metrics.get("has_sufficient_data"):
                    with st.expander("Convergence Metrics Over Time", expanded=False):
                        import plotly.graph_objects as go

                        # Acquisition values over time
                        acq_values = metrics.get("acquisition_values", [])
                        if acq_values:
                            fig_acq = go.Figure()
                            fig_acq.add_trace(
                                go.Scatter(
                                    y=acq_values,
                                    mode="lines+markers",
                                    name="Acquisition Value",
                                    line=dict(color="blue", width=2),
                                )
                            )
                            fig_acq.add_hline(
                                y=acq_thresh,
                                line_dash="dash",
                                line_color="red",
                                annotation_text="Convergence Threshold",
                            )
                            fig_acq.update_layout(
                                title="Acquisition Function Over Cycles",
                                xaxis_title="BO Suggestion Number",
                                yaxis_title="Acquisition Value",
                                height=300,
                            )
                            st.plotly_chart(fig_acq, use_container_width=True)

                        # Best values over time
                        best_values = metrics.get("best_values", [])
                        if best_values:
                            fig_best = go.Figure()
                            fig_best.add_trace(
                                go.Scatter(
                                    y=best_values,
                                    mode="lines+markers",
                                    name="Best Observed Value",
                                    line=dict(color="green", width=2),
                                )
                            )
                            fig_best.update_layout(
                                title="Best Observed Rating Over Time",
                                xaxis_title="Cycle",
                                yaxis_title="Rating",
                                height=300,
                            )
                            st.plotly_chart(fig_best, use_container_width=True)

            except Exception as e:
                st.error(f"Error loading convergence status: {e}")
                import traceback

                with st.expander("Error Details"):
                    st.code(traceback.format_exc())

            st.markdown("---")

            # Route to appropriate visualization
            if num_ingredients == 1:
                single_bo()
            elif num_ingredients == 2:
                binary_bo()
            else:
                st.warning(
                    f"BO visualization not yet implemented for {num_ingredients} ingredients"
                )
                st.info("Supported: 1 (single ingredient) or 2 (binary mixture)")
        else:
            st.error("Could not load session configuration")

    # ========== TAB 4: EXPORT ==========
    with tab_export:
        st.markdown("### Data Export")

        # Export options
        st.markdown("#### Export Formats")

        export_col1, export_col2 = st.columns(2)

        with export_col1:
            st.markdown("**CSV Export**")
            st.caption("Complete dataset with all responses and concentrations")

            if st.button(
                "Generate CSV Export", key="export_csv_button", width="stretch"
            ):
                try:
                    session_code = st.session_state.get(
                        "session_code", "default_session"
                    )
                    csv_data = export_session_csv(session_code)

                    if csv_data:
                        st.download_button(
                            label="Download CSV File",
                            data=csv_data,
                            file_name=f"robotaste_session_{session_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_csv_button",
                            width="stretch",
                        )
                        st.success("CSV export ready!")
                    else:
                        st.warning("No data found to export for this session.")
                except Exception as e:
                    st.error(f"Error exporting CSV: {e}")

        with export_col2:
            st.markdown("**JSON Export**")
            st.caption("Raw database dump in JSON format")

            if st.button(
                "Generate JSON Export",
                key="export_json_button",
                width="stretch",
            ):
                try:
                    import json

                    # Get all session data
                    session = get_session(st.session_state.session_id)
                    samples = get_session_samples(
                        st.session_state.session_id, only_final=False
                    )
                    bo_config_db = get_bo_config(st.session_state.session_id)

                    export_data = {
                        "session": session,
                        "samples": samples,
                        "bo_config": bo_config_db,
                        "exported_at": datetime.now().isoformat(),
                    }

                    json_data = json.dumps(export_data, indent=2, default=str)

                    st.download_button(
                        label="Download JSON File",
                        data=json_data,
                        file_name=f"robotaste_session_{st.session_state.get('session_code', 'default')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        key="download_json_button",
                        width="stretch",
                    )
                    st.success("JSON export ready!")
                except Exception as e:
                    st.error(f"Error exporting JSON: {e}")

        st.markdown("---")

        # Preview section
        st.markdown("#### Export Preview")

        try:
            samples = get_session_samples(st.session_state.session_id, only_final=False)

            if samples:
                preview_count = min(10, len(samples))
                st.caption(f"Showing first {preview_count} of {len(samples)} responses")

                # Build preview DataFrame
                preview_rows = []
                for sample in samples[:preview_count]:
                    row = {
                        "Cycle": sample.get("cycle_number", "?"),
                        "Timestamp": (
                            sample.get("created_at", "")[:19]
                            if sample.get("created_at")
                            else ""
                        ),
                    }

                    # Add concentrations
                    for ing_name, conc in sample.get(
                        "ingredient_concentration", {}
                    ).items():
                        row[f"{ing_name}"] = f"{conc:.2f}"

                    # Add questionnaire
                    for q_key, q_val in sample.get("questionnaire_answer", {}).items():
                        row[q_key] = q_val

                    row["Final"] = "Yes" if sample.get("is_final") else "No"

                    preview_rows.append(row)

                preview_df = pd.DataFrame(preview_rows)
                st.dataframe(preview_df, width="stretch", hide_index=True)
            else:
                st.info("No data available for preview")
        except Exception as e:
            st.warning(f"Could not generate preview: {e}")

        # Export information
        with st.expander("What data gets exported?", expanded=False):
            st.markdown(
                """
            **CSV Export includes:**
            - Session ID and session code
            - Participant information
            - Cycle numbers and timestamps
            - Ingredient concentrations (mM values)
            - Questionnaire responses
            - Final response indicators
            - Interface type and mapping method

            **JSON Export includes:**
            - Complete session configuration
            - All sample data with metadata
            - Bayesian optimization configuration
            - Raw database records

            **Data is organized chronologically** for easy analysis in research tools like R, Python, or Excel.
            """
            )


def moderator_interface():
    if "phase" not in st.session_state:
        from state_machine import recover_phase_from_database

        recovered_phase = recover_phase_from_database(st.session_state.session_id)

        # Moderator UI has only two states:
        # 1. "waiting" = setup mode (configure trial)
        # 2. "trial_started" = monitoring mode (watch subject, regardless of exact subject phase)

        if recovered_phase == "waiting" or recovered_phase is None:
            # Fresh session or explicitly waiting - show setup
            st.session_state.phase = "waiting"
        else:
            # Any other phase (welcome, pre_questionnaire, respond, etc.) means trial is active
            # Normalize to "trial_started" for moderator UI to show monitoring
            st.session_state.phase = "trial_started"
    if ExperimentStateMachine.should_show_setup():
        # Initialize setup type in session state
        if "setup_type" not in st.session_state:
            st.session_state.setup_type = None

        # Buttons to select setup type
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Single Ingredient", width="stretch"):
                st.session_state.setup_type = "single"
        with col2:
            if st.button("Binary Mixture", width="stretch"):
                st.session_state.setup_type = "binary"

        # Render setup UI based on selection (unconditionally)
        if st.session_state.setup_type == "single":
            show_single_ingredient_setup()
        elif st.session_state.setup_type == "binary":
            show_binary_mixture_setup()
    elif ExperimentStateMachine.should_show_monitoring():
        show_moderator_monitoring()
    else:
        # If not setup and not monitoring, must be COMPLETE phase
        from completion_screens import show_moderator_completion_summary
        show_moderator_completion_summary()
