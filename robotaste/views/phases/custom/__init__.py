"""
Custom Phase Renderers

Protocol-defined custom phases that extend the experiment with
dynamic content.

Supported custom phase types:
- text: Display text/instructions
- media: Display images or videos
- survey: Custom survey questions
- break: Timed break with countdown

Author: AI Agent
Date: 2026-01-27
"""

from .custom_phase import render_custom_phase

__all__ = ['render_custom_phase']
