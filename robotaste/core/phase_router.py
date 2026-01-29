"""
Phase Router - Protocol-driven phase navigation system.

This replaces the state machine's explicit transition validation with
dynamic routing based on protocol configuration.

Author: AI Agent
Date: 2026-01-27
"""

import streamlit as st
import logging
from typing import Dict, Any, Callable, Optional
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
    
    # Loop phases are implicit inside experiment_loop and not in phase_sequence
    LOOP_PHASES = {"selection", "loading", "questionnaire", "robot_preparing"}
    
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
        from robotaste.views.phases.builtin.consent import render_consent
        from robotaste.views.phases.builtin.loading import render_loading
        from robotaste.views.phases.builtin.robot_preparing import render_robot_preparing
        from robotaste.views.phases.builtin.completion import render_completion
        from robotaste.views.phases.builtin.registration import render_registration
        from robotaste.views.phases.builtin.questionnaire import render_questionnaire
        from robotaste.views.phases.builtin.selection import render_selection
        
        self._builtin_renderers = {
            "consent": render_consent,
            "loading": render_loading,
            "robot_preparing": render_robot_preparing,
            "completion": render_completion,
            "registration": render_registration,
            "questionnaire": render_questionnaire,
            "selection": render_selection,
        }
    
    def _is_loop_phase(self, phase_id: str) -> bool:
        """Check if phase is an implicit loop phase (not in phase_sequence)."""
        return phase_id in self.LOOP_PHASES
    
    def render_phase(self, phase_id: str) -> None:
        """
        Main entry point: render the specified phase.
        
        Args:
            phase_id: Phase identifier from protocol (e.g., "consent", "selection")
        """
        # Step 1: Validate access
        if not self._validate_phase_access(phase_id):
            return  # _validate_phase_access handles error UI
        
        # Step 2: Handle loop phases specially (they're implicit, not in phase_sequence)
        if self._is_loop_phase(phase_id):
            self._render_loop_phase(phase_id)
            return
        
        # Step 3: Get phase definition for non-loop phases
        phase_def = self._get_phase_definition(phase_id)
        
        if not phase_def:
            self._render_unknown_phase_error(phase_id)
            return
        
        # Step 4: Route based on phase type
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
    
    def _render_loop_phase(self, phase_id: str) -> None:
        """
        Render a loop phase (selection, loading, questionnaire, robot_preparing).
        
        Loop phases are implicit inside experiment_loop and not explicitly
        defined in the protocol's phase_sequence. They route directly to
        builtin renderers.
        """
        renderer = self._builtin_renderers.get(phase_id)
        
        if not renderer:
            st.error(f"No renderer found for loop phase: {phase_id}")
            logger.error(
                f"Missing renderer for loop phase '{phase_id}' "
                f"in session {self.session_id}"
            )
            return
        
        logger.debug(f"Session {self.session_id}: Rendering loop phase '{phase_id}'")
        
        # Call phase-specific renderer
        renderer(self.session_id, self.protocol)
        
        # Add navigation controls
        self._render_phase_navigation(phase_id)
    
    def _render_custom_phase(self, phase_id: str, content: Dict[str, Any]) -> None:
        """Render a custom phase from protocol configuration."""
        from robotaste.views.phases.custom.custom_phase import render_custom_phase
        render_custom_phase(phase_id, content, self.session_id)
        
        # Add navigation controls
        self._render_phase_navigation(phase_id)
    
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
