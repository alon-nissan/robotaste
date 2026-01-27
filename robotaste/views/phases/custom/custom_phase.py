"""
Custom Phase Renderer - Protocol-defined dynamic phases

Supports rendering of protocol-defined custom phases including:
- Text/Instruction phases with optional media
- Media display phases (images, videos)
- Custom survey phases
- Timed break phases with countdown

Author: AI Agent
Date: 2026-01-27
"""

import streamlit as st
import logging
import time
from typing import Dict, Any
from datetime import datetime, timedelta
from robotaste.data.database import save_custom_phase_data

logger = logging.getLogger(__name__)


def render_custom_phase(phase_id: str, content: Dict[str, Any], session_id: str) -> None:
    """
    Main entry point for custom phase rendering.
    
    Routes to specific renderer based on content["type"].
    
    Args:
        phase_id: Custom phase identifier from protocol
        content: Phase content dictionary from protocol
        session_id: Session UUID
    
    Supported types:
        - "text": Text/instruction display with optional media
        - "media": Image or video display
        - "survey": Custom survey questions
        - "break": Timed break with countdown
    """
    if not content:
        st.error(f"No content defined for custom phase: {phase_id}")
        logger.error(f"Session {session_id}: Custom phase {phase_id} has no content")
        return
    
    phase_type = content.get("type")
    
    if not phase_type:
        st.error(f"Custom phase '{phase_id}' missing 'type' field")
        logger.error(f"Session {session_id}: Phase {phase_id} has no type specified")
        return
    
    try:
        if phase_type == "text":
            render_text_phase(phase_id, content)
        
        elif phase_type == "media":
            render_media_phase(phase_id, content)
        
        elif phase_type == "survey":
            render_survey_phase(phase_id, content, session_id)
        
        elif phase_type == "break":
            render_break_phase(phase_id, content)
        
        else:
            st.error(f"Unknown custom phase type: {phase_type}")
            logger.error(
                f"Session {session_id}: Invalid phase type '{phase_type}' "
                f"for phase '{phase_id}'"
            )
    
    except Exception as e:
        st.error(f"Error rendering custom phase: {e}")
        logger.exception(
            f"Session {session_id}: Exception in custom phase {phase_id}: {e}"
        )


def render_text_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """
    Render text/instruction phase.
    
    Displays title, text content (with markdown support), and optional image.
    Simple continue button to proceed.
    
    Args:
        phase_id: Phase identifier
        content: Phase content with keys:
            - title: str (optional)
            - text: str (required) - supports markdown
            - image_url: str (optional)
            - image_caption: str (optional)
    """
    # Display title
    title = content.get("title", "Instructions")
    st.header(title)
    
    # Display optional image
    image_url = content.get("image_url")
    if image_url:
        try:
            st.image(image_url, caption=content.get("image_caption", ""))
        except Exception as e:
            logger.warning(f"Failed to load image {image_url}: {e}")
            st.warning("⚠️ Could not load image")
    
    # Display text content (supports markdown)
    text = content.get("text")
    if not text:
        st.warning("No text content provided for this phase")
        logger.warning(f"Text phase {phase_id} missing text content")
    else:
        st.markdown(text)
    
    # Continue button
    st.markdown("---")
    if st.button("Continue", type="primary", use_container_width=True):
        st.session_state.phase_complete = True
        st.rerun()


def render_media_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """
    Render media display phase (image or video).
    
    Args:
        phase_id: Phase identifier
        content: Phase content with keys:
            - title: str (optional)
            - media_type: "image" or "video" (required)
            - media_url: str (required)
            - caption: str (optional)
    """
    title = content.get("title", "Media")
    st.header(title)
    
    media_type = content.get("media_type")
    media_url = content.get("media_url")
    
    if not media_url:
        st.error("No media URL provided")
        logger.error(f"Media phase {phase_id} missing media_url")
        return
    
    caption = content.get("caption", "")
    
    try:
        if media_type == "image":
            st.image(media_url, caption=caption, use_container_width=True)
        
        elif media_type == "video":
            st.video(media_url)
            if caption:
                st.caption(caption)
        
        else:
            st.error(f"Unknown media type: {media_type}")
            logger.error(f"Invalid media_type '{media_type}' for phase {phase_id}")
            return
    
    except Exception as e:
        st.error(f"Failed to load media: {e}")
        logger.exception(f"Media phase {phase_id} failed to load: {e}")
        return
    
    # Continue button
    st.markdown("---")
    if st.button("Continue", type="primary", use_container_width=True):
        st.session_state.phase_complete = True
        st.rerun()


