from callback import (
    INTERFACE_2D_GRID,
    INTERFACE_SLIDERS,
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
)
from state_machine import (
    ExperimentPhase,
    ExperimentStateMachine,
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
            use_container_width=True,
            key="single_start_trial_button",
        ):
            # Validation
            if min_val >= max_val:
                st.error("Please fix the concentration range (min must be < max)")
                st.stop()

            # Create session in database if not already created
            if not st.session_state.get("session_created_in_db", False):
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
                success_db = update_session_with_config(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.participant,
                    num_ingredients=1,
                    interface_type="sliders",
                    method="linear",  # Sliders always use linear mapping
                    ingredients=ingredients_for_db,
                    question_type_id=st.session_state.get(
                        "selected_questionnaire_type", 1
                    ),
                    bo_config=bo_config,
                    experiment_config=full_experiment_config,
                )

                if success_db:
                    st.session_state.session_created_in_db = True
                    st.success("Session created in database")
                else:
                    st.error("Failed to create session in database. Please try again.")
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
            use_container_width=True,
            key="binary_start_trial_button",
        ):
            # Validation
            if ingredient_1 == ingredient_2:
                st.error("Please select two different ingredients")
                st.stop()

            if min_val_1 >= max_val_1 or min_val_2 >= max_val_2:
                st.error("Please fix the concentration ranges (min must be < max)")
                st.stop()

            # Create session in database if not already created
            if not st.session_state.get("session_created_in_db", False):
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
                success_db = update_session_with_config(
                    session_id=st.session_state.session_id,
                    user_id=st.session_state.participant,
                    num_ingredients=2,
                    interface_type="2d_grid",
                    method=method,
                    ingredients=ingredients_for_db,
                    question_type_id=st.session_state.get(
                        "selected_questionnaire_type", 1
                    ),
                    bo_config=bo_config,
                    experiment_config=full_experiment_config,
                )

                if success_db:
                    st.session_state.session_created_in_db = True
                    st.success("Session created in database")
                else:
                    st.error("Failed to create session in database. Please try again.")
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
    """Placeholder for single ingredient BO visualization."""
    st.info("🚧 Single ingredient BO visualization - To be implemented")
    st.write("**This will show:**")
    st.write("- 1D line plot of GP predictions")
    st.write("- Uncertainty bands (±2σ)")
    st.write("- Observed samples marked on plot")
    st.write("- Next recommended sample")
    st.write("- Acquisition function overlay")


def binary_bo():
    """Placeholder for binary mixture BO visualization."""
    st.info("🚧 Binary mixture BO visualization - To be implemented")
    st.write("**This will show:**")
    st.write("- 2D heatmap of GP predictions")
    st.write("- Uncertainty contours")
    st.write("- Acquisition function contours")
    st.write("- Observed samples as scatter points")
    st.write("- Next recommended sample as star")


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
                    use_container_width=True,
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
                "Generate CSV Export", key="export_csv_button", use_container_width=True
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
                            use_container_width=True,
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
                use_container_width=True,
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
                        use_container_width=True,
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
                st.dataframe(preview_df, use_container_width=True, hide_index=True)
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
            if st.button("Single Ingredient", use_container_width=True):
                st.session_state.setup_type = "single"
        with col2:
            if st.button("Binary Mixture", use_container_width=True):
                st.session_state.setup_type = "binary"

        # Render setup UI based on selection (unconditionally)
        if st.session_state.setup_type == "single":
            show_single_ingredient_setup()
        elif st.session_state.setup_type == "binary":
            show_binary_mixture_setup()
    elif ExperimentStateMachine.should_show_monitoring():
        show_moderator_monitoring()
