"""
RoboTaste Questionnaire Components

Handles questionnaire rendering and validation.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from robotaste.config.questionnaire import get_questionnaire_config

# Setup logging
logger = logging.getLogger(__name__)


def render_questionnaire(
    questionnaire_type: str, participant_id: str, show_final_response: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Render a modular questionnaire component using the centralized questionnaire configuration.

    Args:
        questionnaire_type: Type of questionnaire (e.g., 'hedonic', 'unified_feedback')
        participant_id: Participant identifier
        show_final_response: Whether to show Final Response button instead of Continue

    Returns:
        dict: Questionnaire responses or None if not completed
    """
    # Get questionnaire configuration from centralized system
    config = get_questionnaire_config(questionnaire_type)

    if config is None:
        st.error(f"Unknown questionnaire type: {questionnaire_type}")
        return None

    # Create unique session state keys for this questionnaire instance
    # Include cycle number to ensure unique keys per cycle (prevents form overlap)
    cycle_num = st.session_state.get("current_cycle", 1)
    instance_key = f"questionnaire_{questionnaire_type}_{participant_id}_{cycle_num}"

    # Display questionnaire header
    st.markdown(f"### {config.get('name', 'Questionnaire')}")

    # Form to collect all responses
    with st.form(key=f"form_{instance_key}"):
        responses = {}

        for question in config["questions"]:
            question_id = question["id"]
            question_key = f"{instance_key}_{question_id}"
            question_type = question["type"]

            if question_type == "slider":
                # Build scale labels display if available
                scale_labels = question.get("scale_labels", {})
                help_text = question.get("help_text", "")
                display_type = question.get("display_type", "slider")

                # Get numeric parameters - support both int and float
                min_val = question["min"]
                max_val = question["max"]
                default_val = question.get("default", min_val)
                step_val = question.get("step", 1)

                # Determine if this is a float or int scale
                is_float = isinstance(step_val, float) and step_val < 1

                # Handle pillboxes display type (radio buttons)
                if display_type == "pillboxes":
                    st.markdown(f"**{question['label']}**")
                    if help_text:
                        st.caption(help_text)

                    # Show scale labels if available
                    if scale_labels:
                        label_display = " | ".join(
                            [
                                f"{val}: {label}"
                                for val, label in sorted(scale_labels.items())
                            ]
                        )
                        st.caption(label_display)

                    # Create options list (only works for integer scales)
                    options = list(range(int(min_val), int(max_val) + 1))
                    default_index = (
                        options.index(int(default_val))
                        if int(default_val) in options
                        else 0
                    )

                    responses[question_id] = st.radio(
                        label=question["label"],
                        options=options,
                        index=default_index,
                        format_func=lambda x: (
                            scale_labels.get(x, str(x)) if scale_labels else str(x)
                        ),
                        horizontal=True,
                        key=question_key,
                        label_visibility="collapsed",
                    )

                # Handle continuous slider display (float values)
                elif display_type == "slider_continuous" or is_float:
                    # Check if we should use the visual layout (columns for labels)
                    # For continuous sliders, we base visual steps on the integer range
                    num_steps = int(max_val) - int(min_val) + 1
                    use_visual_layout = bool(scale_labels) and num_steps <= 12 and num_steps > 1

                    if use_visual_layout:
                        st.markdown(f"**{question['label']}**")
                        if help_text:
                            st.caption(help_text)

                        # Create columns for labels
                        cols = st.columns(num_steps)

                        # Iterate through steps to place labels
                        current_val = int(min_val)
                        for i in range(num_steps):
                            with cols[i]:
                                # Try both int and str keys for labels
                                label = scale_labels.get(current_val) or scale_labels.get(
                                    str(current_val)
                                )
                                if label:
                                    # Use HTML to center small text
                                    st.markdown(
                                        f"<div style='text-align: center; font-size: 12px; line-height: 1.1;'>{label}</div>",
                                        unsafe_allow_html=True,
                                    )
                                else:
                                    st.write("")  # Spacer
                            current_val += 1

                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=float(min_val),
                            max_value=float(max_val),
                            value=float(default_val),
                            step=float(step_val),
                            key=question_key,
                            label_visibility="collapsed",
                            format="%.2f",  # Show 2 decimal places
                        )

                    elif scale_labels:
                        st.markdown(f"**{question['label']}**")
                        if help_text:
                            st.caption(help_text)

                        # Show key scale labels
                        label_display = " | ".join(
                            [
                                f"{val}: {label}"
                                for val, label in sorted(scale_labels.items())
                            ]
                        )
                        st.caption(label_display)

                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=float(min_val),
                            max_value=float(max_val),
                            value=float(default_val),
                            step=float(step_val),
                            key=question_key,
                            label_visibility="collapsed",
                            format="%.2f",  # Show 2 decimal places
                        )
                    else:
                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=float(min_val),
                            max_value=float(max_val),
                            value=float(default_val),
                            step=float(step_val),
                            key=question_key,
                            help=help_text if help_text else None,
                            format="%.2f",
                        )

                # Handle standard discrete slider (default behavior)
                else:
                    # Check if we should use the visual layout (columns for labels)
                    # Use visual layout if we have labels and a reasonable number of steps (<= 12)
                    step_int = int(step_val) if step_val >= 1 else 1
                    num_steps = (int(max_val) - int(min_val)) // step_int + 1
                    use_visual_layout = bool(scale_labels) and num_steps <= 12

                    if use_visual_layout:
                        st.markdown(f"**{question['label']}**")
                        if help_text:
                            st.caption(help_text)

                        # Create columns for labels
                        cols = st.columns(num_steps)

                        # Iterate through steps to place labels
                        current_val = int(min_val)
                        for i in range(num_steps):
                            with cols[i]:
                                # Try both int and str keys for labels
                                label = scale_labels.get(current_val) or scale_labels.get(
                                    str(current_val)
                                )
                                if label:
                                    # Use HTML to center small text, matching visual layout approach
                                    st.markdown(
                                        f"<div style='text-align: center; font-size: 12px; line-height: 1.1;'>{label}</div>",
                                        unsafe_allow_html=True,
                                    )
                                else:
                                    st.write("")  # Spacer
                            current_val += step_int

                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=int(min_val),
                            max_value=int(max_val),
                            value=int(default_val),
                            step=int(step_val),
                            key=question_key,
                            label_visibility="collapsed",
                            format="%d",
                        )

                    elif scale_labels:
                        st.markdown(f"**{question['label']}**")
                        if help_text:
                            st.caption(help_text)

                        # Show key scale labels
                        label_display = " | ".join(
                            [
                                f"{val}: {label}"
                                for val, label in sorted(scale_labels.items())
                            ]
                        )
                        st.caption(label_display)

                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=int(min_val),
                            max_value=int(max_val),
                            value=int(default_val),
                            step=int(step_val),
                            key=question_key,
                            label_visibility="collapsed",
                            format="%d",  # Show as integers
                        )
                    else:
                        responses[question_id] = st.slider(
                            label=question["label"],
                            min_value=int(min_val),
                            max_value=int(max_val),
                            value=int(default_val),
                            step=int(step_val),
                            key=question_key,
                            help=help_text if help_text else None,
                        )

            elif question_type == "dropdown":
                responses[question_id] = st.selectbox(
                    label=question["label"],
                    options=question["options"],
                    index=(
                        question["options"].index(
                            question.get("default", question["options"][0])
                        )
                        if question.get("default") in question["options"]
                        else 0
                    ),
                    key=question_key,
                    help=question.get("help_text", None),
                )

            elif question_type == "text_input":
                responses[question_id] = st.text_input(
                    label=question["label"],
                    value=question.get("default", ""),
                    key=question_key,
                    help=question.get("help_text", None),
                )

            elif question_type == "text_area":
                responses[question_id] = st.text_area(
                    label=question["label"],
                    value=question.get("default", ""),
                    key=question_key,
                    help=question.get("help_text", None),
                )

        # Determine button text based on context
        button_text = "Final Response" if show_final_response else "Continue"
        submitted = st.form_submit_button(
            button_text,
            type="primary",
            use_container_width=True,
            key=f"submit_{instance_key}",
        )

        if submitted:
            # Add metadata
            responses["questionnaire_type"] = questionnaire_type
            responses["participant_id"] = participant_id
            responses["timestamp"] = datetime.now().isoformat()
            responses["is_final"] = show_final_response

            return responses

    return None


def ensure_random_values_loaded(participant_id: str) -> bool:
    """
    Ensure random slider values are loaded into session state.

    Args:
        participant_id: Participant identifier

    Returns:
        True if values exist in session state, False otherwise
    """
    try:
        # Check if values already exist in session state
        existing_values = st.session_state.get("random_slider_values", {})
        if existing_values:
            return True

        # No values found
        return False

    except Exception as e:
        logger.error(f"Error ensuring random values loaded: {e}")
        return False
