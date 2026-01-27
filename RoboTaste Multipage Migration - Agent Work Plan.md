# RoboTaste Multipage Migration - Agent Work Plan

## Project Overview
**Objective:** Migrate from state machine-based phase management to a dynamic single-page router that supports protocol-driven phase sequences while maintaining all existing functionality.

**Timeline:** 4-6 weeks  
**Approach:** Incremental migration with continuous testing  
**Risk Level:** Medium

---

## Prerequisites & Context

### Required Reading
- `docs/PROJECT_CONTEXT.md` - Architecture overview
- `AGENTS.md` - Development guidelines
- `robotaste/core/state_machine.py` - Current phase system
- `robotaste/core/phase_engine.py` - Protocol-driven sequencing
- `robotaste/views/subject.py` - Main subject interface (1,290 lines to refactor)

### Key Constraints
- ✅ Multi-device support MUST continue working (moderator + subjects)
- ✅ Database polling for phase sync MUST be preserved
- ✅ Pump control integration MUST remain functional
- ✅ Existing protocols MUST remain compatible
- ✅ No breaking changes to database schema
- ⚠️ Zero downtime requirement if deploying to active experiments

---

## Phase 1: Infrastructure Setup (Week 1)

### Task 1.1: Create New Directory Structure
**Agent: Infrastructure Setup Agent**  
**Priority:** Critical  
**Estimated Time:** 2 hours

**Objective:** Set up new file structure without breaking existing code.

**Files to Create:**
```
robotaste/views/phases/          # New directory
  ├── __init__.py
  ├── builtin/                   # Builtin phase renderers
  │   ├── __init__.py
  │   ├── consent.py
  │   ├── selection.py
  │   ├── questionnaire.py
  │   ├── loading.py
  │   ├── robot_preparing.py
  │   ├── registration.py
  │   └── completion.py
  └── custom/                    # Custom phase renderers
      ├── __init__.py
      └── custom_phase.py

robotaste/core/phase_router.py   # New router class
pages/                           # Streamlit multipage directory
  └── experiment.py              # Main experiment page
```

**Deliverables:**
- [ ] Directory structure created
- [ ] All `__init__.py` files with proper imports
- [ ] Empty stub files with docstrings
- [ ] Git commit: `feat: add multipage infrastructure skeleton`

**Testing:**
```bash
# Verify imports work
python -c "from robotaste.views.phases.builtin import consent"
python -c "from robotaste.core.phase_router import PhaseRouter"
```

**Success Criteria:**
- Existing code still runs (`streamlit run main_app.py` works)
- New imports resolve without errors
- No circular import issues

---

### Task 1.2: Create PhaseRouter Base Class
**Agent: Core Architecture Agent**  
**Priority:** Critical  
**Estimated Time:** 8 hours  
**Dependencies:** Task 1.1

**Objective:** Build the core routing logic that will replace state machine transitions.

**Implementation:**

