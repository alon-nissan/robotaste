"""
Registration Phase Renderer

Displays user registration form for collecting participant demographics.
Saves information to database and links to session.

Author: AI Agent (extracted from robotaste/views/subject.py)
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any
from robotaste.data.database import update_user_profile, update_session_user_id

logger = logging.getLogger(__name__)


def render_registration(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render user registration form.
    
    Collects participant demographics (name, age, gender) and saves to database.
    Links participant to session. Sets phase_complete when form is submitted.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    st.title("Personal Information")
    st.write("Please provide some basic information to begin.")
    
    with st.form("registration_form"):
        name = st.text_input("Name (optional)")
        age = st.number_input("Age", min_value=18, max_value=100, step=1, value=18)
        gender = st.radio(
            "Gender",
            ("Male", "Female", "Other", "Prefer not to say"),
            index=None
        )
        
        submitted = st.form_submit_button("Continue", type="primary")
        
        if submitted:
            # Validate inputs
            if age < 18 or age > 100:
                st.warning("Please enter a valid age (18-100).")
            elif gender is None or gender == "":
                st.warning("Please select your gender.")
            else:
                # Get participant ID from session state
                user_id = st.session_state.get("participant")
                
                if not user_id:
                    st.error(
                        "Session error: No participant ID found. "
                        "Please rejoin the session."
                    )
                    logger.error(
                        f"Session {session_id}: No participant ID in session state"
                    )
                elif not session_id:
                    st.error(
                        "Session error: No session ID found. "
                        "Please rejoin the session."
                    )
                    logger.error(
                        f"Registration attempt with no session_id (user {user_id})"
                    )
                elif update_user_profile(user_id, name, gender, age):
                    # Link user to session in database
                    if update_session_user_id(session_id, user_id):
                        st.success("Information saved and linked to session!")
                        st.session_state.phase_complete = True
                        logger.info(
                            f"Session {session_id}: Registration complete "
                            f"(user {user_id}, age {age}, gender {gender})"
                        )
                        # Don't call st.rerun() - let PhaseRouter handle navigation
                    else:
                        st.error(
                            "Failed to link participant to session. Please try again."
                        )
                        logger.error(
                            f"Session {session_id}: Failed to link user {user_id}"
                        )
                else:
                    st.error("Failed to save your information. Please try again.")
                    logger.error(
                        f"Session {session_id}: Failed to save user profile "
                        f"for {user_id}"
                    )
