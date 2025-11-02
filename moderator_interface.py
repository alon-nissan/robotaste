from callback import (
    INTERFACE_2D_GRID,
    INTERFACE_SLIDERS,
    MultiComponentMixture,
    clear_canvas_state,
    start_trial,
    calculate_stock_volumes,
)
from ui_components import create_header
from session_manager import (
    display_session_qr_code,
    get_connection_status,
    get_session_info,
)
from sql_handler import (
    clear_participant_session,
    export_responses_csv,
    get_live_subject_position,
)
from state_machine import ExperimentPhase, ExperimentStateMachine, initialize_phase


import streamlit as st


import time
from datetime import datetime


def moderator_interface():
    """Multi-device moderator interface with session management."""

    # Validate session
    if not st.session_state.session_code:
        st.error("No active session. Please create or join a session.")
        if st.button("🏠 Return to Home", key="moderator_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    session_info = get_session_info(st.session_state.session_code)
    if not session_info or not session_info["is_active"]:
        st.error("Session expired or invalid.")
        st.session_state.session_code = None
        if st.button("🏠 Return to Home", key="moderator_return_home_invalid_session"):
            st.query_params.clear()
            st.rerun()
        return

    # Recover phase from database on browser refresh
    # Moderator interface uses simplified phase logic: either setup or monitoring
    if "phase" not in st.session_state:
        from state_machine import recover_phase_from_database
        recovered_phase = recover_phase_from_database(st.session_state.session_code)

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

    # Header
    create_header(
        f"Moderator Dashboard - {st.session_state.session_code}",
        f"Managing session for {session_info['moderator_name']}",
        "",
    )

    # ===== TOP SECTION: Essential Session Info & Quick Actions =====
    st.markdown("### Session Overview")

    # Essential session metrics in a clean layout
    overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)

    with overview_col1:
        st.metric("🔑 Session Code", st.session_state.session_code)

    with overview_col2:
        connection_status = get_connection_status(st.session_state.session_code)
        is_connected = connection_status.get("subject_connected", False)

        # Get subject phase from database
        current_phase_str = session_info.get("current_phase", "waiting")
        phase = ExperimentPhase.from_string(current_phase_str)

        if is_connected and phase:
            phase_display = ExperimentStateMachine.get_phase_display_name(phase)
            # Show connection + phase
            st.metric("Subject Status", f"Connected - {phase_display}")
        else:
            st.metric("Subject Status", "🟡 Waiting")

    with overview_col3:
        # Show color-coded phase badge
        current_phase_str = session_info.get("current_phase", "waiting")
        phase = ExperimentPhase.from_string(current_phase_str)
        if phase:
            phase_color = ExperimentStateMachine.get_phase_color(phase)
            phase_name = ExperimentStateMachine.get_phase_display_name(phase)
            # Use colored markdown badge
            if phase_color == "green":
                badge = f":green[{phase_name}]"
            elif phase_color == "blue":
                badge = f":blue[{phase_name}]"
            elif phase_color == "orange":
                badge = f":orange[{phase_name}]"
            elif phase_color == "yellow":
                badge = f":red[{phase_name}]"
            else:
                badge = f":gray[{phase_name}]"
            st.metric("Current Phase", badge)
        else:
            st.metric("Current Phase", "Waiting")

    with overview_col4:
        st.metric("⏰ Status", "🟢 Active")

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
                method = st.session_state.get("mapping_method", "linear") if num_ingredients == 2 else "Independent"
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
                            st.write(f"**{ingredient_name}:** {ranges['min']:.1f} - {ranges['max']:.1f} mM")

        with col_reset:
            # New Session button to reset back to setup
            if st.button(
                "🆕 New Session",
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
                        session_code=st.session_state.session_code,
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
            st.markdown("#### 📏 Concentration Ranges")
            st.info("Set the minimum and maximum concentrations for each ingredient")

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

        # Show interface type
        interface_info = {
            INTERFACE_2D_GRID: "2D Grid Interface (X-Y coordinates)",
            INTERFACE_SLIDERS: "Slider Interface (Independent concentrations)",
        }
        st.info(f"Interface: {interface_info[interface_type]}")

        # Method selection (only for 2D grid)
        if interface_type == INTERFACE_2D_GRID:
            method = st.selectbox(
                "🧮 Mapping Method:",
                ["linear", "logarithmic", "exponential"],
                help="Choose how coordinates map to concentrations",
                key="moderator_mapping_method_selector",
            )

            # Method explanation
            method_info = {
                "linear": "Direct proportional mapping",
                "logarithmic": "Logarithmic scale mapping",
                "exponential": "📉 Exponential scale mapping",
            }
            st.info(method_info[method])
        else:
            method = INTERFACE_SLIDERS
            st.info("Slider-based concentration control")

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
        st.info(
            "Configure your experiment above and click 'Start Trial' to begin monitoring."
        )

    # ===== SUBJECT CONNECTION & ACCESS SECTION =====
    st.markdown("---")

    if not connection_status["subject_connected"]:
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

            # Get current position
            current_response = get_live_subject_position(st.session_state.participant)

            if not current_response:
                st.info("Waiting for subject to start...")
            else:
                # Extract data
                concentrations = current_response.get("ingredient_concentrations", {})
                is_submitted = current_response.get("is_submitted", False)
                interface_type = current_response.get("interface_type", "slider_based")
                created_at = current_response.get("created_at", "Unknown")

                with col_status:
                    status_text = (
                        "Final Submission" if is_submitted else "Live Adjustment"
                    )
                    st.markdown(f"**Status:** {status_text}")

                with col_time:
                    st.caption(f"Last update: {created_at}")

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
                    st.markdown("#### 📝 Preparation Recipe")

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
                time.sleep(15)
                st.rerun()

        with main_tab3:
            st.markdown("### Session Settings")

            # Theme Settings
            st.markdown("#### Theme & Display")

            # Force dark mode option for better readability
            force_dark_mode = st.checkbox(
                "🌙 Force Dark Mode (recommended for better readability)",
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
                "📥 Export Session Data (CSV)",
                key="moderator_export_csv",
                help="Download all experiment data for this session as CSV file",
            ):
                try:

                    session_code = st.session_state.get(
                        "session_code", "default_session"
                    )
                    csv_data = export_responses_csv(session_code)

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