```python
# robotaste/core/phase_router.py
"""
Phase Router - Protocol-driven phase navigation system.

This replaces the state machine's explicit transition validation with
dynamic routing based on protocol configuration.

Author: AI Agent
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any, Callable, Optional, List
from robotaste.core.phase_engine import PhaseEngine
from robotaste.data.database import (
    update_current_phase, 
    get_session_phase,
    get_current_cycle
)

logger = logging.getLogger(__name__)


class PhaseRouter:
    """
    Routes to appropriate phase renderer based on protocol configuration.
    
    Responsibilities:
    - Validate phase access (prevent URL manipulation)
    - Route to correct renderer (builtin vs custom)
    - Handle phase navigation
    - Manage phase completion state
    - Integrate with PhaseEngine for protocol-driven flow
    
    Example:
        >>> protocol = get_session_protocol(session_id)
        >>> router = PhaseRouter(protocol, session_id, "subject")
        >>> router.render_phase("consent")  # Renders consent phase
    """
    
    def __init__(self, protocol: Dict[str, Any], session_id: str, role: str):
        """
        Initialize router with protocol and session context.
        
        Args:
            protocol: Full protocol dictionary from database
            session_id: Session UUID
            role: "moderator" or "subject"
        """
        self.protocol = protocol
        self.session_id = session_id
        self.role = role
        self.engine = PhaseEngine(protocol, session_id)
        
        # Register phase renderers
        self._builtin_renderers: Dict[str, Callable] = {}
        self._register_builtin_phases()
    
    def _register_builtin_phases(self) -> None:
        """Register all builtin phase renderer functions."""
        # TODO: Import will be added in Task 1.3
        pass
    
    def render_phase(self, phase_id: str) -> None:
        """
        Main entry point: render the specified phase.
        
        Args:
            phase_id: Phase identifier from protocol (e.g., "consent", "selection")
        """
        # Step 1: Validate access
        if not self._validate_phase_access(phase_id):
            return  # _validate_phase_access handles error UI
        
        # Step 2: Get phase definition
        phase_def = self._get_phase_definition(phase_id)
        
        if not phase_def:
            self._render_unknown_phase_error(phase_id)
            return
        
        # Step 3: Route based on phase type
        if phase_def.phase_type == "builtin":
            self._render_builtin_phase(phase_id)
        
        elif phase_def.phase_type == "custom":
            self._render_custom_phase(phase_id, phase_def.content)
        
        elif phase_def.phase_type == "loop":
            self._handle_loop_entry(phase_id)
        
        else:
            st.error(f"Unknown phase type: {phase_def.phase_type}")
            logger.error(
                f"Invalid phase type '{phase_def.phase_type}' for "
                f"phase '{phase_id}' in session {self.session_id}"
            )
    
    def _validate_phase_access(self, requested_phase: str) -> bool:
        """
        Validate that user can access requested phase.
        
        Prevents URL manipulation (e.g., subject typing /complete to skip ahead).
        
        Args:
            requested_phase: Phase ID from URL or render call
        
        Returns:
            True if access is valid, False otherwise (displays error UI)
        """
        # Get actual current phase from database (source of truth)
        actual_phase = get_session_phase(self.session_id)
        
        if actual_phase is None:
            st.error("Session not found. Please return to home page.")
            if st.button("Return Home", type="primary"):
                st.switch_page("main_app.py")
            return False
        
        if actual_phase != requested_phase:
            st.warning(
                f"⚠️ Phase Mismatch Detected\n\n"
                f"You're trying to access **{requested_phase}** but the "
                f"experiment is currently at **{actual_phase}**."
            )
            
            st.info(
                "This can happen if:\n"
                "- Another device (moderator) changed the phase\n"
                "- Your browser is out of sync\n"
                "- You used the back button"
            )
            
            # Auto-redirect button
            if st.button("Go to Current Phase", type="primary"):
                logger.info(
                    f"Session {self.session_id}: Redirecting from "
                    f"{requested_phase} to {actual_phase}"
                )
                st.rerun()
            
            return False
        
        return True
    
    def _get_phase_definition(self, phase_id: str):
        """
        Get phase definition from PhaseEngine.
        
        Args:
            phase_id: Phase identifier
        
        Returns:
            PhaseDefinition object or None if not found
        """
        phase_idx = self.engine._find_phase_index(phase_id)
        if phase_idx == -1:
            return None
        return self.engine.phase_sequence[phase_idx]
    
    def _render_builtin_phase(self, phase_id: str) -> None:
        """Render a builtin phase using registered renderer."""
        renderer = self._builtin_renderers.get(phase_id)
        
        if not renderer:
            st.error(f"No renderer found for builtin phase: {phase_id}")
            logger.error(
                f"Missing renderer for builtin phase '{phase_id}' "
                f"in session {self.session_id}"
            )
            return
        
        # Call phase-specific renderer
        # Renderers are responsible for setting st.session_state.phase_complete
        renderer(self.session_id, self.protocol)
        
        # Add navigation controls
        self._render_phase_navigation(phase_id)
    
    def _render_custom_phase(self, phase_id: str, content: Dict[str, Any]) -> None:
        """Render a custom phase from protocol configuration."""
        # TODO: Will be implemented in Task 2.3
        st.info(f"Custom phase rendering coming soon: {phase_id}")
        st.session_state.phase_complete = True
    
    def _handle_loop_entry(self, loop_phase_id: str) -> None:
        """
        Handle entering experiment loop.
        
        The loop is a meta-phase that redirects to the first actual loop phase
        (typically "selection").
        """
        # Determine first phase in loop
        first_loop_phase = "selection"  # Default from current system
        
        logger.info(
            f"Session {self.session_id}: Entering loop, redirecting to "
            f"{first_loop_phase}"
        )
        
        # Update database and trigger rerun
        update_current_phase(self.session_id, first_loop_phase)
        st.rerun()
    
    def _render_phase_navigation(self, current_phase: str) -> None:
        """
        Render navigation controls at bottom of phase.
        
        Handles:
        - Auto-advance (if configured in protocol)
        - Manual continue button
        - Disabled state while phase incomplete
        
        Args:
            current_phase: Current phase ID
        """
        st.markdown("---")
        
        # Check if phase is complete (set by phase renderer)
        phase_complete = st.session_state.get("phase_complete", False)
        
        # Check for auto-advance configuration
        should_auto, duration_ms = self.engine.should_auto_advance(current_phase)
        
        if should_auto and phase_complete:
            # Auto-advance with countdown
            st.info(f"⏱️ Advancing in {duration_ms/1000:.0f} seconds...")
            
            import time
            time.sleep(duration_ms / 1000)
            
            self._advance_to_next_phase(current_phase)
            st.rerun()
        
        elif phase_complete:
            # Manual continue button
            if st.button("Continue →", type="primary", use_container_width=True):
                self._advance_to_next_phase(current_phase)
                st.rerun()
        
        else:
            # Phase not complete - show disabled button
            st.button(
                "Complete the current step to continue", 
                disabled=True,
                use_container_width=True,
                help="Finish the current phase to proceed"
            )
    
    def _advance_to_next_phase(self, current_phase: str) -> None:
        """
        Advance to next phase using PhaseEngine.
        
        Args:
            current_phase: Current phase ID
        """
        # Get current cycle for loop logic
        current_cycle = get_current_cycle(self.session_id)
        
        # Use PhaseEngine to determine next phase
        next_phase = self.engine.get_next_phase(
            current_phase,
            current_cycle=current_cycle
        )
        
        logger.info(
            f"Session {self.session_id}: Phase transition "
            f"{current_phase} → {next_phase} (cycle {current_cycle})"
        )
        
        # Update database (source of truth for multi-device sync)
        update_current_phase(self.session_id, next_phase)
        
        # Clear phase completion flag for next phase
        st.session_state.phase_complete = False
        
        # Log transition for debugging
        from robotaste.core.state_machine import create_phase_transition_log
        from robotaste.core.state_machine import ExperimentPhase
        
        try:
            current_enum = ExperimentPhase(current_phase)
            next_enum = ExperimentPhase(next_phase)
            log_entry = create_phase_transition_log(
                current_enum,
                next_enum,
                session_id=self.session_id
            )
            logger.info(f"Phase transition logged: {log_entry}")
        except ValueError:
            # Custom phases won't be in enum - that's okay
            logger.debug(f"Custom phase transition: {current_phase} → {next_phase}")
    
    def _render_unknown_phase_error(self, phase_id: str) -> None:
        """Display error UI for unknown phase."""
        st.error(f"Unknown phase: **{phase_id}**")
        
        st.markdown(
            "This phase is not defined in the protocol. "
            "Please contact the moderator."
        )
        
        # Emergency recovery options
        with st.expander("🔧 Troubleshooting"):
            st.markdown(
                "**For Moderators:**\n"
                "- Check protocol configuration\n"
                "- Verify phase sequence is complete\n"
                "- Try ending and restarting session"
            )
            
            if self.role == "moderator":
                if st.button("⚠️ Force to Waiting Phase"):
                    update_current_phase(self.session_id, "waiting")
                    st.success("Reset to waiting phase")
                    st.rerun()
        
        logger.error(
            f"Unknown phase '{phase_id}' requested for session {self.session_id}"
        )
```

**Deliverables:**
- [ ] `phase_router.py` file created with full implementation
- [ ] Comprehensive docstrings on all methods
- [ ] Error handling for edge cases
- [ ] Logging statements for debugging
- [ ] Git commit: `feat: implement PhaseRouter core class`

**Testing:**
Create `tests/test_phase_router.py`:
```python
import pytest
from robotaste.core.phase_router import PhaseRouter
from robotaste.core.phase_engine import PhaseEngine

def test_router_initialization():
    """Test router initializes with protocol."""
    protocol = {
        "phase_sequence": {
            "phases": [
                {"phase_id": "consent", "phase_type": "builtin"}
            ]
        }
    }
    router = PhaseRouter(protocol, "test-session", "subject")
    assert router.session_id == "test-session"
    assert router.role == "subject"
    assert isinstance(router.engine, PhaseEngine)

def test_phase_access_validation(mock_db):
    """Test phase access validation prevents skipping."""
    # TODO: Implement mock database
    pass

# Add more tests...
```

