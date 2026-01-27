"""
Consent Phase Renderer

Displays informed consent form based on protocol configuration.
Handles consent acknowledgment and transition to next phase.

Author: AI Agent (extracted from robotaste/views/consent.py)
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any
from robotaste.data.database import save_consent_response

logger = logging.getLogger(__name__)


def render_consent(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render informed consent screen.
    
    Displays consent form from protocol configuration and handles
    subject acknowledgment. Sets st.session_state.phase_complete = True
    when consent is given.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    st.title("Informed Consent")
    
    # Get consent configuration from protocol
    consent_config = protocol.get("consent_form", {})
    
    # Extract consent form fields with defaults
    explanation = consent_config.get(
        "explanation",
        "You are invited to participate in a taste research study."
    )
    contact_info = consent_config.get(
        "contact_info",
        "For questions, please contact the research team."
    )
    medical_disclaimers = consent_config.get("medical_disclaimers", [])
    consent_label = consent_config.get(
        "consent_label",
        "I have read the information above and agree to participate in this study."
    )
    
    # Render consent form
    st.markdown("### About the Study")
    st.markdown(explanation)
    
    # Medical disclaimers (if any)
    if medical_disclaimers:
        st.markdown("### Medical Disclaimers")
        
        # Handle both string and list formats
        if isinstance(medical_disclaimers, str):
            medical_disclaimers = [medical_disclaimers]
        
        for disclaimer in medical_disclaimers:
            st.markdown(f"• {disclaimer}")
    
    # Contact information
    st.markdown("### Contact Information")
    st.markdown(contact_info)
    
    st.markdown("---")
    
    # Consent checkbox
    agreed = st.checkbox(
        consent_label,
        key=f"consent_checkbox_{session_id}"
    )
    
    # Continue button
    if st.button(
        "I Agree - Continue",
        disabled=not agreed,
        type="primary",
        use_container_width=True,
        key=f"consent_continue_{session_id}"
    ):
        # Save consent response to database
        success = save_consent_response(session_id, agreed)
        
        if success:
            logger.info(f"Session {session_id}: Consent given")
            st.session_state.phase_complete = True
            st.success("✓ Thank you! Proceeding to experiment...")
            # Don't call st.rerun() - let PhaseRouter navigation handle it
        else:
            st.error("Failed to save consent response. Please try again.")
            logger.error(f"Session {session_id}: Failed to save consent")
