"""
Builtin Phase Renderers

Phase renderer functions for standard RoboTaste experiment phases.
Each module exports a render_PHASE_NAME function that follows the standard signature:

    def render_PHASE_NAME(session_id: str, protocol: Dict[str, Any]) -> None

Builtin phases:
- consent: Informed consent screen
- loading: Loading/waiting screen
- robot_preparing: Robot preparation phase
- completion: Session completion screen
- registration: User registration form
- questionnaire: Rating questionnaire
- selection: Sample selection interface (grid or slider)

Usage:
    from robotaste.views.phases.builtin.consent import render_consent
    render_consent(session_id, protocol)

Author: RoboTaste Team
Date: 2026-01-27
"""

# Import all builtin phase renderers
from .consent import render_consent
from .loading import render_loading
from .robot_preparing import render_robot_preparing
from .completion import render_completion
from .registration import render_registration
from .questionnaire import render_questionnaire
from .selection import render_selection

__all__ = [
    'render_consent',
    'render_loading',
    'render_robot_preparing',
    'render_completion',
    'render_registration',
    'render_questionnaire',
    'render_selection',
]