**Success Criteria:**
- [ ] All methods have docstrings
- [ ] Error cases handled gracefully
- [ ] Logging statements present
- [ ] Code passes linting (`ruff check robotaste/core/phase_router.py`)

---

### Task 1.3: Create Experiment Page Entry Point
**Agent: UI Integration Agent**  
**Priority:** Critical  
**Estimated Time:** 4 hours  
**Dependencies:** Task 1.2

**Objective:** Create the single dynamic page that will host all experiment phases.

**Implementation:**

```python
# pages/experiment.py
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
from robotaste.data.database import get_session_protocol, get_session_phase
from robotaste.data.session_repo import sync_session_state_to_streamlit

logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="RoboTaste Experiment",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="collapsed"
)


def validate_session_params() -> tuple[str, str]:
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
    from robotaste.data.database import get_session_by_code
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
```

**Deliverables:**
- [ ] `pages/experiment.py` file created
- [ ] Error handling for all edge cases
- [ ] Session validation logic
- [ ] Emergency recovery options for moderators
- [ ] Git commit: `feat: create dynamic experiment page`

**Testing:**
```bash
# Test page loads
streamlit run pages/experiment.py -- ?session=TEST123&role=subject

# Should show error since TEST123 doesn't exist
# Verify error handling works gracefully
```

**Success Criteria:**
- [ ] Page loads without errors (even with invalid params)
- [ ] Redirects to home page on invalid session
- [ ] Handles missing protocol gracefully
- [ ] Logo renders correctly

---

## Phase 2: Extract Builtin Phases (Week 2-3)

### Task 2.1: Extract Consent Phase
**Agent: Phase Extraction Agent #1**  
**Priority:** High  
**Estimated Time:** 4 hours  
**Dependencies:** Task 1.3

**Objective:** Move consent screen logic from `subject.py` to modular renderer.

**Current Code Location:**
`robotaste/views/consent.py` (lines 1-56)

**Implementation:**

```python
# robotaste/views/phases/builtin/consent.py
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
        use_container_width=True
    ):
        # Save consent response to database
        success = save_consent_response(session_id, agreed)
        
        if success:
            logger.info(f"Session {session_id}: Consent given")
            st.session_state.phase_complete = True
            st.success("Thank you! Proceeding to experiment...")
            # Don't call st.rerun() - let PhaseRouter navigation handle it
        else:
            st.error("Failed to save consent response. Please try again.")
            logger.error(f"Session {session_id}: Failed to save consent")
```

**Deliverables:**
- [ ] `consent.py` created in `robotaste/views/phases/builtin/`
- [ ] Original code in `robotaste/views/consent.py` marked as deprecated
- [ ] Register renderer in PhaseRouter (update Task 1.2 code)
- [ ] Git commit: `feat: extract consent phase to modular renderer`

**Router Integration:**
Update `phase_router.py`:
```python
def _register_builtin_phases(self) -> None:
    """Register all builtin phase renderer functions."""
    from robotaste.views.phases.builtin.consent import render_consent
    
    self._builtin_renderers = {
        "consent": render_consent,
        # More will be added in subsequent tasks
    }
```

**Testing:**
```python
# tests/test_phases/test_consent.py
def test_consent_phase_renders(mock_session):
    """Test consent phase displays correctly."""
    protocol = {
        "consent_form": {
            "explanation": "Test study explanation",
            "consent_label": "I agree to test"
        }
    }
    
    # Mock Streamlit context
    with patch('streamlit.title') as mock_title:
        render_consent("test-session", protocol)
        mock_title.assert_called_once_with("Informed Consent")
```

**Success Criteria:**
- [ ] Consent phase renders in experiment page
- [ ] Checkbox and button work correctly
- [ ] `st.session_state.phase_complete` is set on submission
- [ ] Database save is called with correct parameters
- [ ] No `st.rerun()` calls in renderer (navigation handles it)

---

### Task 2.2: Extract Selection Phase
**Agent: Phase Extraction Agent #2**  
**Priority:** High  
**Estimated Time:** 8 hours  
**Dependencies:** Task 2.1

**Objective:** Extract selection interface (2D grid / 1D slider) to modular renderer.

**Current Code Location:**
`robotaste/views/subject.py` - `grid_interface()` and `single_variable_interface()` functions

**Implementation:**

