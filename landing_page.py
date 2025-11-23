from session_manager import (
    get_session_info,
    join_session,
    sync_session_state,
)

import streamlit as st
import time


def landing_page():
    """Multi-device landing page with session management."""
    # Check URL parameters for session joining
    role = st.query_params.get("role", "")
    session_code = st.query_params.get("session", "")

    if role and session_code:
        # Direct access via URL with session code
        if role == "subject":
            if join_session(session_code):
                sync_session_state(session_code, "subject")
                st.success(f"Joined session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Invalid or expired session code: {session_code}")
                st.query_params.clear()
                st.rerun()
        elif role == "moderator":
            session_info = get_session_info(session_code)
            if session_info and session_info["is_active"]:
                sync_session_state(session_code, "moderator")
                st.success(f"Resumed moderator session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Invalid or expired session code: {session_code}")
                st.query_params.clear()
                st.rerun()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        # Tab selection for different entry modes
        tab1, tab2, tab3 = st.tabs(["New Session", "Join Session", "About"])

        with tab1:
            st.markdown("### Create New Session (Moderator)")
            st.info(
                "Start a new experiment session that subjects can join using a session code or QR code."
            )

            moderator_name = st.text_input(
                "Moderator Name:",
                value="Research Team",
                help="This will be displayed to subjects",
                key="landing_moderator_name_input",
            )

            if st.button(
                "Create New Session",
                type="primary",
                width="stretch",
                key="landing_create_session_button",
            ):
                # Create minimal session in database with both UUID and 6-char code
                # Full config will be added when moderator clicks "Start Trial"
                import sql_handler as sql

                # Create session in database (returns both ID and code)
                new_session_id, new_session_code = sql.create_session(moderator_name)

                # Store both identifiers in session state for moderator interface
                st.session_state.session_id = new_session_id
                st.session_state.session_code = new_session_code
                st.session_state.device_role = "moderator"
                st.session_state.moderator_name = moderator_name
                st.session_state.session_shell_created = (
                    True  # Minimal session created (needs full config)
                )

                st.query_params.update(
                    {
                        "role": "moderator",
                        "session": new_session_code,
                    }  # Use 6-char code in URL
                )
                st.success(f"Session Code: {new_session_code}")
                st.info("Please configure your experiment settings on the next screen.")
                time.sleep(1)
                st.rerun()

        with tab2:
            st.markdown("### Join Existing Session (Subject)")
            st.info(
                "Enter the session code provided by your moderator to join an active experiment."
            )

            input_session_code = st.text_input(
                "Session Code:",
                placeholder="e.g., ABC123",
                max_chars=6,
                help="6-character code provided by the moderator",
                key="landing_session_code_input",
            ).upper()

            if st.button(
                "Join Session",
                type="primary",
                width="stretch",
                key="landing_join_session_button",
            ):
                if input_session_code and len(input_session_code) == 6:
                    if join_session(input_session_code):
                        st.session_state.session_code = input_session_code
                        st.session_state.device_role = "subject"
                        st.query_params.update(
                            {"role": "subject", "session": input_session_code}
                        )
                        st.success(f"Joined session {input_session_code}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Invalid or expired session code")
                else:
                    st.error("Please enter a valid 6-character session code")

        with tab3:
            st.markdown("### About RoboTaste")
            st.markdown(
                """
            **Multi-Device Taste Preference Experiment Platform**
            
            **Features:**
            - **2D Grid Interface**: Binary mixtures with coordinate selection
            - **Vertical Sliders**: Multi-component concentration control
            - **Multi-Device**: Moderator dashboard + subject interface
            - **Real-time Sync**: Live monitoring and data collection
            - **Cloud Ready**: Deployed on Streamlit Cloud
            
            **How to Use:**
            1. **Moderator**: Create a new session from any device
            2. **Subject**: Join using the 6-digit session code or QR code
            3. **Experiment**: Real-time synchronized taste preference testing
            
            **Device Requirements:**
            - Moderator: Desktop/laptop with large screen
            - Subject: Any device (phone, tablet, laptop)
            """
            )
