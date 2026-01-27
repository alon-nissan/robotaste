"""
Dynamic Experiment Page - RoboTaste

This single page renders all experiment phases based on protocol configuration.
Replaces the state-machine-based routing in main_app.py with protocol-driven
dynamic content rendering.

Navigation:
- URL: /experiment?session=ABC123&role=subject
- Phase determined by database (current_phase field)
- Content rendered by PhaseRouter

Multi-Device Support:
- Moderator polls database for subject progress
- Subjects poll for moderator phase changes
- All state synchronized via database

Author: AI Agent
Date: 2026-01-27
"""

import streamlit as st
import logging
import time
from robotaste.core.phase_router import PhaseRouter
from robotaste.data.database import get_session_protocol, get_session_phase, get_session_by_code
from robotaste.data.session_repo import sync_session_state_to_streamlit

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="RoboTaste Experiment",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed"
)


def validate_session_params() -> tuple:
    """
    Validate and extract session parameters from URL.
    
    Returns:
        Tuple of (session_id, role) or redirects to home on error
    """
    session_code = st.query_params.get("session")
    role = st.query_params.get("role")
    
    if not session_code or not role:
        st.error("⚠️ Invalid Session Link")
        st.markdown(
            "This page requires a valid session link. "
            "Please start from the home page or scan the QR code."
        )
        
        if st.button("Go to Home Page", type="primary"):
            st.switch_page("main_app.py")
        
        st.stop()
    
    # Get session_id from session_code
    session_info = get_session_by_code(session_code)
    
    if not session_info:
        st.error(f"Session not found: {session_code}")
        st.markdown("The session may have expired or been deleted.")
        
        if st.button("Return Home", type="primary"):
            st.switch_page("main_app.py")
        
        st.stop()
    
    session_id = session_info["session_id"]
    
    # Validate role
    if role not in ["moderator", "subject"]:
        st.error(f"Invalid role: {role}")
        st.stop()
    
    return session_id, role


def setup_session_state(session_id: str, role: str) -> None:
    """
    Initialize Streamlit session state with session data.
    
    Args:
        session_id: Session UUID
        role: "moderator" or "subject"
    """
    # Sync from database
    sync_session_state_to_streamlit(session_id, role)
    
    # Ensure required keys exist
    if "phase_complete" not in st.session_state:
        st.session_state.phase_complete = False


def render_logo() -> None:
    """Render Niv Lab logo in top left corner."""
    import base64
    from pathlib import Path
    
    logo_path = Path(__file__).parent.parent / "docs" / "niv_lab_logo.png"
    
    if logo_path.exists():
        logo_data = base64.b64encode(logo_path.read_bytes()).decode()
        st.markdown(
            f"""
            <div style="position: fixed !important; 
                        top: 10px !important; 
                        left: 10px !important; 
                        z-index: 9999 !important;
                        pointer-events: none !important;">
                <img src="data:image/png;base64,{logo_data}" 
                     alt="Niv Taste Lab" 
                     style="height: 50px !important; 
                            width: auto !important;
                            display: block !important;
                            opacity: 1 !important;">
            </div>
            """,
            unsafe_allow_html=True
        )


def main():
    """Main experiment page entry point."""
    # Render logo
    render_logo()
    
    # Validate session parameters
    session_id, role = validate_session_params()
    
    # Setup session state
    setup_session_state(session_id, role)
    
    # Load protocol
    protocol = get_session_protocol(session_id)
    
    if not protocol:
        st.error("Protocol not found for this session.")
        st.markdown("The session may not be fully configured yet.")
        
        if role == "subject":
            st.info("Please wait for the moderator to start the experiment.")
            time.sleep(3)
            st.rerun()
        else:
            st.warning("Please configure the experiment in the setup screen.")
            if st.button("Go to Setup"):
                st.switch_page("main_app.py")
        
        st.stop()
    
    # Get current phase from database
    current_phase = get_session_phase(session_id)
    
    if not current_phase:
        st.error("Current phase not found in database.")
        logger.error(f"No current_phase for session {session_id}")
        st.stop()
    
    # Initialize router
    try:
        router = PhaseRouter(protocol, session_id, role)
    except Exception as e:
        st.error("Failed to initialize phase router")
        logger.error(f"Router init error for session {session_id}: {e}", exc_info=True)
        st.stop()
    
    # Render current phase
    try:
        router.render_phase(current_phase)
    except Exception as e:
        st.error("An error occurred while rendering this phase.")
        logger.error(
            f"Phase render error (session={session_id}, phase={current_phase}): {e}",
            exc_info=True
        )
        
        # Emergency recovery
        with st.expander("🔧 Error Details"):
            st.code(str(e))
            
            if role == "moderator":
                if st.button("⚠️ Reset to Waiting Phase"):
                    from robotaste.data.database import update_current_phase
                    update_current_phase(session_id, "waiting")
                    st.success("Reset to waiting phase")
                    st.rerun()


if __name__ == "__main__":
    main()