```python
# robotaste/views/phases/builtin/selection.py
"""
Selection Phase Renderer

Displays sample selection interface (2D grid for binary mixtures,
1D slider for single ingredients). Handles user selections and
predetermined/BO samples.

Author: AI Agent (extracted from robotaste/views/subject.py)
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any
from robotaste.core.trials import prepare_cycle_sample
from robotaste.data.database import get_current_cycle

logger = logging.getLogger(__name__)


def render_selection(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render sample selection interface.
    
    Determines selection mode (user/BO/predetermined) and displays
    appropriate interface (2D grid or 1D slider).
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    st.title("Select Your Sample")
    
    # Get current cycle
    current_cycle = get_current_cycle(session_id)
    
    # Prepare cycle sample (determines mode and concentrations)
    cycle_info = prepare_cycle_sample(session_id, current_cycle)
    
    # Display cycle information
    max_cycles = protocol.get("stopping_criteria", {}).get("max_cycles", "?")
    st.markdown(
        f"### Cycle {current_cycle} of {max_cycles}",
        unsafe_allow_html=True
    )
    
    # Check selection mode
    mode = cycle_info.get("mode", "user_selected")
    
    if mode in ["predetermined", "bo_selected"]:
        # Auto-selected sample - no user interaction needed
        _render_auto_selected_sample(session_id, cycle_info, mode)
    else:
        # User selection required
        _render_user_selection_interface(session_id, protocol, cycle_info)


def _render_auto_selected_sample(
    session_id: str,
    cycle_info: Dict[str, Any],
    mode: str
) -> None:
    """Render UI for predetermined or BO-selected samples."""
    
    mode_labels = {
        "predetermined": "📋 Predetermined Sample",
        "bo_selected": "🤖 AI-Optimized Sample"
    }
    
    st.success(mode_labels.get(mode, "Sample Ready"))
    
    st.info(
        "The sample for this cycle has been prepared. "
        "Please proceed to taste it."
    )
    
    # Store sample in session state for database save
    st.session_state.current_tasted_sample = cycle_info["concentrations"].copy()
    st.session_state.next_selection_data = {
        "mode": mode,
        "timestamp": datetime.now().isoformat()
    }
    
    # Mark phase complete
    st.session_state.phase_complete = True
    
    logger.info(
        f"Session {session_id} cycle {cycle_info['cycle']}: "
        f"Auto-selected sample ({mode})"
    )


def _render_user_selection_interface(
    session_id: str,
    protocol: Dict[str, Any],
    cycle_info: Dict[str, Any]
) -> None:
    """Render appropriate selection UI based on number of ingredients."""
    
    num_ingredients = len(protocol.get("ingredients", []))
    
    if num_ingredients == 2:
        _render_2d_grid_interface(session_id, protocol, cycle_info)
    elif num_ingredients == 1:
        _render_1d_slider_interface(session_id, protocol, cycle_info)
    else:
        st.error(
            f"Unsupported number of ingredients: {num_ingredients}. "
            f"Only 1 or 2 ingredients are currently supported."
        )
        logger.error(
            f"Session {session_id}: Invalid ingredient count {num_ingredients}"
        )


def _render_2d_grid_interface(
    session_id: str,
    protocol: Dict[str, Any],
    cycle_info: Dict[str, Any]
) -> None:
    """Render 2D grid for binary mixture selection."""
    
    # Import grid component
    from robotaste.components.grid import render_ingredient_grid
    
    ingredients = protocol["ingredients"]
    
    st.markdown("### Select Your Next Sample")
    st.caption(
        "Click on the grid below to choose the concentrations "
        "for your next sample."
    )
    
    # Render grid
    selection = render_ingredient_grid(
        ingredients=ingredients,
        session_id=session_id,
        cycle_info=cycle_info
    )
    
    # Check if selection was made
    if selection:
        # Store in session state
        st.session_state.current_tasted_sample = selection["concentrations"]
        st.session_state.next_selection_data = {
            "mode": "user_selected",
            "grid_position": selection.get("position"),
            "timestamp": datetime.now().isoformat()
        }
        
        # Mark complete
        st.session_state.phase_complete = True
        
        logger.info(
            f"Session {session_id}: User selected sample "
            f"{selection['concentrations']}"
        )


def _render_1d_slider_interface(
    session_id: str,
    protocol: Dict[str, Any],
    cycle_info: Dict[str, Any]
) -> None:
    """Render 1D slider for single ingredient selection."""
    
    from robotaste.components.slider import render_concentration_slider
    
    ingredient = protocol["ingredients"][0]
    
    st.markdown(f"### Select {ingredient['name']} Concentration")
    
    # Render slider
    concentration = render_concentration_slider(
        ingredient=ingredient,
        session_id=session_id,
        cycle_info=cycle_info
    )
    
    if st.button("Confirm Selection", type="primary"):
        # Store selection
        st.session_state.current_tasted_sample = {
            ingredient["name"]: concentration
        }
        st.session_state.next_selection_data = {
            "mode": "user_selected",
            "concentration": concentration,
            "timestamp": datetime.now().isoformat()
        }
        
        # Mark complete
        st.session_state.phase_complete = True
        
        logger.info(
            f"Session {session_id}: User selected concentration "
            f"{concentration} mM"
        )
```

**CRITICAL NOTE:** This task requires careful extraction of the grid and slider logic. The current `grid_interface()` function in `subject.py` is ~200 lines. Consider breaking into sub-tasks if needed.

**Deliverables:**
- [ ] `selection.py` created with full grid/slider logic
- [ ] Components `render_ingredient_grid()` and `render_concentration_slider()` tested
- [ ] Auto-selection mode works (predetermined/BO)
- [ ] User selection mode works (grid and slider)
- [ ] Register in PhaseRouter
- [ ] Git commit: `feat: extract selection phase with grid and slider interfaces`

**Testing:**
```python
def test_selection_auto_mode(mock_session):
    """Test selection phase with predetermined sample."""
    protocol = {
        "ingredients": [{"name": "Sugar", "min": 0, "max": 100}],
        "stopping_criteria": {"max_cycles": 10}
    }
    
    # Mock prepare_cycle_sample to return predetermined mode
    with patch('robotaste.core.trials.prepare_cycle_sample') as mock_prep:
        mock_prep.return_value = {
            "cycle": 1,
            "mode": "predetermined",
            "concentrations": {"Sugar": 50.0}
        }
        
        render_selection("test-session", protocol)
        
        # Should set phase_complete automatically
        assert st.session_state.phase_complete == True
```

**Success Criteria:**
- [ ] Both grid (2D) and slider (1D) interfaces work
- [ ] Auto-selection (BO/predetermined) completes automatically
- [ ] User selections saved to session state
- [ ] No crashes with different ingredient configurations
- [ ] Selection data includes all required fields

---

### Task 2.3: Extract Questionnaire Phase
**Agent: Phase Extraction Agent #3**  
**Priority:** High  
**Estimated Time:** 6 hours  
**Dependencies:** Task 2.2

**Objective:** Extract questionnaire rendering logic to modular renderer.

**Current Code Location:**
`robotaste/views/questionnaire.py` - main rendering functions

**Implementation:**

