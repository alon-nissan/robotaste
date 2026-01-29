"""
RoboTaste Landing Page - Multi-Device Session Management

Handles session creation and joining for both moderators and subjects.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

from robotaste.data.session_repo import (
    get_session_info,
    join_session,
    sync_session_state_to_streamlit as sync_session_state,
    get_joinable_sessions,
)
from robotaste.data.database import create_session, get_session_by_code

import streamlit as st
import time
from datetime import datetime


def landing_page_subject():
    """
    Subject landing page - displays available sessions with smart join logic.
    
    Auto-joins if exactly one session available.
    Auto-refreshes every 5 seconds if no sessions available.
    """
    from main_app import render_logo
    render_logo()
    
    st.markdown("### Join Experiment Session")
    
    # Get available sessions
    available_sessions = get_joinable_sessions()
    
    if len(available_sessions) == 0:
        # No sessions available - show message and auto-refresh
        st.info("🔍 **No active sessions available**")
        st.markdown("Waiting for moderator to create a session...")
        
        with st.spinner("Checking for new sessions..."):
            time.sleep(5)
            st.rerun()
    
    elif len(available_sessions) == 1:
        # Exactly one session - auto-join
        session = available_sessions[0]
        session_code = session["session_code"]
        moderator_name = session["moderator_name"]
        
        st.success(f"✓ Found session by **{moderator_name}**")
        st.info(f"Session Code: **{session_code}**")
        
        with st.spinner("Joining session automatically..."):
            time.sleep(1)
            session_id = join_session(session_code)
            if session_id:
                st.session_state.session_id = session_id
                st.session_state.session_code = session_code
                st.session_state.device_role = "subject"
                st.query_params.update(
                    {"role": "subject", "session": session_code}
                )
                st.success(f"Joined session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to join session. Please try again.")
                time.sleep(2)
                st.rerun()
    
    else:
        # Multiple sessions available - show list with join buttons
        st.info(f"📋 **{len(available_sessions)} active sessions available**")
        st.markdown("Select a session to join:")
        
        for session in available_sessions:
            session_code = session["session_code"]
            moderator_name = session["moderator_name"]
            current_phase = session["current_phase"]
            created_at = session["created_at"]
            
            # Parse created_at timestamp
            try:
                created_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_ago = format_time_ago(created_dt)
            except:
                time_ago = "Recently"
            
            # Render session card
            with st.container():
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Session {session_code}**")
                    st.caption(f"Moderator: {moderator_name} • Created {time_ago} • Phase: {current_phase}")
                
                with col2:
                    if st.button(
                        "Join",
                        key=f"join_{session_code}",
                        type="primary",
                        use_container_width=True
                    ):
                        session_id = join_session(session_code)
                        if session_id:
                            st.session_state.session_id = session_id
                            st.session_state.session_code = session_code
                            st.session_state.device_role = "subject"
                            st.query_params.update(
                                {"role": "subject", "session": session_code}
                            )
                            st.success(f"Joined session {session_code}")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("Failed to join session")
                
                st.divider()


def format_time_ago(dt: datetime) -> str:
    """Format datetime as relative time (e.g., '2 minutes ago')."""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def landing_page_moderator():
    """
    Moderator landing page - session creation interface.
    
    This is the existing "New Session" tab content, extracted into a separate function.
    """
    from main_app import render_logo
    render_logo()
    
    st.markdown("### Create New Session")
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
        use_container_width=True,
        key="landing_create_session_button",
    ):
        if moderator_name:
            # Create minimal session in database with both UUID and 6-char code
            # Full config will be added when moderator clicks "Start Trial"
            new_session_id, new_session_code = create_session(moderator_name)

            # Store both identifiers in session state for moderator interface
            st.session_state.session_id = new_session_id
            st.session_state.session_code = new_session_code
            st.session_state.device_role = "moderator"
            st.session_state.moderator_name = moderator_name
            st.session_state.session_shell_created = True  # Minimal session created (needs full config)

            st.query_params.update({
                "role": "moderator",
                "session": new_session_code,
            })
            st.success(f"Session Code: {new_session_code}")
            st.info("Please configure your experiment settings on the next screen.")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Please enter your name")


def landing_page():
    """
    Multi-device landing page router with role-based navigation.
    
    Routes based on URL parameters:
    - ?role=subject (no session): Show available sessions list
    - ?role=subject&session=CODE: Direct join (existing behavior)
    - ?role=moderator (no session): Show session creation
    - ?role=moderator&session=CODE: Resume moderator session
    - No params: Default to moderator flow
    """
    # Check URL parameters for routing
    role = st.query_params.get("role", "")
    session_code = st.query_params.get("session", "")

    # Handle direct session access (existing behavior - preserved)
    if role and session_code:
        from main_app import render_logo
        render_logo()
        
        # Direct access via URL with session code
        if role == "subject":
            session_id = join_session(session_code)
            if session_id:
                sync_session_state(session_id, "subject")
                st.success(f"Joined session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Invalid or expired session code: {session_code}")
                st.query_params.clear()
                st.rerun()
        elif role == "moderator":
            session_info = get_session_by_code(session_code)
            if session_info and session_info.get("state") == "active":
                sync_session_state(session_info["session_id"], "moderator")
                st.success(f"Resumed moderator session {session_code}")
                time.sleep(1)
                st.rerun()
            else:
                st.error(f"Invalid or expired session code: {session_code}")
                st.query_params.clear()
                st.rerun()
        return
    
    # Route to role-specific landing pages
    if role == "subject":
        # Subject wants to join - show available sessions
        landing_page_subject()
    else:
        # Default to moderator flow (role == "moderator" or no role specified)
        landing_page_moderator()

