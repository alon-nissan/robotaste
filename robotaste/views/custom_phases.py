"""
Custom Phase Renderers for RoboTaste

This module provides rendering functions for custom phases defined in protocols.
Supports text, media, break, and survey phase types with error handling.

Author: Claude Sonnet 4.5
Date: January 2026
"""

import streamlit as st
import time
import json
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


# =============================================================================
# Custom Phase Data Persistence
# =============================================================================


def save_custom_phase_data(
    session_id: str,
    phase_id: str,
    data: Dict[str, Any]
) -> bool:
    """
    Save custom phase data (survey responses, etc.) to database.

    Stores in experiment_config JSON under 'custom_phase_data' key.

    Args:
        session_id: Session ID
        phase_id: Custom phase ID
        data: Phase data to save

    Returns:
        True if saved successfully
    """
    try:
        from robotaste.data.database import get_database_connection

        with get_database_connection() as conn:
            cursor = conn.cursor()

            # Get current experiment_config
            cursor.execute(
                "SELECT experiment_config FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            if row:
                config = json.loads(row['experiment_config'] or '{}')

                # Add custom phase data
                if 'custom_phase_data' not in config:
                    config['custom_phase_data'] = {}

                config['custom_phase_data'][phase_id] = {
                    'data': data,
                    'timestamp': time.time()
                }

                # Update database
                cursor.execute(
                    "UPDATE sessions SET experiment_config = ? WHERE session_id = ?",
                    (json.dumps(config), session_id)
                )
                conn.commit()

                logger.info(
                    f"Saved custom phase data for phase '{phase_id}' "
                    f"in session {session_id}"
                )
                return True

            logger.warning(f"Session {session_id} not found")
            return False

    except Exception as e:
        logger.error(f"Failed to save custom phase data: {e}")
        return False


# =============================================================================
# Phase Renderers
# =============================================================================


def render_custom_text_phase(content: Dict[str, Any]) -> None:
    """
    Display custom text/instructions phase.

    Content structure:
    {
        "type": "text",
        "title": "Welcome!",
        "body": "Custom introduction...",
        "image_url": "https://..." (optional)
    }

    Args:
        content: Phase content dictionary
    """
    # Display title
    title = content.get("title", "")
    if title:
        st.title(title)

    # Display body text
    body = content.get("body", "")
    if body:
        st.markdown(body)

    # Display optional image
    image_url = content.get("image_url")
    if image_url:
        try:
            st.image(image_url)
        except Exception as e:
            logger.warning(f"Failed to load image: {e}")
            st.warning("Failed to load image")

    # Continue button
    st.write("")  # Spacing
    if st.button("Continue", key="custom_text_continue", type="primary"):
        st.session_state.phase_complete = True
        st.rerun()


def render_custom_media_phase(content: Dict[str, Any]) -> None:
    """
    Display image or video phase.

    Content structure:
    {
        "type": "media",
        "media_type": "image" | "video",
        "media_url": "https://...",
        "caption": "..." (optional)
    }

    Args:
        content: Phase content dictionary
    """
    media_type = content.get("media_type", "image")
    media_url = content.get("media_url")
    caption = content.get("caption")

    if not media_url:
        st.error("No media URL provided")
        return

    try:
        if media_type == "image":
            st.image(media_url, caption=caption)
        elif media_type == "video":
            st.video(media_url)
        else:
            st.error(f"Unknown media type: {media_type}")
            return
    except Exception as e:
        logger.error(f"Failed to load media: {e}")
        st.error("Failed to load media")
        return

    # Next button
    st.write("")  # Spacing
    if st.button("Next", key="custom_media_next", type="primary"):
        st.session_state.phase_complete = True
        st.rerun()


def render_break_phase(content: Dict[str, Any]) -> None:
    """
    Timed break screen with countdown.

    Content structure:
    {
        "type": "break",
        "duration_seconds": 30,
        "message": "Please wait 30 seconds..."
    }

    Args:
        content: Phase content dictionary
    """
    message = content.get("message", "Please wait...")
    duration = content.get("duration_seconds", 30)

    # Display message
    st.info(message)

    # Initialize break start time
    if 'break_start_time' not in st.session_state:
        st.session_state.break_start_time = time.time()
        logger.info(f"Started break timer for {duration} seconds")

    # Calculate elapsed and remaining time
    elapsed = time.time() - st.session_state.break_start_time
    remaining = max(0, duration - elapsed)

    # Progress bar
    progress = elapsed / duration if duration > 0 else 1.0
    st.progress(min(1.0, progress))

    # Time display
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.metric("Time Remaining", f"{int(remaining)}s")

    # Check if break is complete
    if remaining == 0:
        st.success("Break complete!")
        st.session_state.phase_complete = True

        # Clean up timer state
        if 'break_start_time' in st.session_state:
            del st.session_state.break_start_time

        logger.info("Break phase completed")
        st.rerun()
    else:
        # Sleep briefly and rerun to update timer
        time.sleep(1)
        st.rerun()


def render_custom_survey_phase(content: Dict[str, Any]) -> None:
    """
    Additional survey questions phase.

    Content structure:
    {
        "type": "survey",
        "title": "Additional Questions" (optional),
        "questions": [
            {
                "id": "q1",
                "text": "Question text...",
                "type": "slider" | "text" | "radio",
                "min": 1,  # For slider
                "max": 9,  # For slider
                "options": ["Option1", "Option2"]  # For radio
            }
        ]
    }

    Args:
        content: Phase content dictionary
    """
    # Display title
    title = content.get("title", "Additional Questions")
    st.title(title)

    questions = content.get("questions", [])

    if not questions:
        st.warning("No questions defined for this survey")
        return

    # Initialize responses in session state
    if 'custom_survey_responses' not in st.session_state:
        st.session_state.custom_survey_responses = {}

    responses = st.session_state.custom_survey_responses

    # Render each question
    for q in questions:
        q_id = q.get("id", f"q_{questions.index(q)}")
        q_text = q.get("text", "")
        q_type = q.get("type", "text")

        st.write("")  # Spacing

        if q_type == "slider":
            min_val = q.get("min", 1)
            max_val = q.get("max", 9)
            default = responses.get(q_id, (min_val + max_val) // 2)

            responses[q_id] = st.slider(
                q_text,
                min_value=min_val,
                max_value=max_val,
                value=default,
                key=f"survey_{q_id}"
            )

        elif q_type == "text":
            default = responses.get(q_id, "")
            responses[q_id] = st.text_input(
                q_text,
                value=default,
                key=f"survey_{q_id}"
            )

        elif q_type == "radio":
            options = q.get("options", ["Yes", "No"])
            default_idx = 0
            if q_id in responses and responses[q_id] in options:
                default_idx = options.index(responses[q_id])

            responses[q_id] = st.radio(
                q_text,
                options=options,
                index=default_idx,
                key=f"survey_{q_id}"
            )

        else:
            st.warning(f"Unknown question type: {q_type}")

    # Submit button
    st.write("")  # Spacing
    if st.button("Submit", key="custom_survey_submit", type="primary"):
        # Save responses to database
        session_id = st.session_state.get("session_id")
        custom_phase_id = st.session_state.get("custom_phase_id", "custom_survey")

        if session_id:
            success = save_custom_phase_data(session_id, custom_phase_id, responses)
            if success:
                logger.info(
                    f"Saved {len(responses)} survey responses for session {session_id}"
                )
            else:
                logger.error("Failed to save survey responses")

        # Mark phase as complete
        st.session_state.phase_complete = True

        # Clean up survey state
        if 'custom_survey_responses' in st.session_state:
            del st.session_state.custom_survey_responses

        st.rerun()


# =============================================================================
# Router Function
# =============================================================================


def render_custom_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """
    Route to appropriate renderer based on content type.

    Includes error handling and moderator emergency controls.

    Args:
        phase_id: Custom phase ID
        content: Phase content dictionary with 'type' field

    Raises:
        None - errors are displayed in UI
    """
    try:
        # Validate content structure
        if not isinstance(content, dict):
            raise ValueError(f"Phase content must be a dictionary, got {type(content)}")

        phase_type = content.get("type")

        if not phase_type:
            raise ValueError("Phase content missing 'type' field")

        # Route to appropriate renderer
        if phase_type == "text":
            render_custom_text_phase(content)

        elif phase_type == "media":
            render_custom_media_phase(content)

        elif phase_type == "break":
            render_break_phase(content)

        elif phase_type == "survey":
            render_custom_survey_phase(content)

        else:
            st.error(f"Unknown custom phase type: {phase_type}")
            logger.error(f"Unknown phase type '{phase_type}' for phase '{phase_id}'")

            # Provide skip button for unknown types
            if st.button("Skip This Phase", key=f"skip_{phase_id}"):
                st.session_state.phase_complete = True
                st.rerun()

    except Exception as e:
        logger.error(f"Custom phase render error for {phase_id}: {e}")
        st.error("⚠️ Phase rendering failed. Please contact the moderator.")

        # Show error details in expander
        with st.expander("Error Details"):
            st.code(str(e))
            st.json(content)

        # Emergency skip button for moderator only
        role = st.session_state.get('role', 'subject')
        if role == 'moderator':
            st.warning("**Moderator Controls**")
            if st.button("⚠️ Skip This Phase (Moderator Only)", key=f"mod_skip_{phase_id}"):
                logger.warning(
                    f"Moderator skipped failed phase '{phase_id}' in session "
                    f"{st.session_state.get('session_id')}"
                )
                st.session_state.phase_complete = True
                st.rerun()
        else:
            st.info("Please wait for the moderator to resolve this issue.")


# =============================================================================
# Helper Functions
# =============================================================================


def enter_custom_phase(phase_id: str) -> None:
    """
    Enter a custom phase, clearing completion flags.

    Args:
        phase_id: Custom phase ID (e.g., "custom_intro")
    """
    st.session_state.phase = "custom"
    st.session_state.custom_phase_id = phase_id
    st.session_state.phase_complete = False

    logger.info(f"Entered custom phase: {phase_id}")