```python
# robotaste/views/phases/builtin/questionnaire.py
"""
Questionnaire Phase Renderer

Displays rating questionnaire based on protocol configuration.
Supports multiple questionnaire types (hedonic, intensity, liking+intensity).

Author: AI Agent (extracted from robotaste/views/questionnaire.py)
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from robotaste.data.database import (
    save_questionnaire_responses,
    increment_cycle,
    get_current_cycle
)

logger = logging.getLogger(__name__)


def render_questionnaire(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render questionnaire based on protocol configuration.
    
    Displays appropriate questions for the selected questionnaire type
    and handles response submission.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    st.title("Rate Your Sample")
    
    # Get questionnaire type from protocol
    q_type = protocol.get("questionnaire_type", "liking_intensity")
    
    st.markdown(
        "Please answer the following questions about the sample you just tasted."
    )
    
    # Render appropriate questionnaire
    if q_type == "hedonic":
        responses = _render_hedonic_questionnaire()
    elif q_type == "intensity":
        responses = _render_intensity_questionnaire()
    elif q_type == "liking_intensity":
        responses = _render_liking_intensity_questionnaire()
    else:
        st.error(f"Unknown questionnaire type: {q_type}")
        logger.error(f"Session {session_id}: Invalid questionnaire type {q_type}")
        responses = _render_liking_intensity_questionnaire()  # Fallback
    
    # Submit button
    if st.button("Submit Responses", type="primary", use_container_width=True):
        # Validate responses
        if not _validate_responses(responses):
            st.error("Please answer all questions before submitting.")
            return
        
        # Add metadata
        responses["questionnaire_type"] = q_type
        responses["timestamp"] = datetime.now().isoformat()
        responses["cycle"] = get_current_cycle(session_id)
        
        # Save to database
        success = save_questionnaire_responses(session_id, responses)
        
        if success:
            # Increment cycle count
            increment_cycle(session_id)
            
            # Mark phase complete
            st.session_state.phase_complete = True
            
            logger.info(
                f"Session {session_id} cycle {responses['cycle']}: "
                f"Questionnaire responses saved"
            )
            
            st.success("✓ Responses saved!")
        else:
            st.error("Failed to save responses. Please try again.")
            logger.error(
                f"Session {session_id}: Failed to save questionnaire responses"
            )


def _render_hedonic_questionnaire() -> Dict[str, Any]:
    """Render hedonic scale questionnaire."""
    responses = {}
    
    st.markdown("### How much did you like this sample?")
    
    responses["hedonic_rating"] = st.select_slider(
        "Liking",
        options=[
            1, 2, 3, 4, 5, 6, 7, 8, 9
        ],
        format_func=lambda x: _get_hedonic_label(x),
        key="hedonic_slider"
    )
    
    return responses


def _render_intensity_questionnaire() -> Dict[str, Any]:
    """Render intensity rating questionnaire."""
    responses = {}
    
    st.markdown("### Rate the intensity of each taste:")
    
    responses["sweetness_intensity"] = st.slider(
        "Sweetness",
        min_value=0,
        max_value=10,
        value=5,
        key="sweetness_slider"
    )
    
    responses["saltiness_intensity"] = st.slider(
        "Saltiness",
        min_value=0,
        max_value=10,
        value=5,
        key="saltiness_slider"
    )
    
    return responses


def _render_liking_intensity_questionnaire() -> Dict[str, Any]:
    """Render combined liking + intensity questionnaire."""
    responses = {}
    
    # Liking section
    st.markdown("### How much did you like this sample?")
    
    responses["hedonic_rating"] = st.select_slider(
        "Overall Liking",
        options=[1, 2, 3, 4, 5, 6, 7, 8, 9],
        format_func=lambda x: _get_hedonic_label(x),
        key="hedonic_slider"
    )
    
    st.markdown("---")
    
    # Intensity section
    st.markdown("### Rate the intensity of each taste:")
    
    col1, col2 = st.columns(2)
    
    with col1:
        responses["sweetness_intensity"] = st.slider(
            "Sweetness",
            min_value=0,
            max_value=10,
            value=5,
            key="sweetness_slider",
            help="0 = Not sweet at all, 10 = Extremely sweet"
        )
    
    with col2:
        responses["saltiness_intensity"] = st.slider(
            "Saltiness",
            min_value=0,
            max_value=10,
            value=5,
            key="saltiness_slider",
            help="0 = Not salty at all, 10 = Extremely salty"
        )
    
    return responses


def _get_hedonic_label(value: int) -> str:
    """Get hedonic scale label for value."""
    labels = {
        1: "1 - Dislike Extremely",
        2: "2 - Dislike Very Much",
        3: "3 - Dislike Moderately",
        4: "4 - Dislike Slightly",
        5: "5 - Neither Like nor Dislike",
        6: "6 - Like Slightly",
        7: "7 - Like Moderately",
        8: "8 - Like Very Much",
        9: "9 - Like Extremely"
    }
    return labels.get(value, str(value))


def _validate_responses(responses: Dict[str, Any]) -> bool:
    """
    Validate that all required questions were answered.
    
    Args:
        responses: Response dictionary
    
    Returns:
        True if all required fields present
    """
    if not responses:
        return False
    
    # Check for at least one rating
    rating_keys = ["hedonic_rating", "sweetness_intensity", "saltiness_intensity"]
    
    return any(key in responses for key in rating_keys)
```

**Deliverables:**
- [ ] `questionnaire.py` created with all questionnaire types
- [ ] Response validation logic
- [ ] Cycle increment after successful submission
- [ ] Register in PhaseRouter
- [ ] Git commit: `feat: extract questionnaire phase with all types`

**Testing:**
```python
def test_questionnaire_submission(mock_db):
    """Test questionnaire saves responses correctly."""
    protocol = {"questionnaire_type": "liking_intensity"}
    
    # Render questionnaire
    render_questionnaire("test-session", protocol)
    
    # Simulate user input
    st.session_state["hedonic_slider"] = 7
    st.session_state["sweetness_slider"] = 6
    st.session_state["saltiness_slider"] = 4
    
    # Submit
    # ... verify save_questionnaire_responses called with correct data
```

**Success Criteria:**
- [ ] All questionnaire types render correctly
- [ ] Responses saved to database with correct format
- [ ] Cycle incremented after successful submission
- [ ] Validation prevents incomplete submissions
- [ ] `phase_complete` flag set on success

---

### Task 2.4-2.7: Extract Remaining Builtin Phases
**Agents: Phase Extraction Agents #4-7**  
**Priority:** Medium  
**Estimated Time:** 2-4 hours each

Extract these phases following the same pattern:

- **2.4: Loading Phase** (`robotaste/views/subject.py` - loading screen logic)
- **2.5: Robot Preparing Phase** (pump control waiting screen)
- **2.6: Registration Phase** (`robotaste/views/subject.py` - registration form)
- **2.7: Completion Phase** (`robotaste/views/completion.py`)

Each follows the same template:
```python
def render_PHASE_NAME(session_id: str, protocol: Dict[str, Any]) -> None:
    """Render PHASE_NAME phase."""
    # 1. Display UI
    # 2. Handle user interaction
    # 3. Set st.session_state.phase_complete = True when done
    # 4. NO st.rerun() calls
```

---

## Phase 3: Custom Phase Support (Week 3-4)

### Task 3.1: Implement Custom Phase Router
**Agent: Custom Phase Agent**  
**Priority:** Medium  
**Estimated Time:** 8 hours  
**Dependencies:** Tasks 2.1-2.7

**Objective:** Enable dynamic rendering of custom phases from protocol JSON.

**Implementation:**