def render_survey_phase(phase_id: str, content: Dict[str, Any], session_id: str) -> None:
    """
    Render custom survey phase with protocol-defined questions.
    
    Supports multiple question types and saves responses to database.
    
    Args:
        phase_id: Phase identifier
        content: Phase content with keys:
            - title: str (optional)
            - questions: List[Dict] (required) - question definitions
    
    Question types:
        - scale: Slider with min/max/step
        - text: Short text input
        - textarea: Long text input
        - choice: Single selection from options
        - multiple_choice: Multiple selections
    """
    title = content.get("title", "Survey")
    st.header(title)
    
    questions = content.get("questions", [])
    if not questions:
        st.error("No questions defined for survey phase")
        logger.error(f"Survey phase {phase_id} has no questions")
        return
    
    # Initialize response storage
    form_key = f"survey_{phase_id}"
    
    with st.form(form_key):
        responses = {}
        
        for i, question in enumerate(questions):
            q_id = question.get("id", f"q{i}")
            q_type = question.get("type", "text")
            q_label = question.get("label", f"Question {i+1}")
            q_required = question.get("required", True)
            
            # Add required indicator
            label_text = f"{q_label} {'*' if q_required else ''}"
            
            try:
                if q_type == "scale":
                    # Slider question
                    min_val = question.get("min", 1)
                    max_val = question.get("max", 10)
                    default = question.get("default", (min_val + max_val) / 2)
                    step = question.get("step", 1)
                    
                    value = st.slider(
                        label_text,
                        min_value=min_val,
                        max_value=max_val,
                        value=default,
                        step=step,
                        help=question.get("help_text")
                    )
                    responses[q_id] = value
                
                elif q_type == "text":
                    # Short text input
                    value = st.text_input(
                        label_text,
                        placeholder=question.get("placeholder", ""),
                        help=question.get("help_text")
                    )
                    if q_required and not value:
                        st.warning(f"⚠️ {q_label} is required")
                    responses[q_id] = value
                
                elif q_type == "textarea":
                    # Long text input
                    value = st.text_area(
                        label_text,
                        placeholder=question.get("placeholder", ""),
                        help=question.get("help_text")
                    )
                    if q_required and not value:
                        st.warning(f"⚠️ {q_label} is required")
                    responses[q_id] = value
                
                elif q_type == "choice":
                    # Single selection
                    options = question.get("options", [])
                    if not options:
                        st.error(f"Question '{q_label}' has no options")
                        continue
                    
                    value = st.radio(
                        label_text,
                        options=options,
                        help=question.get("help_text")
                    )
                    responses[q_id] = value
                
                elif q_type == "multiple_choice":
                    # Multiple selections
                    options = question.get("options", [])
                    if not options:
                        st.error(f"Question '{q_label}' has no options")
                        continue
                    
                    st.write(label_text)
                    selected = []
                    for option in options:
                        if st.checkbox(option, key=f"{q_id}_{option}"):
                            selected.append(option)
                    
                    if q_required and not selected:
                        st.warning(f"⚠️ {q_label} requires at least one selection")
                    responses[q_id] = selected
                
                else:
                    st.error(f"Unknown question type: {q_type}")
                    logger.error(f"Invalid question type '{q_type}' in phase {phase_id}")
            
            except Exception as e:
                st.error(f"Error rendering question '{q_label}': {e}")
                logger.exception(f"Question rendering error in phase {phase_id}: {e}")
        
        # Submit button
        submitted = st.form_submit_button(
            "Submit",
            type="primary",
            use_container_width=True
        )
        
        if submitted:
            # Validate required fields
            all_valid = True
            for question in questions:
                if question.get("required", True):
                    q_id = question.get("id", f"q{questions.index(question)}")
                    response = responses.get(q_id)
                    
                    # Check if response is empty
                    if response is None or response == "" or response == []:
                        all_valid = False
                        st.error(f"Please answer: {question.get('label', q_id)}")
            
            if all_valid:
                # Save to database
                try:
                    success = save_custom_phase_data(session_id, phase_id, responses)
                    
                    if success:
                        st.session_state.phase_complete = True
                        logger.info(
                            f"Session {session_id}: Survey {phase_id} responses saved"
                        )
                        st.rerun()
                    else:
                        st.error("Failed to save responses. Please try again.")
                        logger.error(
                            f"Session {session_id}: Failed to save survey {phase_id}"
                        )
                
                except Exception as e:
                    st.error(f"Database error: {e}")
                    logger.exception(
                        f"Session {session_id}: Exception saving survey {phase_id}: {e}"
                    )


def render_break_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """
    Render timed break phase with countdown.
    
    Displays message and progress bar that counts down.
    Auto-completes when timer expires.
    
    Args:
        phase_id: Phase identifier
        content: Phase content with keys:
            - title: str (optional)
            - message: str (optional)
            - duration_seconds: int (required)
    """
    title = content.get("title", "Break Time")
    st.header(title)
    
    message = content.get("message", "Please take a short break.")
    duration_seconds = content.get("duration_seconds")
    
    if not duration_seconds:
        st.error("Break duration not specified")
        logger.error(f"Break phase {phase_id} missing duration_seconds")
        return
    
    st.info(message)
    
    # Initialize timer start time
    timer_key = f"break_timer_start_{phase_id}"
    if timer_key not in st.session_state:
        st.session_state[timer_key] = datetime.now()
        logger.info(
            f"Break phase {phase_id}: Timer started for {duration_seconds}s"
        )
    
    start_time = st.session_state[timer_key]
    elapsed = (datetime.now() - start_time).total_seconds()
    remaining = max(0, duration_seconds - elapsed)
    
    # Display countdown
    if remaining > 0:
        st.write(f"⏱️ Time remaining: **{int(remaining)}** seconds")
        
        # Progress bar (inverted - starts full, empties)
        progress = remaining / duration_seconds
        st.progress(progress)
        
        # Auto-refresh every second
        time.sleep(1)
        st.rerun()
    
    else:
        # Timer complete
        st.success("✅ Break complete!")
        st.session_state.phase_complete = True
        
        # Clean up timer state
        if timer_key in st.session_state:
            del st.session_state[timer_key]
        
        logger.info(f"Break phase {phase_id}: Timer complete")
        
        # Add manual continue button for user to acknowledge
        if st.button("Continue", type="primary", use_container_width=True):
            st.rerun()
