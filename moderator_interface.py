from callback import (
    INTERFACE_2D_GRID,
    INTERFACE_SLIDERS,
    MultiComponentMixture,
    clear_canvas_state,
    start_trial,
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
    get_all_participants,
    get_latest_recipe_for_participant,
    get_latest_submitted_response,
    get_live_subject_position,
    get_participant_responses,
)


import streamlit as st


import time
from datetime import datetime


def moderator_interface():
    """Multi-device moderator interface with session management."""

    # Validate session
    if not st.session_state.session_code:
        st.error("❌ No active session. Please create or join a session.")
        if st.button("🏠 Return to Home", key="moderator_return_home_no_session"):
            st.query_params.clear()
            st.rerun()
        return

    session_info = get_session_info(st.session_state.session_code)
    if not session_info or not session_info["is_active"]:
        st.error("❌ Session expired or invalid.")
        st.session_state.session_code = None
        if st.button("🏠 Return to Home", key="moderator_return_home_invalid_session"):
            st.query_params.clear()
            st.rerun()
        return

    # Header
    create_header(
        f"Moderator Dashboard - {st.session_state.session_code}",
        f"Managing session for {session_info['moderator_name']}",
        "🎮",
    )

    # ===== TOP SECTION: Essential Session Info & Quick Actions =====
    st.markdown("### 📊 Session Overview")

    # Essential session metrics in a clean layout
    overview_col1, overview_col2, overview_col3, overview_col4 = st.columns(4)

    with overview_col1:
        st.metric("🔑 Session Code", st.session_state.session_code)

    with overview_col2:
        connection_status = get_connection_status(st.session_state.session_code)
        status_text = (
            "Connected"
            if connection_status.get("subject_connected", False)
            else "Waiting"
        )
        status_color = (
            "🟢" if connection_status.get("subject_connected", False) else "🟡"
        )
        st.metric("👤 Subject Status", f"{status_color} {status_text}")

    with overview_col3:
        st.metric("🧪 Current Phase", session_info["current_phase"].title())

    with overview_col4:
        st.metric("⏰ Status", "🟢 Active")

    # ===== SESSION STATE MANAGEMENT =====
    # Initialize session active state
    if "session_active" not in st.session_state:
        st.session_state.session_active = False

    # ===== EXPERIMENT CONFIGURATION & START CONTROLS (HIGHEST PRIORITY) =====
    st.markdown("---")

    # Show different views based on session state
    if not st.session_state.session_active:
        # SETUP MODE: Show experiment configuration
        st.markdown("### 🚀 Experiment Setup & Launch")
    else:
        # MONITORING MODE: Show session controls and configuration summary
        col_config, col_reset = st.columns([3, 1])
        with col_config:
            st.markdown("### 📊 Active Session Configuration")

            # Display current session configuration
            if st.session_state.get("selected_ingredients") and st.session_state.get(
                "ingredient_ranges"
            ):
                config_parts = []
                for ingredient_name in st.session_state.selected_ingredients:
                    if ingredient_name in st.session_state.ingredient_ranges:
                        ranges = st.session_state.ingredient_ranges[ingredient_name]
                        config_parts.append(
                            f"{ingredient_name}: {ranges['min']:.1f}-{ranges['max']:.1f} mM"
                        )

                config_display = " | ".join(config_parts)
                st.info(f"**Ingredients:** {config_display}")

                # Show interface and method info
                num_ingredients = len(st.session_state.selected_ingredients)
                interface_type = "🎯 2D Grid" if num_ingredients == 2 else "🎛️ Slider"
                method_display = (
                    st.session_state.get("mapping_method", "linear")
                    if num_ingredients == 2
                    else INTERFACE_SLIDERS
                )
                st.info(
                    f"**Interface:** {interface_type} | **Method:** {method_display}"
                )

        with col_reset:
            # New Session button to reset back to setup
            if st.button(
                "🆕 New Session",
                type="secondary",
                use_container_width=True,
                key="new_session_button",
                help="End current session and return to setup",
            ):
                # Reset session state
                st.session_state.session_active = False
                if "participant" in st.session_state:
                    clear_participant_session(st.session_state.participant)
                st.success("Session ended. Returning to setup...")
                time.sleep(1)
                st.rerun()

    # Show setup section only if session is not active
    if not st.session_state.session_active:
        # Two-column layout for configuration and start controls
        config_col1, config_col2 = st.columns([2, 1])

        with config_col1:
            # Multi-component mixture configuration
            st.markdown("#### 🧪 Ingredient Configuration")

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
                "🧪 Select Ingredients:",
                options=available_ingredients,
                default=st.session_state.selected_ingredients,
                help="Choose 2-6 ingredients for your experiment (2 = 2D grid, 3+ = sliders)",
                key="moderator_ingredient_selector",
            )

            # Validation: ensure 2-6 ingredients are selected
            if len(selected_ingredients) < 2:
                st.error("⚠️ Please select at least 2 ingredients")
                selected_ingredients = (
                    st.session_state.selected_ingredients
                )  # Keep previous valid selection
            elif len(selected_ingredients) > 6:
                st.error("⚠️ Maximum 6 ingredients allowed")
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
                        st.error(f"⚠️ Min must be less than Max for {ingredient_name}")
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
            INTERFACE_2D_GRID: "🎯 2D Grid Interface (X-Y coordinates)",
            INTERFACE_SLIDERS: "🎛️ Slider Interface (Independent concentrations)",
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
                "linear": "📈 Direct proportional mapping",
                "logarithmic": "📊 Logarithmic scale mapping",
                "exponential": "📉 Exponential scale mapping",
            }
            st.info(method_info[method])
        else:
            method = INTERFACE_SLIDERS
            st.info("🎛️ Slider-based concentration control")

            # Random start option for sliders
            st.session_state.use_random_start = st.checkbox(
                "🎲 Random Starting Positions",
                value=st.session_state.get("use_random_start", False),
                help="Start sliders at randomized positions instead of 50% for each trial",
                key="moderator_random_start_toggle",
            )

        with config_col2:
            st.markdown("#### 🚀 Launch Trial")

            # Show current participant
            participant_display = st.session_state.get("participant", "None selected")
            st.write(f"**Current Participant:** {participant_display}")

            # Start trial button (prominent)
            if st.button(
                "🚀 Start Trial",
                type="primary",
                use_container_width=True,
                key="moderator_start_trial_button",
            ):
                num_ingredients = st.session_state.experiment_config["num_ingredients"]
                success = start_trial(
                    "mod", st.session_state.participant, method, num_ingredients
                )
                if success:
                    clear_canvas_state()  # Clear any previous canvas state
                    st.session_state.session_active = True  # Activate session
                    st.success(f"✅ Trial started for {st.session_state.participant}")
                    time.sleep(1)
                    st.rerun()

            # Reset session button
            if st.button(
                "🔄 Reset Session",
                use_container_width=True,
                key="moderator_reset_session_main_top",
            ):
                if "participant" in st.session_state:
                    success = clear_participant_session(st.session_state.participant)
                    if success:
                        st.success("✅ Session reset successfully!")
                        time.sleep(1)
                        st.rerun()

    # ===== SUBJECT CONNECTION & ACCESS SECTION =====
    st.markdown("---")

    if not connection_status["subject_connected"]:
        with st.expander("📱 Subject Access - QR Code & Session Info", expanded=False):
            st.info(
                "⏳ Waiting for subject to join session... Share the QR code or session code below."
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
        st.success("✅ Subject device connected and active")

    # ===== ORGANIZED TABS FOR MONITORING & MANAGEMENT =====
    # Only show monitoring tabs when session is active
    if st.session_state.session_active:
        st.markdown("---")

        # Streamlined tabs - keep essential functionality organized
        main_tab1, main_tab2, main_tab3 = st.tabs(
            ["📊 Live Monitor", "📈 Analytics", "⚙️ Settings"]
        )

        with main_tab1:
            # Add refresh button at the top
            col_header, col_refresh = st.columns([4, 1])
            with col_header:
                st.markdown("### 📡 Real-time Monitoring")
            with col_refresh:
                if st.button(
                    "🔄 Refresh",
                    key="live_monitor_refresh",
                    help="Refresh monitoring data",
                    use_container_width=True,
                ):
                    st.rerun()

            # Show current participant session info
            st.info(
                "Live monitoring functionality - shows real-time participant responses"
            )

            # Get live or latest submitted response
            current_response = get_live_subject_position(st.session_state.participant)

            col1, col2 = st.columns([2, 1])

            with col1:
                if current_response:
                    interface_type = current_response.get(
                        "interface_type", INTERFACE_2D_GRID
                    )
                    method = current_response.get("method", INTERFACE_2D_GRID)
                    status_text = "🎯 Live Subject Position"
                    st.markdown(f"#### {status_text}")

                    # Initialize concentration_data for all interface types
                    concentration_data = current_response.get(
                        "ingredient_concentrations",
                        current_response.get("concentration_data", {}),
                    )

                    if (
                        interface_type == INTERFACE_SLIDERS
                        or method == INTERFACE_SLIDERS
                    ):
                        # Monitor slider interface using new database function
                        st.markdown("**🎛️ Slider Interface Monitoring**")
                        # For slider positions, we can derive from concentrations if needed
                        slider_data = concentration_data
                        is_submitted = current_response.get("is_submitted", False)

                        status_emoji = "✅" if is_submitted else "🔄"
                        status_text = (
                            "Final Submission" if is_submitted else "Live Adjustment"
                        )
                        st.markdown(f"**Status:** {status_emoji} {status_text}")

                        if concentration_data:
                            # Display concentrations and visual representation
                            st.markdown("#### 🧪 Current Ingredient Concentrations")

                            # Create visual representation of concentrations
                            for ingredient_name, conc_mM in concentration_data.items():
                                col_name, col_bar, col_value = st.columns([2, 4, 1])

                                with col_name:
                                    st.markdown(f"**{ingredient_name}**")

                                with col_bar:
                                    # Assume typical range 0-50 mM for progress bar (adjustable)
                                    max_concentration = 50.0
                                    progress_value = min(
                                        conc_mM / max_concentration, 1.0
                                    )
                                    st.progress(progress_value)

                                with col_value:
                                    st.markdown(f"**{conc_mM:.1f} mM**")
                        else:
                            st.info("🔄 Subject hasn't started adjusting sliders yet")

                            # Show what ingredients are being tested
                            num_ingredients = current_response.get("num_ingredients", 4)
                            if num_ingredients:
                                from callback import DEFAULT_INGREDIENT_CONFIG

                                ingredients = DEFAULT_INGREDIENT_CONFIG[
                                    :num_ingredients
                                ]
                                st.markdown("#### 🧪 Expected Ingredients:")
                                for ing in ingredients:
                                    st.markdown(
                                        f"• {ing['name']} ({ing['min_concentration']}-{ing['max_concentration']} {ing['unit']})"
                                    )

                    else:
                        # Monitor grid interface - show ingredient concentrations instead of coordinates
                        st.markdown("**🎯 Grid Interface Monitoring**")

                        # Show ingredient concentrations for grid interface too
                        if concentration_data:
                            st.markdown("#### 🧪 Current Ingredient Concentrations")

                            for ingredient_name, conc_mM in concentration_data.items():
                                col_name, col_value = st.columns([3, 1])

                                with col_name:
                                    st.markdown(f"**{ingredient_name}**")

                                with col_value:
                                    st.markdown(f"**{conc_mM:.1f} mM**")
                        else:
                            st.info("🔄 No grid data available yet")

                        # Legacy canvas drawing code removed since we no longer use x/y positions
                        # Grid interface now shows concentration data above instead of canvas visualization

                else:
                    st.info("🔍 No participant activity detected yet.")

            with col2:
                if current_response:
                    method = current_response.get("method", INTERFACE_2D_GRID)
                    st.markdown("#### 📊 Live Metrics")

                    if method == INTERFACE_SLIDERS:
                        # Slider-based metrics
                        current_sliders = getattr(
                            st.session_state, "current_slider_values", {}
                        )
                        if current_sliders:
                            st.metric("Interface Type", "🎛️ Multi-Slider")
                            st.metric("Ingredients", str(len(current_sliders)))

                            # Show average position
                            avg_pos = sum(current_sliders.values()) / len(
                                current_sliders
                            )
                            st.metric("Avg Position", f"{avg_pos:.1f}%")
                        else:
                            st.metric("Interface Type", "🎛️ Multi-Slider")
                            st.metric("Status", "⏳ Starting...")
                    else:
                        # Grid-based metrics - show concentration data instead of coordinates
                        if concentration_data:
                            # Show total ingredients metric
                            num_ingredients = len(concentration_data)
                            st.metric("Active Ingredients", f"{num_ingredients}")

                            # Show total concentration
                            total_conc = sum(concentration_data.values())
                            st.metric("Total Concentration", f"{total_conc:.1f} mM")
                        else:
                            st.metric("Interface Type", "🎯 Grid-based")
                            st.metric("Status", "⏳ No data yet")

                    # Show current recipe - works for both live and submitted responses
                    if st.session_state.get("participant"):
                        st.markdown("##### 🧪 Current Recipe")

                        # Get latest recipe for the participant
                        current_recipe = get_latest_recipe_for_participant(
                            st.session_state.participant
                        )

                        if current_recipe and current_recipe != "No recipe yet":
                            # Display the recipe prominently
                            st.success(current_recipe)

                            # Show individual ingredient metrics if available
                            latest_submitted = get_latest_submitted_response(
                                st.session_state.participant
                            )
                            if latest_submitted and latest_submitted.get(
                                "ingredient_concentrations"
                            ):
                                ingredients = latest_submitted[
                                    "ingredient_concentrations"
                                ]

                                # Display metrics for each ingredient
                                for (
                                    ingredient_name,
                                    concentration,
                                ) in ingredients.items():
                                    if concentration > 0:
                                        st.metric(
                                            f"🧪 {ingredient_name}",
                                            f"{concentration:.1f} mM",
                                        )
                        else:
                            # Show placeholder when no recipe is available
                            if current_response.get("is_submitted", False):
                                st.info("⏳ Calculating recipe...")
                            else:
                                st.info("👀 Waiting for participant response...")

                    # Show reaction time if available
                    if current_response.get("is_submitted", False):
                        latest_submitted = get_latest_submitted_response(
                            st.session_state.participant
                        )
                        if latest_submitted and latest_submitted.get(
                            "reaction_time_ms"
                        ):
                            st.metric(
                                "⏱️ Reaction Time",
                                f"{latest_submitted['reaction_time_ms']} ms",
                            )

                    else:
                        # For live positioning, calculate concentrations
                        st.write("here")

                    st.caption(f"Last update: {current_response['created_at']}")
                else:
                    st.write("Waiting for participant data...")

        # Auto-refresh disabled to prevent blank screen issues
        # User can manually refresh using browser or button controls
        # if st.session_state.auto_refresh:
        #     time.sleep(2)
        #     st.rerun()

        with main_tab3:
            st.markdown("### ⚙️ Session Settings")

            # Theme Settings
            st.markdown("#### 🎨 Theme & Display")

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
                "🔄 Auto-refresh monitoring (experimental)",
                value=st.session_state.get("auto_refresh", False),
                key="moderator_auto_refresh_setting",
                help="Automatically refresh live monitoring data (may cause performance issues)",
            )
            st.session_state.auto_refresh = auto_refresh

            st.divider()

            # Data Export Section
            st.markdown("#### 📊 Data Export")

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
                            label="💾 Download CSV File",
                            data=csv_data,
                            file_name=f"robotaste_session_{session_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_csv_data",
                        )
                        st.success("✅ Export data ready for download!")
                    else:
                        st.warning("⚠️ No data found to export for this session.")

                except Exception as e:
                    st.error(f"❌ Error exporting data: {e}")

            # Summary of data that will be exported
            with st.expander("ℹ️ What data gets exported?"):
                st.markdown(
                    """
                **CSV Export includes:**
                - 👤 Participant IDs and session information
                - 🎛️ Interface type (grid vs. slider) and method used
                - 🎲 Random start settings and initial positions
                - 📍 All user interactions (clicks, slider adjustments)
                - ⏱️ Reaction times and timestamps
                - 🧪 Actual concentrations (mM values) for all ingredients
                - ✅ Final response indicators
                - 📋 Questionnaire responses (if any)
                
                **Data is organized chronologically** for easy analysis in research tools like R, Python, or Excel.
                """
                )

            st.divider()

            # Debug: Check database directly
            with st.expander("🔍 Debug Database"):
                if st.button(
                    "Check Responses Table", key="moderator_check_responses_debug"
                ):
                    responses_df = get_participant_responses(
                        st.session_state.participant
                    )
                    st.write(
                        f"Found {len(responses_df)} responses for {st.session_state.participant}"
                    )
                    if not responses_df.empty:
                        st.dataframe(responses_df)
                    else:
                        st.write("No responses found in database")

                    # Also check all participants
                    all_participants = get_all_participants()
                    st.write(f"All participants in database: {all_participants}")

                # Get response history
                responses_df = get_participant_responses(
                    st.session_state.participant, limit=50
                )

    if not st.session_state.session_active:
        # Show message when session is not active
        st.info(
            "👆 Configure your experiment above and click 'Start Trial' to begin monitoring."
        )