```python
# robotaste/views/phases/custom/custom_phase.py
"""
Custom Phase Renderer

Dynamically renders custom phases based on protocol configuration.
Supports: text, media (image/video), survey, break/timer phases.

Author: AI Agent
Date: 2026-01-27
"""

import streamlit as st
import logging
import time
from typing import Dict, Any
from datetime import datetime
from robotaste.data.database import save_custom_phase_data

logger = logging.getLogger(__name__)


def render_custom_phase(phase_id: str, content: Dict[str, Any], session_id: str) -> None:
    """
    Route to appropriate custom phase renderer based on content type.
    
    Args:
        phase_id: Custom phase identifier from protocol
        content: Phase content dictionary with 'type' field
        session_id: Session UUID
    """
    content_type = content.get("type")
    
    if not content_type:
        st.error(f"Custom phase '{phase_id}' missing 'type' field")
        logger.error(f"Custom phase {phase_id} has no type in session {session_id}")
        st.session_state.phase_complete = True  # Allow skip
        return
    
    # Route to appropriate renderer
    if content_type == "text":
        render_text_phase(phase_id, content)
    
    elif content_type == "media":
        render_media_phase(phase_id, content)
    
    elif content_type == "survey":
        render_survey_phase(phase_id, content, session_id)
    
    elif content_type == "break":
        render_break_phase(phase_id, content)
    
    else:
        st.error(f"Unknown custom phase type: {content_type}")
        logger.error(
            f"Unknown custom phase type '{content_type}' for "
            f"phase {phase_id} in session {session_id}"
        )
        st.session_state.phase_complete = True  # Allow skip


def render_text_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """Render text/instructions phase."""
    
    title = content.get("title", phase_id.replace("_", " ").title())
    text = content.get("text", "")
    button_label = content.get("button_label", "Continue")
    
    st.title(title)
    
    # Render text (supports markdown)
    st.markdown(text)
    
    # Optional image
    if "image_url" in content:
        try:
            st.image(content["image_url"])
        except Exception as e:
            logger.warning(f"Failed to load image: {e}")
    
    # Continue button
    if st.button(button_label, type="primary", use_container_width=True):
        st.session_state.phase_complete = True


def render_media_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """Render image or video phase."""
    
    title = content.get("title", "Media")
    media_type = content.get("media_type", "image")
    media_url = content.get("media_url")
    caption = content.get("caption")
    
    st.title(title)
    
    if not media_url:
        st.error("No media URL provided")
        st.session_state.phase_complete = True
        return
    
    try:
        if media_type == "image":
            st.image(media_url, caption=caption)
        elif media_type == "video":
            st.video(media_url)
        else:
            st.error(f"Unknown media type: {media_type}")
            st.session_state.phase_complete = True
            return
    except Exception as e:
        logger.error(f"Failed to load media: {e}")
        st.error("Failed to load media content")
    
    # Next button
    if st.button("Next", type="primary", use_container_width=True):
        st.session_state.phase_complete = True


def render_survey_phase(
    phase_id: str,
    content: Dict[str, Any],
    session_id: str
) -> None:
    """Render custom survey questions."""
    
    title = content.get("title", "Additional Questions")
    questions = content.get("questions", [])
    
    st.title(title)
    
    if not questions:
        st.warning("No questions defined for this survey.")
        st.session_state.phase_complete = True
        return
    
    # Render each question
    responses = {}
    
    for i, question in enumerate(questions):
        q_type = question.get("type", "text")
        q_text = question.get("text", f"Question {i+1}")
        q_id = question.get("id", f"q{i}")
        
        if q_type == "scale":
            responses[q_id] = st.slider(
                q_text,
                min_value=question.get("min", 0),
                max_value=question.get("max", 10),
                value=question.get("default", 5),
                key=f"custom_survey_{phase_id}_{q_id}"
            )
        
        elif q_type == "text":
            responses[q_id] = st.text_input(
                q_text,
                key=f"custom_survey_{phase_id}_{q_id}"
            )
        
        elif q_type == "textarea":
            responses[q_id] = st.text_area(
                q_text,
                key=f"custom_survey_{phase_id}_{q_id}"
            )
        
        elif q_type == "choice":
            options = question.get("options", [])
            responses[q_id] = st.selectbox(
                q_text,
                options,
                key=f"custom_survey_{phase_id}_{q_id}"
            )
        
        elif q_type == "multiple_choice":
            options = question.get("options", [])
            responses[q_id] = st.multiselect(
                q_text,
                options,
                key=f"custom_survey_{phase_id}_{q_id}"
            )
        
        else:
            st.warning(f"Unknown question type: {q_type}")
    
    # Submit button
    if st.button("Submit Responses", type="primary", use_container_width=True):
        # Add metadata
        responses["_phase_id"] = phase_id
        responses["_timestamp"] = datetime.now().isoformat()
        
        # Save to database
        success = save_custom_phase_data(session_id, phase_id, responses)
        
        if success:
            logger.info(f"Session {session_id}: Custom survey '{phase_id}' saved")
            st.session_state.phase_complete = True
            st.success("Responses saved!")
        else:
            st.error("Failed to save responses. Please try again.")


def render_break_phase(phase_id: str, content: Dict[str, Any]) -> None:
    """Render timed break with countdown."""
    
    title = content.get("title", "Break")
    duration = content.get("duration_seconds", 30)
    message = content.get("message", f"Please wait {duration} seconds...")
    
    st.title(title)
    st.info(message)
    
    # Initialize timer in session state
    timer_key = f"break_timer_{phase_id}"
    
    if timer_key not in st.session_state:
        st.session_state[timer_key] = time.time()
        logger.info(f"Started break timer for phase {phase_id}: {duration}s")
    
    # Calculate elapsed and remaining time
    elapsed = time.time() - st.session_state[timer_key]
    remaining = max(0, duration - elapsed)
    progress = min(1.0, elapsed / duration)
    
    # Display progress bar
    st.progress(progress)
    
    # Display time remaining
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.metric("Time Remaining", f"{int(remaining)}s")
    
    # Check if complete
    if remaining == 0:
        st.success("Break complete!")
        
        # Clean up timer
        del st.session_state[timer_key]
        
        st.session_state.phase_complete = True
        logger.info(f"Break phase {phase_id} completed")
        
        # Trigger rerun to advance (phase navigation will handle)
        time.sleep(0.5)
        st.rerun()
    else:
        # Sleep briefly and rerun to update countdown
        time.sleep(1)
        st.rerun()
```

**Deliverables:**
- [ ] `custom_phase.py` created with all renderers
- [ ] Support for text, media, survey, break phases
- [ ] Database save for survey responses
- [ ] Timer management for break phases
- [ ] Update PhaseRouter to call `render_custom_phase()`
- [ ] Git commit: `feat: implement custom phase rendering system`

