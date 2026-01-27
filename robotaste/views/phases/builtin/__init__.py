"""
Builtin Phase Renderers

Standard experiment phases that are part of the RoboTaste core system.
Each renderer is a function that takes (session_id, protocol) and renders
the appropriate UI for that phase.

Available renderers:
- consent: Informed consent phase
- selection: Sample selection interface (grid/slider)
- questionnaire: Rating questionnaire
- loading: Loading/waiting screen
- robot_preparing: Robot preparation phase
- registration: Subject registration form
- completion: Experiment completion screen

Author: AI Agent
Date: 2026-01-27
"""

# Renderers imported as they are created
from .consent import render_consent
# from .selection import render_selection
# from .questionnaire import render_questionnaire
# from .loading import render_loading
# from .robot_preparing import render_robot_preparing
# from .registration import render_registration
# from .completion import render_completion

__all__ = [
    'render_consent',
    # Add more as they are created
]
