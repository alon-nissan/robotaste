"""
Robotaste Styling and CSS Configuration

Provides responsive styling with viewport detection for the RoboTaste application.

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st


def initialize_viewport_detection():
    """
    Initialize viewport detection and store in session state.

    This must be called early in the application lifecycle before CSS is rendered.

    Returns:
        Dictionary with viewport data (width, height)
    """
    # Use Streamlit's built-in viewport detection via JavaScript
    viewport_data = {
        'width': 1920,  # Default fallback
        'height': 1080,  # Default fallback
    }

    # Try to get actual viewport dimensions
    try:
        # This would typically use st.components or JavaScript injection
        # For now, use sensible defaults that work across devices
        pass
    except Exception:
        pass

    # Store in session state
    st.session_state.viewport_data = viewport_data

    return viewport_data


def get_responsive_font_scale():
    """
    Calculate responsive font scaling based on viewport width.

    Returns:
        Float representing font scale multiplier
    """
    if "viewport_data" not in st.session_state:
        return 1.0

    viewport_width = st.session_state.viewport_data.get('width', 1920)

    # Scale fonts based on viewport width
    if viewport_width < 480:
        return 0.8  # Mobile: smaller fonts
    elif viewport_width < 768:
        return 0.9  # Tablet: slightly smaller
    elif viewport_width < 1024:
        return 1.0  # Small desktop: normal
    else:
        return 1.1  # Large desktop: slightly larger


def get_style_css() -> str:
    """
    Generate the main CSS stylesheet for the application.

    Returns:
        String containing CSS styles
    """
    # Initialize viewport if not already done
    if "viewport_initialized" not in st.session_state:
        viewport = initialize_viewport_detection()
        st.session_state.viewport_initialized = True
    else:
        viewport = st.session_state.viewport_data

    # Get responsive font scale
    font_scale = get_responsive_font_scale()

    return f"""
<style>
    /* Dynamic viewport-based constraints and color palette */
    :root {{
        --viewport-width: {viewport.get('width', 1920)}px;
        --viewport-height: {viewport.get('height', 1080)}px;
        --font-scale: {font_scale};

        /* Purple Accents */
        --primary-color: #8B5CF6;
        --primary-hover: #7C3AED;

        /* Semantic Colors */
        --success-color: #10B981;
        --warning-color: #F59E0B;
        --error-color: #EF4444;
        --info-color: #3B82F6;

        /* Neutral Colors */
        --text-primary: #111827;
        --text-secondary: #6B7280;
        --bg-primary: #FFFFFF;
        --bg-secondary: #F9FAFB;
        --border-color: #E5E7EB;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.1);
    }}

    /* Base Typography */
    body {{
        font-size: calc(1.25rem * var(--font-scale));
        color: var(--text-primary);
    }}

    h1 {{ font-size: 3rem; font-weight: 600; }}
    h2 {{ font-size: 2.5rem; font-weight: 600; }}
    h3 {{ font-size: 2rem; font-weight: 600; }}
    p, div, span, label {{ font-size: calc(1.25rem * var(--font-scale)); }}

    /* --- SELECTBOX FIXES --- */

    /* 1. Force text visibility and wrapping in the main box */
    .stSelectbox [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] span {{
        font-size: calc(1.1rem * var(--font-scale)) !important;
        color: var(--text-primary) !important;
        visibility: visible !important;
        opacity: 1 !important;
        white-space: normal !important;
    }}

    /* 2. Style the container itself */
    .stSelectbox [data-baseweb="select"] {{
        min-height: 3.5rem !important;
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
        background-color: var(--bg-primary) !important;
    }}

    /* 3. Ensure the dropdown list (popover) is visible and readable */
    [data-baseweb="popover"] [role="listbox"] {{
        background-color: white !important;
    }}

    [data-baseweb="popover"] li {{
        font-size: calc(1.1rem * var(--font-scale)) !important;
        color: var(--text-primary) !important;
        white-space: normal !important;
        line-height: 1.4 !important;
        padding: 10px !important;
    }}

    /* 4. Fix the focus purple border */
    .stSelectbox [data-baseweb="select"]:focus-within {{
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2) !important;
    }}

    /* --- GENERAL INPUT STYLING --- */

    .stTextInput input, .stNumberInput input {{
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
        padding: 0.75rem !important;
        font-size: calc(1.25rem * var(--font-scale)) !important;
    }}

    /* --- COMPONENT STYLING --- */

    .card {{
        background: var(--bg-primary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 2rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow-sm);
    }}

    .stButton > button {{
        border-radius: 8px;
        padding: 0.75rem 2rem;
        font-size: 1.25rem;
        transition: all 0.2s;
    }}

    .stButton > button[kind="primary"] {{
        background: var(--primary-color);
        color: white;
        border: none;
    }}

    /* --- LAYOUT & RESPONSIVENESS --- */

    @media (max-width: 480px) {{
        h1 {{ font-size: 1.75rem; }}
        .card {{ padding: 1rem; }}
    }}

    /* Prevent page-level scrolling and constrain to viewport */
    .main .block-container {{
        max-height: calc(var(--viewport-height) - 2rem);
        overflow-y: auto;
        padding-top: 2rem;
    }}

    /* Force Light Mode */
    * {{ color-scheme: light !important; }}
</style>
"""


def apply_styles():
    """
    Apply CSS styles to the Streamlit application.

    Call this function early in your main application file.
    """
    st.markdown(get_style_css(), unsafe_allow_html=True)


# Backward compatibility: Export STYLE constant for modules that import it directly
STYLE = get_style_css()