**Testing:**
```python
def test_custom_text_phase():
    """Test custom text phase renders."""
    content = {
        "type": "text",
        "title": "Welcome",
        "text": "Welcome to the experiment!",
        "button_label": "Let's Begin"
    }
    
    render_custom_phase("welcome", content, "test-session")
    # Verify title and text displayed
```

**Success Criteria:**
- [ ] All custom phase types render correctly
- [ ] Survey responses saved to database
- [ ] Timer countdown works without blocking
- [ ] Images/videos load from URLs
- [ ] Error handling for invalid content

---

## Phase 4: Integration & Testing (Week 4)

### Task 4.1: Update Main App Router
**Agent: Integration Agent**  
**Priority:** Critical  
**Estimated Time:** 4 hours  
**Dependencies:** All Phase 3 tasks

**Objective:** Redirect subject interface to use new experiment page.

**Implementation:**

Update `main_app.py`:
```python
def main():
    """Main application router."""
    
    role = st.query_params.get("role", "")
    session_code = st.query_params.get("session", "")
    
    if role == "subject" and session_code:
        # NEW: Redirect subjects to experiment page
        st.switch_page("pages/experiment.py")
    
    elif role == "moderator" and session_code:
        # Moderators still use old interface (for now)
        moderator_interface()
    
    else:
        # Landing page
        landing_page()
```

**Deliverables:**
- [ ] Main app redirects subjects to experiment page
- [ ] Moderator interface unchanged (backward compatible)
- [ ] Landing page still works
- [ ] Git commit: `feat: integrate experiment page into main router`

---

### Task 4.2: End-to-End Testing
**Agent: QA Agent**  
**Priority:** Critical  
**Estimated Time:** 8 hours  
**Dependencies:** Task 4.1

**Test Scenarios:**

#### Scenario 1: Standard Experiment Flow
```
1. Moderator creates session
2. Subject joins via URL
3. Subject completes consent
4. Subject goes through loop:
   - Selection (user-selected)
   - Loading
   - Questionnaire
   - (repeat 5 times)
5. Subject completes registration
6. Subject sees completion screen
```

#### Scenario 2: BO-Driven Experiment
```
1. Moderator creates session with BO protocol
2. Subject joins
3. Cycles alternate user-selected / BO-selected
4. BO converges early → experiment ends
```

#### Scenario 3: Custom Phases
```
1. Protocol with custom phases:
   - Custom text intro
   - Custom video tutorial
   - Experiment loop
   - Custom exit survey
   - Completion
2. Subject goes through all phases
3. Custom survey responses saved
```

#### Scenario 4: Multi-Device Sync
```
1. Subject and moderator on different devices
2. Moderator monitors progress
3. Subject completes phases
4. Both see updated state
```

#### Scenario 5: Error Recovery
```
1. Subject tries to access /experiment without session
   → Redirected to home
2. Subject manipulates URL to skip ahead
   → Blocked by phase validation
3. Network error during phase transition
   → Graceful error message
```

**Deliverables:**
- [ ] Test matrix completed
- [ ] All scenarios pass
- [ ] Edge cases handled
- [ ] Performance acceptable (< 2s page transitions)
- [ ] Git commit: `test: end-to-end experiment flow validation`

---

### Task 4.3: Migration Documentation
**Agent: Documentation Agent**  
**Priority:** High  
**Estimated Time:** 4 hours  
**Dependencies:** Task 4.2

**Create:**

