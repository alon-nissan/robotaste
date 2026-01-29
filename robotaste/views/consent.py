import streamlit as st
from robotaste.core.state_machine import ExperimentPhase
from robotaste.views.phase_utils import transition_to_next_phase
from robotaste.data.database import get_session_protocol, save_consent_response

def render_consent_screen():
    """
    Renders the informed consent screen based on protocol configuration.
    """
    # Add anchor at top for scroll navigation
    st.markdown('<a name="top"></a>', unsafe_allow_html=True)
    
    # Check if consent was submitted via query param
    query_params = st.query_params
    if query_params.get("consent_submitted") == "true":
        # Clear the query param
        st.query_params.clear()
        # Save consent response
        agreed = st.session_state.get("consent_agreed", False)
        if save_consent_response(st.session_state.session_id, agreed):
            # Transition to next phase
            transition_to_next_phase(
                current_phase_str=ExperimentPhase.CONSENT.value,
                default_next_phase=ExperimentPhase.SELECTION,
                session_id=st.session_state.session_id,
            )
            st.rerun()
        else:
            st.error("Failed to save consent response. Please try again.")
    
    st.header("Informed Consent")
    
    # Get protocol configuration
    protocol = get_session_protocol(st.session_state.session_id)
    consent_config = protocol.get("consent_form", {}) if protocol else {}
    
    # Defaults
    explanation = consent_config.get("explanation", "You are invited to participate in a taste research study.")
    contact_info = consent_config.get("contact_info", "For questions, please contact the research team.")
    medical_disclaimers = consent_config.get("medical_disclaimers", [])
    consent_label = consent_config.get("consent_label", "I have read the information above and agree to participate in this study.")
    
    # 1. Explanation
    st.subheader("About the Study")
    st.markdown(explanation)
    
    # 2. Medical Disclaimers
    if medical_disclaimers:
        st.subheader("Medical Disclaimers")
        # Ensure it's a list, even if string provided
        if isinstance(medical_disclaimers, str):
            medical_disclaimers = [medical_disclaimers]
            
        for disclaimer in medical_disclaimers:
            st.markdown(f"• {disclaimer}")
            
    # 3. Contact Information
    st.subheader("Contact Information")
    st.markdown(contact_info)
    
    st.markdown("---")
    
    # 4. Consent Checkbox
    agreed = st.checkbox(consent_label)
    
    # Store agreement in session state for link button approach
    st.session_state.consent_agreed = agreed
    
    if agreed:
        # Use link button to navigate to top anchor with query param
        st.link_button(
            "Continue",
            url="?consent_submitted=true#top",
            type="primary"
        )
    else:
        st.button("Continue", disabled=True, type="primary")
