"""
UI Components - Shared user interface components for RoboTaste platform

This module contains reusable UI components that are used across
different interfaces to maintain consistency and avoid circular imports.
"""

import streamlit as st


def create_header(title: str, subtitle: str = "", icon: str = "🧪"):
    """Create a beautiful, accessible header section."""

    # Theme toggle in header
    col1, col2, col3 = st.columns([1, 2, 1])
    with col3:
        # Add theme preference (stored in session state)
        if "theme_preference" not in st.session_state:
            st.session_state.theme_preference = "auto"

        theme_options = {"🌓 Auto": "auto", "☀️ Light": "light", "🌙 Dark": "dark"}

        selected_theme = st.selectbox(
            "Theme",
            options=list(theme_options.keys()),
            index=list(theme_options.values()).index(st.session_state.theme_preference),
            key="header_theme_selector",
            label_visibility="collapsed",
        )

        st.session_state.theme_preference = theme_options[selected_theme]

    # Header content
    st.markdown(
        f"""
    <div class="main-header">
        <h1>{icon} {title}</h1>
        {f"<p>{subtitle}</p>" if subtitle else ""}
    </div>
    """,
        unsafe_allow_html=True,
    )


def display_phase_status(phase: str, participant_id: str):
    """Display current phase with beautiful, accessible status card."""
    phase_info = {
        "welcome": {
            "icon": "👋",
            "title": "Welcome Phase",
            "desc": "Waiting to begin experiment",
            "class": "phase-welcome",
            "color": "var(--warning-color)",
        },
        "pre_questionnaire": {
            "icon": "📋",
            "title": "Pre-Sample Questionnaire",
            "desc": "Please complete the initial questionnaire",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "respond": {
            "icon": "🎯",
            "title": "Response Phase",
            "desc": "Experiment in progress - make your selection",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "post_response_message": {
            "icon": "🧪",
            "title": "Solution Preparation",
            "desc": "Thank you for your response - solution is being prepared",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "post_questionnaire": {
            "icon": "📋",
            "title": "Post-Response Questionnaire",
            "desc": "Please answer questions about your response",
            "class": "phase-respond",
            "color": "var(--primary-color)",
        },
        "done": {
            "icon": "✅",
            "title": "Completed",
            "desc": "Trial finished successfully",
            "class": "phase-done",
            "color": "var(--success-color)",
        },
    }

    info = phase_info.get(phase, phase_info["welcome"])

    st.markdown(
        f"""
    <div class="status-card {info['class']}">
        <h3 style="color: {info['color']};">{info['icon']} {info['title']}</h3>
        <p><strong>Participant:</strong> {participant_id}</p>
        <p style="font-size: 1.1rem; margin-top: 0.5rem;">{info['desc']}</p>
    </div>
    """,
        unsafe_allow_html=True,
    )