#### docs/MULTIPAGE_MIGRATION.md
```markdown
# Multipage Migration Guide

## Overview
RoboTaste has migrated from state machine-based phase management
to a dynamic single-page router for improved code organization
and protocol flexibility.

## Key Changes

### For Researchers
- **No changes to protocol format** - all existing protocols work
- **Custom phases fully supported** - add custom phases via JSON
- **Same URLs** - subject links unchanged

### For Developers
- **Phase code location changed**:
  - Old: `robotaste/views/subject.py` (1,290 lines)
  - New: `robotaste/views/phases/builtin/*.py` (modular)
  
- **Navigation changed**:
  - Old: `st.rerun()` + state machine transitions
  - New: PhaseRouter handles progression
  
- **Adding new phases**: See [Phase Development Guide](#)

## Architecture

[Diagram showing PhaseRouter flow]

## Backward Compatibility

- Existing sessions continue working
- Database schema unchanged
- Moderator interface unchanged

## Troubleshooting

[Common issues and solutions]
```

#### Update AGENTS.md
```markdown
## Multipage Architecture

### Phase Development

To add a new builtin phase:

1. Create `robotaste/views/phases/builtin/my_phase.py`
2. Implement `render_my_phase(session_id, protocol)` function
3. Set `st.session_state.phase_complete = True` when done
4. Register in `PhaseRouter._register_builtin_phases()`
5. Update database with new phase ID

[Full example code]
```

**Deliverables:**
- [ ] `docs/MULTIPAGE_MIGRATION.md` created
- [ ] `AGENTS.md` updated with new architecture
- [ ] `README.md` updated (if needed)
- [ ] Code comments in PhaseRouter
- [ ] Git commit: `docs: add multipage migration guide`

---

## Phase 5: Deprecation & Cleanup (Week 4-5)

### Task 5.1: Mark Old Code as Deprecated
**Agent: Cleanup Agent**  
**Priority:** Low  
**Estimated Time:** 2 hours

**Add deprecation warnings:**

```python
# robotaste/views/subject.py
"""
DEPRECATED: This module is being phased out.

Subject interface has been migrated to pages/experiment.py with
modular phase renderers in robotaste/views/phases/.

This file is kept for backward compatibility during migration period.

See docs/MULTIPAGE_MIGRATION.md for details.
"""

import warnings
warnings.warn(
    "robotaste.views.subject is deprecated. Use pages/experiment.py",
    DeprecationWarning,
    stacklevel=2
)

# ... existing code ...
```

**Deliverables:**
- [ ] Deprecation warnings added to old files
- [ ] Comments explaining migration
- [ ] Git commit: `chore: deprecate old subject interface`

---

### Task 5.2: Performance Optimization
**Agent: Optimization Agent**  
**Priority:** Medium  
**Estimated Time:** 4 hours

**Optimize:**

1. **Reduce database queries**
   - Cache protocol in session state
   - Batch phase validation queries

2. **Optimize PhaseRouter initialization**
   - Lazy load phase renderers
   - Cache PhaseEngine instance

3. **Minimize reruns**
   - Use `st.fragment()` for countdown timers
   - Reduce unnecessary state updates

**Deliverables:**
- [ ] Performance benchmarks before/after
- [ ] Reduced database queries by 30%
- [ ] Page transitions < 1s
- [ ] Git commit: `perf: optimize PhaseRouter performance`

---

## Phase 6: Future Enhancements (Optional - Week 5-6)

### Task 6.1: Moderator Interface Migration
**Agent: Moderator Migration Agent**  
**Priority:** Low (Nice to have)  
**Estimated Time:** 12 hours

**Migrate moderator interface to pages/moderator.py**

- Separate setup page
- Monitoring page
- Configuration page

### Task 6.2: URL-Based Phase Navigation
**Agent: Advanced Navigation Agent**  
**Priority:** Low  
**Estimated Time:** 8 hours

**Add phase to URL:**
```
/experiment?session=ABC123&role=subject&phase=selection
```

Benefits:
- Browser back button support
- Deep linking to specific phases
- Better debugging

---

## Success Metrics

### Technical Metrics
- [ ] **Zero breaking changes** to existing sessions
- [ ] **< 100ms** PhaseRouter initialization
- [ ] **< 1s** phase transition time
- [ ] **100% test coverage** for phase renderers
- [ ] **50% reduction** in `st.rerun()` calls

### User Experience Metrics
- [ ] **No user-visible changes** to experiment flow
- [ ] **Same or better** performance
- [ ] **All protocols work** without modification

### Code Quality Metrics
- [ ] **Modular** phase code (< 200 lines per phase)
- [ ] **Clear separation** of concerns
- [ ] **Easy to extend** (new phases < 1 hour)
- [ ] **Well documented** (inline + external docs)

---

## Risk Mitigation

### High Risk: Database Sync Issues
**Mitigation:**
- Keep polling mechanism unchanged
- Test multi-device extensively
- Add fallback to direct DB queries

### Medium Risk: Custom Phase Compatibility
**Mitigation:**
- Test with all existing custom phase types
- Add graceful fallbacks for unknown types
- Provide migration tool if needed

### Low Risk: Performance Degradation
**Mitigation:**
- Benchmark before/after
- Optimize PhaseRouter initialization
- Cache protocol data in session state

---

## Rollout Plan

### Week 1: Development Branch
- Create `feature/multipage-migration` branch
- Complete Phase 1 tasks
- Daily commits

### Week 2-3: Implementation
- Complete Phase 2-3 tasks
- Weekly testing checkpoints
- Stakeholder demos

### Week 4: Testing & Documentation
- Complete Phase 4 tasks
- Bug fixes
- Documentation updates

### Week 5: Soft Launch
- Merge to `staging` branch
- Run parallel with old system
- Monitor for issues

### Week 6: Full Deployment
- Merge to `main`
- Update production
- Deprecate old code

---

## Communication Plan

### Weekly Updates
**To:** Project stakeholders  
**Format:** Email summary  
**Contents:**
- Completed tasks
- Blockers
- Next week's plan
- Demo link (if available)

### Code Reviews
**Frequency:** Daily (for critical tasks), weekly (for others)  
**Reviewers:** 2 developers minimum  
**Checklist:**
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No breaking changes
- [ ] Performance acceptable

---

## Agent Assignments

| Agent ID | Role | Tasks | Availability |
|----------|------|-------|--------------|
| Agent-1 | Infrastructure Setup | 1.1-1.3 | Week 1 |
| Agent-2 | Core Architecture | 1.2 | Week 1 |
| Agent-3 | UI Integration | 1.3 | Week 1 |
| Agent-4 | Phase Extraction #1 | 2.1, 2.4 | Week 2 |
| Agent-5 | Phase Extraction #2 | 2.2, 2.5 | Week 2 |
| Agent-6 | Phase Extraction #3 | 2.3, 2.6, 2.7 | Week 2-3 |
| Agent-7 | Custom Phase | 3.1 | Week 3 |
| Agent-8 | Integration | 4.1 | Week 4 |
| Agent-9 | QA | 4.2 | Week 4 |
| Agent-10 | Documentation | 4.3, 5.1 | Week 4 |
| Agent-11 | Optimization | 5.2 | Week 5 |

---

## Quick Start for Agents

### Prerequisites
```bash
git clone https://github.com/alon-nissan/robotaste.git
cd robotaste
git checkout -b feature/multipage-migration
pip install -r requirements.txt
```

### Before Starting Any Task
1. Read task description fully
2. Check dependencies completed
3. Review relevant existing code
4. Ask clarifying questions if needed

### During Task
1. Create feature branch: `feat/task-X.X-description`
2. Write tests first (TDD)
3. Implement functionality
4. Update documentation
5. Self-review code
6. Commit with conventional commit message

### After Task
1. Run full test suite: `pytest`
2. Check linting: `ruff check .`
3. Push branch
4. Create PR with template
5. Request reviews
6. Address feedback
7. Merge when approved

---

## Emergency Contacts

- **Technical Lead:** [Your Name]
- **Product Owner:** [Name]
- **DevOps:** [Name]
- **On-call:** [Rotation schedule]

---

## Appendix: Code Templates

### Phase Renderer Template
```python
def render_PHASE_NAME(session_id: str, protocol: Dict[str, Any]) -> None:
    """
    Render PHASE_NAME phase.
    
    Args:
        session_id: Session UUID
        protocol: Full protocol dictionary
    """
    st.title("PHASE TITLE")
    
    # 1. Get phase configuration from protocol
    config = protocol.get("PHASE_NAME_config", {})
    
    # 2. Render UI
    # ... your Streamlit UI code ...
    
    # 3. Handle user interaction
    if st.button("Continue"):
        # Save data if needed
        # ...
        
        # Mark phase complete
        st.session_state.phase_complete = True
        logger.info(f"Session {session_id}: PHASE_NAME completed")
```

### Test Template
```python
def test_PHASE_NAME_renders():
    """Test PHASE_NAME phase displays correctly."""
    protocol = {
        "PHASE_NAME_config": {...}
    }
    
    render_PHASE_NAME("test-session", protocol)
    
    # Assertions
    assert ...
```

---

**Total Estimated Effort:** 120-160 hours over 4-6 weeks

**Confidence Level:** High (80%) - Architecture is proven, risks are manageable

**Go/No-Go Decision Point:** End of Week 1 - After Task 1.3, validate that routing works before proceeding to phase extraction.