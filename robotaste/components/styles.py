"""
Minimal styling for RoboTaste - brand colors and essential overrides only.

Most styling is handled by Streamlit defaults and .streamlit/config.toml.
This file provides only:
- CSS variables for brand colors (used by inline styles elsewhere)
- Button styling (primary burgundy)
- Progress bar gradient
- Ghost element cleanup

Author: RoboTaste Team
Version: 4.0 (Minimal)
"""

import streamlit as st


def get_style_css() -> str:
    """
    Generate minimal CSS stylesheet.
    
    Returns:
        String containing CSS styles
    """
    return """
<style>
    /* === CSS VARIABLES (Brand Colors) === */
    :root {
        --primary: #521924;
        --primary-light: #7a2e3d;
        --primary-dark: #3a1119;
        --accent: #fda50f;
        --accent-light: #ffc04d;
    }

    /* === LAYOUT (Reduce header blank space) === */
    .main .block-container {
        padding-top: 1rem !important;
    }

    /* === BUTTONS (Burgundy branding) === */
    .stButton > button {
        background: var(--primary) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        min-height: 44px !important;
    }

    .stButton > button:hover {
        background: var(--primary-light) !important;
    }

    .stButton > button p,
    .stButton > button span,
    .stButton > button div {
        color: white !important;
    }

    /* Secondary buttons */
    .stButton > button[kind="secondary"] {
        background: transparent !important;
        color: var(--primary) !important;
        border: 2px solid var(--primary) !important;
    }

    .stButton > button[kind="secondary"]:hover {
        background: rgba(82, 25, 36, 0.05) !important;
    }

    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span {
        color: var(--primary) !important;
    }

    /* Form submit buttons */
    .stFormSubmitButton > button {
        background: var(--primary) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        min-height: 44px !important;
    }

    .stFormSubmitButton > button:hover {
        background: var(--primary-light) !important;
    }

    /* === PROGRESS BAR (Burgundy gradient) === */
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--primary) 0%, var(--primary-light) 100%) !important;
    }

    /* === GHOST ELEMENT FIX === */
    .element-container:empty {
        display: none !important;
    }

    button:disabled, input:disabled, select:disabled {
        opacity: 0.6 !important;
        cursor: not-allowed !important;
    }

    /* === FORCE LIGHT MODE === */
    * { color-scheme: light !important; }
</style>
"""


def apply_styles():
    """
    Apply CSS styles to the Streamlit application.
    Call this function early in your main application file.
    """
    st.markdown(get_style_css(), unsafe_allow_html=True)


# Backward compatibility
STYLE = get_style_css()
