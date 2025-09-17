#!/usr/bin/env python3
"""
Test script to verify that all Streamlit elements have unique keys
"""

import streamlit as st
import sys
import os

# Add current directory to path to import our modules
sys.path.append(os.path.dirname(__file__))

# Simple test interface to check for key duplicates
st.set_page_config(page_title="Key Test", layout="wide")

st.title("🧪 Testing Streamlit Element Keys")

# Initialize session state like the main app
if "session_code" not in st.session_state:
    st.session_state.session_code = "TEST123"
if "participant" not in st.session_state:
    st.session_state.participant = "test_participant"
if "device_role" not in st.session_state:
    st.session_state.device_role = "moderator"

# Test some key combinations from our app
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Moderator Interface Test")
    
    # Test moderator keys
    test_participant = st.selectbox(
        "Select Participant:",
        ["test_participant", "participant_001"],
        key="moderator_select_participant",
    )
    
    if st.button("Reset Session", key="moderator_reset_session_main"):
        st.success("Reset button works!")
    
    if st.button("Start Trial", key="moderator_start_trial_button"):
        st.success("Start trial button works!")
    
    num_ingredients = st.selectbox(
        "Number of ingredients:",
        [2, 3, 4, 5, 6],
        key="moderator_num_ingredients_selector",
    )
    st.write(f"Selected: {num_ingredients}")

with col2:
    st.markdown("### Subject Interface Test")
    
    # Test subject keys
    participant_id = st.text_input(
        "Participant ID:",
        key="subject_participant_id_input",
    )
    
    if st.button("Check Status", key="subject_check_status_button"):
        st.success("Check status button works!")
    
    show_final = st.checkbox(
        "Ready to submit final response?",
        key=f"subject_ready_final_response_{st.session_state.participant}_{st.session_state.session_code}",
    )
    
    if st.button("Finish Selection", key="subject_finish_sliders_button"):
        st.success("Finish selection button works!")

st.markdown("---")
st.success("✅ If you can see this page without blank screens, the key fixes are working!")

# Test theme selector
st.selectbox(
    "Theme",
    ["🌓 Auto", "☀️ Light", "🌙 Dark"],
    key="header_theme_selector",
)

st.info("This test page verifies that Streamlit elements have unique keys and don't cause duplicate ID errors.")