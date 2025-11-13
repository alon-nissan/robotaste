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


import streamlit as st
import pandas as pd
import time
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_current_phase_safe() -> str:
    """
    Get current phase safely from session_state or database.
    Falls back to session_state when session not yet in DB.

    Returns:
        str: Current phase string (e.g., "waiting", "selection", etc.)
    """
    session_created_in_db = st.session_state.get("session_created_in_db", True)

    if session_created_in_db:
        session_info = get_session_info(st.session_state.session_id)
        if session_info:
            return session_info.get("current_phase", "waiting")

    # Session not in DB yet, or session_info is None - use session_state fallback
    return st.session_state.get("phase", "waiting")


def moderator_interface():
    """Multi-device moderator interface with session management."""
    # Validate session
    if not st.session_state.get("session_id"):
        st.error("No active session. Please create or join a session.")
        if st.button("Return to Home", key="moderator_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    # Check if session has been created in database yet
    session_created_in_db = st.session_state.get("session_created_in_db", True)
    if session_created_in_db:
        # Verify session is still valid in database
        session_info = get_session_info(st.session_state.session_id)
        if not session_info or session_info.get("state") != "active":
            st.error("Session expired or invalid.")
            st.session_state.session_id = None
            st.session_state.session_code = None
            if st.button("Return to Home", key="moderator_return_home_invalid_session"):
                st.query_params.clear()
                st.rerun()
            return
    else:
        # Session not yet in database - show configuration message
        st.info(
            "Please configure your experiment settings below, then click 'Start Trial' to begin."
        )

    # Recover phase from database on browser refresh
    # Moderator interface uses simplified phase logic: either setup or monitoring
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

    # ===== ROBOT PREPARING PHASE CONTROL =====
    # Show "Sample Prepared" button ONLY in robot_preparing phase
    current_phase_str = get_current_phase_safe()
    phase = ExperimentPhase.from_string(current_phase_str)

    if phase == ExperimentPhase.ROBOT_PREPARING:
        st.markdown("---")
        col_prep1, col_prep2, col_prep3 = st.columns([1, 2, 1])
        with col_prep2:
            if st.button(
                "Mark Sample Ready",
                type="primary",
                key="mark_prepared",
                use_container_width=True,
            ):
                ExperimentStateMachine.transition(
                    new_phase=ExperimentPhase.QUESTIONNAIRE,
                    session_id=st.session_state.session_id,
                )
                st.success("Sample marked as ready! Subject will answer questionnaire.")
                time.sleep(0.5)
                st.rerun()

    # ===== SESSION STATE MANAGEMENT =====
    # Initialize phase if not set (moderator starts in waiting phase)
    initialize_phase(default_phase="waiting")

    # ===== EXPERIMENT CONFIGURATION & START CONTROLS (HIGHEST PRIORITY) =====
    st.markdown("---")

    # Show different views based on experiment phase
    if ExperimentStateMachine.should_show_setup():
        # SETUP MODE: Show experiment configuration
        st.markdown("### Experiment Setup & Launch")
    else:
        # MONITORING MODE: Show session controls and configuration summary
        col_config, col_reset = st.columns([3, 1])
        with col_config:
            st.markdown("### Active Session Configuration")

            # Display current session configuration
            if st.session_state.get("selected_ingredients") and st.session_state.get(
                "ingredient_ranges"
            ):
                # Get interface and method info
                num_ingredients = len(st.session_state.selected_ingredients)
                interface_type = "2D Grid" if num_ingredients == 2 else "Slider-based"
                method = (
                    st.session_state.get("mapping_method", "linear")
                    if num_ingredients == 2
                    else "Independent"
                )
                random_start = st.session_state.get("use_random_start", False)

                # Display configuration in a compact format
                config_col1, config_col2, config_col3 = st.columns(3)

                with config_col1:
                    st.caption("**Interface:**")
                    st.write(f"{interface_type}")

                with config_col2:
                    st.caption("**Method:**")
                    st.write(f"{method}")

                with config_col3:
                    st.caption("**Random Start:**")
                    st.write(f"{'Yes' if random_start else 'No'}")

                # Display ingredient ranges in a compact expander
                with st.expander("View Ingredient Ranges", expanded=False):
                    for ingredient_name in st.session_state.selected_ingredients:
                        if ingredient_name in st.session_state.ingredient_ranges:
                            ranges = st.session_state.ingredient_ranges[ingredient_name]
                            st.write(
                                f"**{ingredient_name}:** {ranges['min']:.1f} - {ranges['max']:.1f} mM"
                            )

        with col_reset:
            # New Session button to reset back to setup
            st.write("reset_session_placeholder")  # Placeholder for layout alignment
            """
            if st.button(
                "New Session",
                type="secondary",
                use_container_width=True,
                key="new_session_button",
                help="End current session and return to setup",
            ):
                # Clear participant session first
                if "participant" in st.session_state:
                    clear_participant_session(st.session_state.participant)

                # Transition back to WAITING phase (replaces session_active = False)
                try:
                    ExperimentStateMachine.transition(
                        new_phase=ExperimentPhase.WAITING,
                        session_code=st.session_state.session_code,  # Display only
                        sync_to_database=True
                    )
                    st.toast("Session ended. Returning to setup...")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    # Fallback: directly set phase if state machine fails
                    import logging
                    logging.warning(f"State machine transition failed: {e}. Using direct assignment.")
                    st.session_state.phase = "waiting"
                    st.toast("Session ended. Returning to setup...")
                    time.sleep(1)
                    st.rerun()
            """

    # Show setup section only in waiting phase
    if ExperimentStateMachine.should_show_setup():
        # Two-column layout for configuration and start controls
        config_col1, config_col2 = st.columns([2, 1])

        with config_col1:
            # Multi-component mixture configuration
            st.markdown("#### Ingredient Configuration")

            # Number of ingredients selection
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
                "Select Ingredients:",
                options=available_ingredients,
                default=st.session_state.selected_ingredients,
                help="Choose 2-6 ingredients for your experiment (2 = 2D grid, 3+ = sliders)",
                key="moderator_ingredient_selector",
            )

            # Validation: ensure 2-6 ingredients are selected
            if len(selected_ingredients) < 2:
                st.error("Please select at least 2 ingredients")
                selected_ingredients = (
                    st.session_state.selected_ingredients
                )  # Keep previous valid selection
            elif len(selected_ingredients) > 6:
                st.error("Maximum 6 ingredients allowed")
                selected_ingredients = selected_ingredients[:6]  # Truncate to 6

            # Update session state
            st.session_state.selected_ingredients = selected_ingredients

        # ===== INGREDIENT RANGE CONFIGURATION =====
        if selected_ingredients:
            st.markdown("#### Concentration Ranges")

            # Initialize ingredient ranges in session state
            if "ingredient_ranges" not in st.session_state:
                st.session_state.ingredient_ranges = {}

            # Create range selectors for each selected ingredient
            range_cols = st.columns(2)  # Two columns for compact layout
            for i, ingredient_name in enumerate(selected_ingredients):
                col_idx = i % 2
                with range_cols[col_idx]:
                    st.markdown(f"**{ingredient_name}**")

                    # Get default ranges from DEFAULT_INGREDIENT_CONFIG
                    from callback import DEFAULT_INGREDIENT_CONFIG

                    default_ingredient = next(
                        (
                            ing
                            for ing in DEFAULT_INGREDIENT_CONFIG
                            if ing["name"] == ingredient_name
                        ),
                        None,
                    )
                    default_min = (
                        default_ingredient.get("min_concentration", 0.0)
                        if default_ingredient
                        else 0.0
                    )
                    default_max = (
                        default_ingredient.get("max_concentration", 20.0)
                        if default_ingredient
                        else 20.0
                    )

                    # Initialize with defaults if not set
                    if ingredient_name not in st.session_state.ingredient_ranges:
                        st.session_state.ingredient_ranges[ingredient_name] = {
                            "min": default_min,
                            "max": default_max,
                        }

                    current_range = st.session_state.ingredient_ranges[ingredient_name]

                    # Create input fields for min and max
                    min_col, max_col = st.columns(2)
                    with min_col:
                        min_val = st.number_input(
                            f"Min (mM)",
                            min_value=0.0,
                            max_value=1000.0,
                            value=current_range["min"],
                            step=0.1,
                            key=f"min_{ingredient_name}",
                            help=f"Minimum concentration for {ingredient_name}",
                        )
                    with max_col:
                        max_val = st.number_input(
                            f"Max (mM)",
                            min_value=0.1,
                            max_value=1000.0,
                            value=current_range["max"],
                            step=0.1,
                            key=f"max_{ingredient_name}",
                            help=f"Maximum concentration for {ingredient_name}",
                        )

                    # Validation: ensure min < max
                    if min_val >= max_val:
                        st.error(f"Min must be less than Max for {ingredient_name}")
                        # Keep previous valid values
                        min_val = current_range["min"]
                        max_val = current_range["max"]

                    # Update session state
                    st.session_state.ingredient_ranges[ingredient_name] = {
                        "min": min_val,
                        "max": max_val,
                    }

            st.markdown("---")

        # ===== QUESTIONNAIRE CONFIGURATION =====
        st.markdown("#### Questionnaire Selection")

        # Import questionnaire configuration
        from questionnaire_config import (
            list_available_questionnaires,
            get_default_questionnaire_type,
            get_questionnaire_config,
        )

        # Get available questionnaires
        available_questionnaires = list_available_questionnaires()
        questionnaire_options = {
            q[0]: f"{q[1]} - {q[2]}" for q in available_questionnaires
        }

        # Initialize questionnaire type in session state
        if "selected_questionnaire_type" not in st.session_state:
            st.session_state.selected_questionnaire_type = (
                get_default_questionnaire_type()
            )

        # Questionnaire selector
        selected_questionnaire_type = st.selectbox(
            "Questionnaire Type:",
            options=list(questionnaire_options.keys()),
            format_func=lambda x: questionnaire_options[x],
            index=list(questionnaire_options.keys()).index(
                st.session_state.selected_questionnaire_type
            ),
            help="Select the type of questionnaire participants will complete",
            key="moderator_questionnaire_selector",
        )

        # Update session state
        st.session_state.selected_questionnaire_type = selected_questionnaire_type

        # Show questionnaire preview
        questionnaire_config = get_questionnaire_config(selected_questionnaire_type)  # type: ignore
        if questionnaire_config:
            with st.expander("Preview Questionnaire Questions", expanded=False):
                st.markdown(f"**{questionnaire_config['name']}**")
                st.caption(questionnaire_config.get("description", ""))

                for i, question in enumerate(
                    questionnaire_config.get("questions", []), 1
                ):
                    st.markdown(f"{i}. **{question['label']}**")
                    st.caption(f"   Type: {question['type'].title()}")
                    if question["type"] == "slider":
                        st.caption(f"   Range: {question['min']} - {question['max']}")
                        if "scale_labels" in question:
                            st.caption(
                                f"   Labels: {question['min']}=\"{question['scale_labels'].get(question['min'], '')}\" ... {question['max']}=\"{question['scale_labels'].get(question['max'], '')}\""
                            )
                    elif question["type"] == "dropdown":
                        st.caption(
                            f"   Options: {', '.join(question.get('options', []))}"
                        )

                # Show Bayesian optimization target
                if "bayesian_target" in questionnaire_config:
                    st.markdown("---")
                    st.markdown("**Bayesian Optimization Target:**")
                    target = questionnaire_config["bayesian_target"]
                    st.caption(f"Variable: {target['variable']}")
                    st.caption(f"Goal: {target['description']}")

        st.markdown("---")

        # ===== BAYESIAN OPTIMIZATION CONFIGURATION =====
        st.markdown("#### Bayesian Optimization Settings")

        # Initialize BO config in session state
        if "bo_config" not in st.session_state:
            from bayesian_optimizer import get_default_bo_config

            st.session_state.bo_config = get_default_bo_config()

        # Enable/disable BO
        bo_enabled = st.checkbox(
            "Enable Bayesian Optimization",
            value=st.session_state.bo_config.get("enabled", True),
            help="Use machine learning to guide participants toward optimal preferences after initial exploration",
            key="moderator_bo_enabled",
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
                    key="moderator_bo_acq_func",
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
                    key="moderator_bo_min_samples",
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
                        key="moderator_bo_xi",
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
                        key="moderator_bo_kappa",
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
                    key="moderator_bo_kernel_nu",
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
                        key="moderator_bo_alpha",
                    )
                    st.session_state.bo_config["alpha"] = alpha

                    # Only use final responses
                    only_final = st.checkbox(
                        "Only Use Final Responses",
                        value=st.session_state.bo_config["only_final_responses"],
                        help="Train BO only on participants' final choices (recommended)",
                        key="moderator_bo_only_final",
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
                        key="moderator_bo_restarts",
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
                        key="moderator_bo_seed",
                    )
                    st.session_state.bo_config["random_state"] = random_state

            st.caption(
                "For detailed guidance on kernel selection and BO parameters, see `docs/bayesian_optimization_kernel_guide.md`"
            )

        st.markdown("---")

        # Auto-determine number of ingredients from selection
        num_ingredients = len(selected_ingredients)

        # Initialize experiment configuration in session state
        if "experiment_config" not in st.session_state:
            # Ensure DEFAULT_INGREDIENT_CONFIG is available
            from callback import DEFAULT_INGREDIENT_CONFIG

            st.session_state.experiment_config = {
                "num_ingredients": 2,
                "ingredients": DEFAULT_INGREDIENT_CONFIG[:2],
            }

        # Update configuration when number changes
        if num_ingredients != st.session_state.experiment_config["num_ingredients"]:
            # Ensure DEFAULT_INGREDIENT_CONFIG is available
            from callback import DEFAULT_INGREDIENT_CONFIG

            st.session_state.experiment_config["num_ingredients"] = num_ingredients
            st.session_state.experiment_config["ingredients"] = (
                DEFAULT_INGREDIENT_CONFIG[:num_ingredients]
            )

        # Create mixture handler
        mixture = MultiComponentMixture(
            st.session_state.experiment_config["ingredients"]
        )
        interface_type = mixture.get_interface_type()

        # Method selection (only for 2D grid)
        if interface_type == INTERFACE_2D_GRID:
            method = st.selectbox(
                "Mapping Method:",
                ["linear", "logarithmic", "exponential"],
                help="Choose how coordinates map to concentrations",
                key="moderator_mapping_method_selector",
            )
            # Store in session state immediately for database persistence
            st.session_state.selected_method = method
        else:
            method = INTERFACE_SLIDERS
            st.session_state.selected_method = method

            # Random start option for sliders
            st.session_state.use_random_start = st.checkbox(
                "Random Starting Positions",
                value=st.session_state.get("use_random_start", True),
                help="Start sliders at randomized positions instead of 50% for each trial",
                key="moderator_random_start_toggle",
            )

        with config_col2:
            st.markdown("#### Launch Trial")

            # Show current participant
            participant_display = st.session_state.get("participant", "None selected")
            st.write(f"**Current Participant:** {participant_display}")

            # Start trial button (prominent)
            if st.button(
                "Start Trial",
                type="primary",
                use_container_width=True,
                key="moderator_start_trial_button",
            ):
                # Create session in database if not already created
                if not st.session_state.get("session_created_in_db", False):
                    from sql_handler import update_session_with_config
                    from bayesian_optimizer import get_default_bo_config

                    # Get configuration from session state
                    num_ingredients = st.session_state.experiment_config[
                        "num_ingredients"
                    ]
                    interface_type = st.session_state.experiment_config.get(
                        "interface_type", "grid_2d"
                    )
                    # Use the freshly selected method from session state
                    method = st.session_state.get("selected_method", "logarithmic")

                    # Build ingredient list for database
                    ingredients_for_db = []
                    for idx, ingredient_name in enumerate(
                        st.session_state.selected_ingredients
                    ):
                        ranges = st.session_state.ingredient_ranges.get(
                            ingredient_name, {}
                        )
                        ingredients_for_db.append(
                            {
                                "position": idx,
                                "name": ingredient_name,
                                "min": ranges.get("min", 0),
                                "max": ranges.get("max", 100),
                                "unit": "mM",
                            }
                        )

                    # Get BO config or use defaults
                    bo_config = st.session_state.get(
                        "bo_config", get_default_bo_config()
                    )

                    # Build full experiment config
                    full_experiment_config = {
                        **st.session_state.experiment_config,
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
                        num_ingredients=num_ingredients,
                        interface_type=interface_type,
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
                        st.error(
                            "Failed to create session in database. Please try again."
                        )
                        st.stop()

                num_ingredients = st.session_state.experiment_config["num_ingredients"]

                # Build ingredient configs with custom ranges
                # FIXED: Pass moderator's actual ingredient selection to start_trial
                ingredient_configs = []
                for ingredient_name in st.session_state.selected_ingredients:
                    # Get base configuration from defaults
                    from callback import DEFAULT_INGREDIENT_CONFIG

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
                        continue

                    # Create a copy and apply custom ranges if set
                    custom_config = base_config.copy()

                    if ingredient_name in st.session_state.ingredient_ranges:
                        ranges = st.session_state.ingredient_ranges[ingredient_name]
                        custom_config["min_concentration"] = ranges["min"]
                        custom_config["max_concentration"] = ranges["max"]

                    ingredient_configs.append(custom_config)

                # Validate ingredient count matches
                if len(ingredient_configs) != num_ingredients:
                    st.error(
                        f"Configuration error: Expected {num_ingredients} ingredients, got {len(ingredient_configs)}"
                    )
                else:
                    # Start trial with moderator's ingredient selection
                    success = start_trial(
                        "mod",
                        st.session_state.participant,
                        method,
                        num_ingredients,
                        selected_ingredients=st.session_state.selected_ingredients,
                        ingredient_configs=ingredient_configs,
                    )
                    if success:
                        clear_canvas_state()  # Clear any previous canvas state
                        # Transition to trial_started phase (replaces session_active = True)
                        # Note: start_trial() in callback.py handles the phase transition
                        st.toast(f"Trial started for {st.session_state.participant}")
                        time.sleep(1)
                        st.rerun()

        # Helper message at bottom of setup section
        st.markdown("---")

    # ===== SUBJECT CONNECTION & ACCESS SECTION =====
    st.markdown("---")
    from state_machine import recover_phase_from_database

    recovered_phase = recover_phase_from_database(st.session_state.session_id)
    if recovered_phase == "waiting":
        with st.expander("Subject Access - QR Code & Session Info", expanded=False):
            st.info(
                "Waiting for subject to join session... Share the QR code or session code below."
            )

            # Smart URL detection - production first, then localhost for development
            try:
                server_address = st.get_option("browser.serverAddress")
                if server_address and "streamlit.app" in server_address:
                    base_url = f"https://{server_address}"
                elif st.get_option("server.headless"):
                    # Running in cloud/headless mode, use production URL
                    base_url = "https://robotaste.streamlit.app"
                else:
                    # Check if running locally (port 8501 indicates local development)
                    base_url = "http://localhost:8501"  # Local development
            except:
                # Default to production URL for QR codes
                base_url = "https://robotaste.streamlit.app"

            display_session_qr_code(
                st.session_state.session_code, base_url, context="waiting"
            )
    else:
        st.success("Subject device connected and active")

    # ===== ORGANIZED TABS FOR MONITORING & MANAGEMENT =====
    # Only show monitoring tabs when trial is in active phase
    if ExperimentStateMachine.should_show_monitoring():
        st.markdown("---")

        # Streamlined tabs - keep essential functionality organized
        main_tab1, main_tab2, main_tab3 = st.tabs(
            ["Live Monitor", "Analytics", "Settings"]
        )

        with main_tab1:
            st.markdown("### Live Subject Monitoring")

            # Header with refresh and status
            col_refresh, col_status, col_time = st.columns([1, 2, 2])

            with col_refresh:
                if st.button(
                    "Refresh", key="live_monitor_refresh", use_container_width=True
                ):
                    st.rerun()

            # Get current position from latest sample
            concentrations = get_latest_sample_concentrations(
                st.session_state.session_id
            )

            if not concentrations:
                st.info("Waiting for subject to start...")
            else:
                with col_status:
                    st.markdown(f"**Status:** Latest Sample")

                with col_time:
                    # Get sample timestamp from database
                    samples = get_session_samples(st.session_state.session_id)
                    if samples:
                        latest_sample = samples[-1]  # Most recent
                        created_at = latest_sample.get("created_at", "Unknown")
                        st.caption(f"Last update: {created_at}")
                    else:
                        st.caption("Last update: Unknown")

                st.markdown("---")

                # Main layout: Left = Current Selection, Right = Recipe
                col_left, col_right = st.columns([1.2, 1])

                # ============= LEFT PANEL: Current Selection =============
                with col_left:
                    st.markdown("#### Current Selection")

                    if not concentrations:
                        st.warning("No concentration data available")
                    else:
                        # Get ingredient configs from session state
                        if (
                            hasattr(st.session_state, "ingredients")
                            and st.session_state.ingredients
                        ):
                            ingredient_configs = st.session_state.ingredients
                        else:
                            # Fallback to defaults
                            from callback import DEFAULT_INGREDIENT_CONFIG

                            num_ing = len(concentrations)
                            ingredient_configs = DEFAULT_INGREDIENT_CONFIG[:num_ing]

                        # Display each ingredient with bar
                        for ingredient_name, concentration_mM in concentrations.items():
                            # Find config for this ingredient
                            config = next(
                                (
                                    ing
                                    for ing in ingredient_configs
                                    if ing["name"] == ingredient_name
                                ),
                                None,
                            )

                            if config:
                                min_mM = config["min_concentration"]
                                max_mM = config["max_concentration"]

                                # Calculate percentage of scale
                                percentage = (
                                    (concentration_mM - min_mM) / (max_mM - min_mM)
                                ) * 100
                                percentage = max(
                                    0, min(100, percentage)
                                )  # Clamp to 0-100

                                # Display ingredient name
                                st.markdown(f"**{ingredient_name}**")

                                # Progress bar
                                st.progress(percentage / 100.0)

                                # Values below bar
                                col_conc, col_pct = st.columns(2)
                                with col_conc:
                                    st.caption(f"{concentration_mM:.3f} mM")
                                with col_pct:
                                    st.caption(f"{percentage:.1f}% of scale")

                                st.markdown("")  # Spacing

                # ============= RIGHT PANEL: Recipe Card =============
                with col_right:
                    st.markdown("#### Preparation Recipe")

                    if concentrations and ingredient_configs:
                        # Calculate stock volumes
                        from callback import calculate_stock_volumes

                        recipe = calculate_stock_volumes(
                            concentrations=concentrations,
                            ingredient_configs=ingredient_configs,
                            final_volume_mL=10.0,  # CONFIGURABLE - 10 mL final volume
                        )

                        # Display recipe card
                        st.markdown("**Stock Solutions:**")

                        for ingredient_name, volume_µL in recipe[
                            "stock_volumes"
                        ].items():
                            # Get stock concentration for display
                            config = next(
                                (
                                    ing
                                    for ing in ingredient_configs
                                    if ing["name"] == ingredient_name
                                ),
                                None,
                            )
                            stock_mM = (
                                config.get("stock_concentration_mM", 1000)
                                if config
                                else 1000
                            )

                            st.markdown(
                                f"**{ingredient_name}** Stock ({stock_mM:.0f} mM)"
                            )
                            st.markdown(f"└─ `{volume_µL:.3f} µL`")
                            st.markdown("")

                        # Water volume
                        st.markdown("**Water**")
                        st.markdown(f"└─ `{recipe['water_volume']:.1f} µL`")
                        st.markdown("")

                        # Total
                        st.markdown("---")
                        st.markdown(
                            f"**Total Volume:** `{recipe['total_volume']:.1f} mL`"
                        )
                    else:
                        st.info("Configure ingredients to see recipe")

            # Auto-refresh every 15 seconds (reduced flicker)
            if st.session_state.get("auto_refresh", True):
                st.caption("Auto-refresh enabled (15s interval)")

                # Sync phase from database (in case subject progressed independently)
                session_info = get_session_info(st.session_state.session_id)
                if session_info:
                    phase_from_db = session_info.get(
                        "current_phase", st.session_state.get("phase", "waiting")
                    )
                    if phase_from_db != st.session_state.get("phase"):
                        logger.info(
                            f"Moderator synced phase: {st.session_state.get('phase')} -> {phase_from_db}"
                        )
                        st.session_state.phase = phase_from_db

        with main_tab2:
            st.markdown("### Session Analytics")

            # ===== SESSION STATISTICS =====
            try:
                stats = get_session_stats(st.session_state.session_id)
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Cycles", stats.get("total_cycles", 0))
                col2.metric("Final Samples", stats.get("final_samples", 0))
                col3.metric("Status", stats.get("state", "unknown"))
                col4.metric(
                    "Created",
                    stats.get("created_at", "")[:10] if stats.get("created_at") else "",
                )
            except Exception as e:
                st.warning(f"Could not load session stats: {e}")

            st.markdown("---")

            # ===== BAYESIAN OPTIMIZATION STATUS =====
            st.markdown("### Bayesian Optimization")

            try:
                from bayesian_optimizer import get_bo_status
                import plotly.graph_objects as go
                import numpy as np

                bo_status = get_bo_status(st.session_state.session_id)

                # BO Enable/Disable Toggle
                col1, col2 = st.columns([1, 3])
                with col1:
                    # Get current BO enabled status
                    current_enabled = bo_status.get("is_enabled", True)
                    bo_enabled = st.checkbox(
                        "Enable BO",
                        value=current_enabled,
                        key="bo_enabled_toggle",
                        help="Enable Bayesian Optimization for automatic sample selection after cycle 2",
                    )

                    # Update BO config if toggle changed
                    if bo_enabled != current_enabled:
                        session = get_session(st.session_state.session_id)
                        if session and "experiment_config" in session:
                            experiment_config = session["experiment_config"]
                            if "bayesian_optimization" not in experiment_config:
                                from bayesian_optimizer import get_default_bo_config

                                experiment_config["bayesian_optimization"] = (
                                    get_default_bo_config()
                                )

                            experiment_config["bayesian_optimization"][
                                "enabled"
                            ] = bo_enabled

                            # Update in database
                            import json

                            with get_database_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute(
                                    """
                                    UPDATE sessions
                                    SET experiment_config = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE session_id = ?
                                    """,
                                    (
                                        json.dumps(experiment_config),
                                        st.session_state.session_id,
                                    ),
                                )
                                conn.commit()
                            st.rerun()

                with col2:
                    st.info(bo_status.get("status_message", "Unknown"))

                # Display BO metrics
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Current Cycle", bo_status.get("current_cycle", 0))
                col2.metric("Samples Collected", bo_status.get("samples_collected", 0))
                col3.metric("Min Required", bo_status.get("min_samples_required", 3))

                # Show latest prediction if available
                latest_pred = bo_status.get("latest_prediction")
                latest_unc = bo_status.get("latest_uncertainty")
                if latest_pred is not None and latest_unc is not None:
                    col4.metric(
                        "Latest Prediction", f"{latest_pred:.2f} ± {latest_unc:.2f}"
                    )
                else:
                    col4.metric("Latest Prediction", "N/A")

                # Visualization (only if BO is active)
                if (
                    bo_status.get("is_active")
                    and bo_status.get("samples_collected", 0) >= 3
                ):
                    st.markdown("#### Predicted Preference Landscape")

                    try:
                        # Get training data
                        from bayesian_optimizer import train_bo_model_for_participant
                        import sql_handler as sql

                        # Get session config to determine interface type
                        session = sql.get_session(st.session_state.session_id)
                        if session and "experiment_config" in session:
                            experiment_config = session["experiment_config"]
                            num_ingredients = experiment_config.get(
                                "num_ingredients", 2
                            )
                            ingredients = experiment_config.get("ingredients", [])

                            # Train BO model
                            participant_id = session.get("participant_id", "unknown")
                            bo_model = train_bo_model_for_participant(
                                participant_id=participant_id,
                                session_id=st.session_state.session_id,
                                bo_config=bo_status.get("bo_config", {}),
                            )

                            if bo_model and num_ingredients == 2:
                                # 2D Grid visualization - Heatmap
                                from bayesian_optimizer import (
                                    generate_candidate_grid_2d,
                                )

                                # Get ingredient ranges
                                ing_ranges = [
                                    (ing["min_concentration"], ing["max_concentration"])
                                    for ing in ingredients[:2]
                                ]

                                # Generate fine grid for visualization
                                candidates = generate_candidate_grid_2d(
                                    sugar_range=ing_ranges[0],
                                    salt_range=ing_ranges[1],
                                    n_points=30,  # 30x30 grid for smooth heatmap
                                )

                                # Get predictions
                                predictions, uncertainties = bo_model.predict(
                                    candidates, return_std=True
                                )

                                # Reshape for heatmap
                                n_points = 30
                                x_vals = candidates[
                                    : n_points**2 : n_points, 0
                                ]  # First ingredient values
                                y_vals = candidates[
                                    :n_points, 1
                                ]  # Second ingredient values
                                z_vals = predictions.reshape(n_points, n_points)

                                # Create heatmap
                                fig = go.Figure(
                                    data=go.Heatmap(
                                        x=x_vals,
                                        y=y_vals,
                                        z=z_vals,
                                        colorscale="RdYlGn",
                                        colorbar=dict(title="Predicted<br>Score"),
                                    )
                                )

                                # Add past sample markers
                                training_df = sql.get_training_data(
                                    st.session_state.session_id,
                                    only_final=bo_status.get("bo_config", {}).get(
                                        "only_final_responses", True
                                    ),
                                )

                                if training_df is not None and len(training_df) > 0:
                                    ing_names = [ing["name"] for ing in ingredients[:2]]
                                    fig.add_trace(
                                        go.Scatter(
                                            x=training_df[ing_names[0]],
                                            y=training_df[ing_names[1]],
                                            mode="markers",
                                            marker=dict(
                                                size=12,
                                                color="white",
                                                symbol="circle",
                                                line=dict(color="black", width=2),
                                            ),
                                            name="Past Samples",
                                            text=[
                                                f"Score: {score:.1f}"
                                                for score in training_df["target_value"]
                                            ],
                                            hovertemplate="%{text}<br>%{x:.2f}, %{y:.2f}<extra></extra>",
                                        )
                                    )

                                # Formatting
                                ing_names = [ing["name"] for ing in ingredients[:2]]
                                fig.update_layout(
                                    xaxis_title=f"{ing_names[0]} (mM)",
                                    yaxis_title=f"{ing_names[1]} (mM)",
                                    height=500,
                                    hovermode="closest",
                                )

                                st.plotly_chart(fig, use_container_width=True)

                            elif bo_model and num_ingredients > 2:
                                # Multi-ingredient visualization - Parallel coordinates
                                training_df = sql.get_training_data(
                                    st.session_state.session_id,
                                    only_final=bo_status.get("bo_config", {}).get(
                                        "only_final_responses", True
                                    ),
                                )

                                if training_df is not None and len(training_df) > 0:
                                    ing_names = [ing["name"] for ing in ingredients]

                                    # Create dimensions for parallel coordinates
                                    dimensions = []
                                    for ing_name in ing_names:
                                        dimensions.append(
                                            dict(
                                                label=ing_name,
                                                values=training_df[ing_name],
                                            )
                                        )

                                    # Add target variable
                                    dimensions.append(
                                        dict(
                                            label="Score",
                                            values=training_df["target_value"],
                                        )
                                    )

                                    fig = go.Figure(
                                        data=go.Parcoords(
                                            line=dict(
                                                color=training_df["target_value"],
                                                colorscale="RdYlGn",
                                                showscale=True,
                                                cmin=training_df["target_value"].min(),
                                                cmax=training_df["target_value"].max(),
                                            ),
                                            dimensions=dimensions,
                                        )
                                    )

                                    fig.update_layout(
                                        height=400,
                                        title="Ingredient Concentrations vs Scores",
                                    )

                                    st.plotly_chart(fig, use_container_width=True)

                    except Exception as viz_error:
                        st.warning(f"Could not generate visualization: {viz_error}")

            except Exception as e:
                st.warning(f"Could not load BO status: {e}")

            st.markdown("---")

            # ===== CYCLE HISTORY TABLE =====
            st.markdown("### Cycle History")

            try:
                cycle_num = get_current_cycle(st.session_state.session_id)
                st.info(f"Current Cycle: {cycle_num}")

                # Get all samples for this session
                samples = get_session_samples(
                    st.session_state.session_id, only_final=False
                )

                if samples:
                    # Build display dataframe
                    history_data = []
                    for sample in samples:
                        row = {
                            "Cycle": sample.get("cycle_number", "?"),
                            "Concentrations": ", ".join(
                                [
                                    f"{k}: {v:.1f}"
                                    for k, v in sample.get(
                                        "ingredient_concentration", {}
                                    ).items()
                                ]
                            ),
                            "Target Score": sample.get("questionnaire_answer", {}).get(
                                "overall_liking", "N/A"
                            ),
                            "Is Final": "Yes" if sample.get("is_final") else "",
                            "Timestamp": (
                                sample.get("created_at", "")[:19]
                                if sample.get("created_at")
                                else ""
                            ),
                        }
                        history_data.append(row)

                    df = pd.DataFrame(history_data)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("No cycles completed yet")
            except Exception as e:
                st.warning(f"Could not load cycle history: {e}")

            st.markdown("---")

            # ===== CYCLE MANAGEMENT CONTROLS =====
            # Show controls when in SELECTION phase
            if phase == ExperimentPhase.SELECTION:
                st.markdown("### Session Management")

                # Only show Finish Session button (Start Next Cycle is now automatic)
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button(
                        "Finish Session",
                        type="primary",
                        use_container_width=True,
                        key="finish_session",
                    ):
                        # Show confirmation
                        if st.session_state.get("confirm_finish"):
                            # Update session state to completed
                            update_session_state(
                                st.session_state.session_id, "completed"
                            )

                            # Transition to complete
                            ExperimentStateMachine.transition(
                                new_phase=ExperimentPhase.COMPLETE,
                                session_id=st.session_state.session_id,
                            )
                            st.success("Session completed!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.session_state.confirm_finish = True
                            st.warning("Click 'Finish Session' again to confirm")
                            st.rerun()

        with main_tab3:
            st.markdown("### Session Settings")

            # Theme Settings
            st.markdown("#### Theme & Display")

            # Force dark mode option for better readability
            force_dark_mode = st.checkbox(
                "Force Dark Mode (recommended for better readability)",
                value=st.session_state.get("force_dark_mode", False),
                key="moderator_force_dark_mode",
                help="Enables dark mode theme to fix text visibility issues in select boxes",
            )

            if force_dark_mode != st.session_state.get("force_dark_mode", False):
                st.session_state.force_dark_mode = force_dark_mode
                # Add JavaScript to apply theme change
                if force_dark_mode:
                    st.markdown(
                        """
                        <script>
                        document.documentElement.setAttribute('data-theme', 'dark');
                        </script>
                        """,
                        unsafe_allow_html=True,
                    )
                st.success(
                    "Theme setting updated! Refresh the page to see full effects."
                )

            # Display Settings
            auto_refresh = st.checkbox(
                "Auto-refresh monitoring",
                value=st.session_state.get("auto_refresh", True),
                key="moderator_auto_refresh_setting",
                help="Automatically refresh live monitoring every 15 seconds",
            )
            st.session_state.auto_refresh = auto_refresh

            st.divider()

            # Data Export Section
            st.markdown("#### Data Export")

            if st.button(
                "Export Session Data (CSV)",
                key="moderator_export_csv",
                help="Download all experiment data for this session as CSV file",
            ):
                try:
                    session_code = st.session_state.get(
                        "session_code", "default_session"
                    )

                    # Try new export function first, fallback to old one if needed
                    csv_data = export_session_csv(session_code)

                    if csv_data:
                        # Create download button
                        st.download_button(
                            label="Download CSV File",
                            data=csv_data,
                            file_name=f"robotaste_session_{session_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_csv_data",
                        )
                        st.success("Export data ready for download!")
                    else:
                        st.warning("No data found to export for this session.")

                except Exception as e:
                    st.error(f"Error exporting data: {e}")

            # Summary of data that will be exported
            with st.expander("What data gets exported?"):
                st.markdown(
                    """
                **CSV Export includes:**
                - Participant IDs and session information
                - Interface type (grid vs. slider) and method used
                - Random start settings and initial positions
                - All user interactions (clicks, slider adjustments)
                - Reaction times and timestamps
                - Actual concentrations (mM values) for all ingredients
                - Final response indicators
                - Questionnaire responses (if any)
                
                **Data is organized chronologically** for easy analysis in research tools like R, Python, or Excel.
                """
                )
    # ===== AUTO-REFRESH LOGIC =====
    if ExperimentStateMachine.should_show_monitoring():
        if st.session_state.get("auto_refresh", True):
            # Sync phase from database (in case subject progressed independently)
            session_info = get_session_info(st.session_state.session_id)
            if session_info:
                phase_from_db = session_info.get(
                    "current_phase", st.session_state.get("phase", "waiting")
                )
                if phase_from_db != st.session_state.get("phase"):
                    logger.info(
                        f"Moderator synced phase: {st.session_state.get('phase')} -> {phase_from_db}"
                    )
                    st.session_state.phase = phase_from_db
            time.sleep(15)
            st.rerun()
