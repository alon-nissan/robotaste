"""
Robotaste Styling and CSS Configuration

Provides responsive styling with viewport detection for the RoboTaste application.
Matches the clean, scientific aesthetic of mashaniv.wixsite.com/niv-taste-lab

Target devices:
- Moderator: 13" laptop (1366x768 or 1440x900)
- Subject: 11" tablet (1024x768)

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
        'width': 1366,  # Default fallback (13" laptop)
        'height': 768,
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

    viewport_width = st.session_state.viewport_data.get('width', 1366)

    # Scale fonts based on viewport width
    if viewport_width < 480:
        return 0.8  # Mobile: smaller fonts
    elif viewport_width < 768:
        return 0.9  # Tablet: slightly smaller
    elif viewport_width < 1024:
        return 0.95  # Small tablet: nearly normal
    elif viewport_width < 1440:
        return 1.0  # Laptop: normal
    else:
        return 1.05  # Large desktop: slightly larger


def get_style_css() -> str:
    """
    Generate the main CSS stylesheet for the application.
    Matches the clean, scientific aesthetic of the reference site.

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
    /* === CSS VARIABLES (Niv Taste Lab Palette) === */
    :root {{
        --viewport-width: {viewport.get('width', 1366)}px;
        --viewport-height: {viewport.get('height', 768)}px;
        --font-scale: {font_scale};

        /* Primary Colors (Burgundy + Saffron) */
        --primary: #521924;
        --primary-light: #7a2e3d;
        --primary-dark: #3a1119;
        --accent: #fda50f;
        --accent-light: #ffc04d;

        /* Neutral Colors (Clean, scientific) */
        --text-primary: #1a1a1a;
        --text-secondary: #4a4a4a;
        --text-light: #6a6a6a;
        --bg-primary: #FFFFFF;
        --bg-secondary: #F8F9FA;
        --bg-tertiary: #F3F4F6;
        --border-light: #E5E7EB;
        --border-medium: #D1D5DB;

        /* Semantic Colors (Muted, professional) */
        --success: #27AE60;
        --success-light: #E8F5E9;
        --warning: #F39C12;
        --warning-light: #FFF8E1;
        --error: #E74C3C;
        --error-light: #FFEBEE;
        --info: #3498DB;
        --info-light: #E3F2FD;

        /* Minimal shadows (flat design) */
        --shadow-minimal: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-subtle: 0 1px 3px rgba(0,0,0,0.08);

        /* Spacing */
        --spacing-xs: 0.5rem;
        --spacing-sm: 1rem;
        --spacing-md: 1.5rem;
        --spacing-lg: 2rem;
        --spacing-xl: 3rem;

        /* Transitions */
        --transition: 0.2s ease;
    }}

    /* === BASE TYPOGRAPHY (Light-weight headers, readable body) === */
    body {{
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                     "Roboto", "Oxygen", "Ubuntu", "Helvetica Neue",
                     Arial, sans-serif !important;
        color: var(--text-primary) !important;
        line-height: 1.7 !important;
        font-weight: 400 !important;
    }}

    h1 {{
        font-size: clamp(2rem, 3vw, 2.5rem) !important;
        font-weight: 300 !important;
        color: var(--text-primary) !important;
        letter-spacing: 0.05em !important;
        margin: var(--spacing-lg) 0 var(--spacing-md) 0 !important;
        line-height: 1.3 !important;
    }}

    h2 {{
        font-size: clamp(1.75rem, 2.5vw, 2rem) !important;
        font-weight: 300 !important;
        color: var(--text-primary) !important;
        letter-spacing: 0.03em !important;
        margin: var(--spacing-md) 0 var(--spacing-sm) 0 !important;
    }}

    h3 {{
        font-size: clamp(1.5rem, 2vw, 1.75rem) !important;
        font-weight: 400 !important;
        color: var(--text-primary) !important;
        margin: var(--spacing-md) 0 var(--spacing-sm) 0 !important;
    }}

    p, div, span, label {{
        font-size: clamp(1rem, 1.5vw, 1.125rem) !important;
        line-height: 1.7 !important;
        color: var(--text-primary) !important;
    }}

    .stCaption {{
        font-size: 0.9rem !important;
        color: var(--text-secondary) !important;
        font-weight: 400 !important;
    }}

    /* === MAIN CONTAINER (Optimized for laptop/tablet) === */
    .main .block-container {{
        max-width: 100% !important;
        padding: var(--spacing-md) var(--spacing-lg) !important;
        max-height: calc(var(--viewport-height) - 3rem) !important;
        overflow-y: auto !important;
        animation: fadeIn 0.3s ease-in !important;
    }}

    /* === BUTTONS (Clean, Flat Design) === */
    .stButton > button {{
        background: var(--primary) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.75rem 1.75rem !important;
        font-size: clamp(0.95rem, 1.5vw, 1.1rem) !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
        transition: all var(--transition) !important;
        box-shadow: none !important;
        cursor: pointer !important;
        min-height: 44px !important;
    }}

    /* Ensure all text elements inside buttons are white */
    .stButton > button p,
    .stButton > button span,
    .stButton > button div {{
        color: white !important;
    }}

    .stButton > button:hover {{
        background: var(--primary-light) !important;
        color: white !important;
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-subtle) !important;
    }}

    .stButton > button:active {{
        transform: translateY(0) !important;
    }}

    /* === FORM SUBMIT BUTTONS (Same styling as regular buttons) === */
    .stFormSubmitButton > button {{
        background: var(--primary) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.75rem 1.75rem !important;
        font-size: clamp(0.95rem, 1.5vw, 1.1rem) !important;
        font-weight: 500 !important;
        letter-spacing: 0.02em !important;
        transition: all var(--transition) !important;
        box-shadow: none !important;
        cursor: pointer !important;
        min-height: 44px !important;
    }}

    /* Ensure all text elements inside form submit buttons are white */
    .stFormSubmitButton > button p,
    .stFormSubmitButton > button span,
    .stFormSubmitButton > button div {{
        color: white !important;
    }}

    .stFormSubmitButton > button:hover {{
        background: var(--primary-light) !important;
        color: white !important;
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-subtle) !important;
    }}

    .stFormSubmitButton > button:active {{
        transform: translateY(0) !important;
    }}

    .stButton > button[kind="secondary"] {{
        background: transparent !important;
        color: var(--primary) !important;
        border: 2px solid var(--primary) !important;
    }}

    /* Ensure text elements in secondary buttons stay burgundy */
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span,
    .stButton > button[kind="secondary"] div {{
        color: var(--primary) !important;
    }}

    .stButton > button[kind="secondary"]:hover {{
        background: var(--bg-secondary) !important;
        color: var(--primary) !important;
    }}

    .stButton > button[kind="secondary"]:hover p,
    .stButton > button[kind="secondary"]:hover span,
    .stButton > button[kind="secondary"]:hover div {{
        color: var(--primary) !important;
    }}

    /* === SELECTBOX STYLING (Enhanced) === */
    .stSelectbox [data-baseweb="select"] {{
        min-height: 3.5rem !important;
        border: 2px solid var(--border-medium) !important;
        border-radius: 8px !important;
        background-color: white !important;
        transition: all var(--transition) !important;
    }}

    .stSelectbox [data-baseweb="select"]:hover {{
        border-color: var(--text-secondary) !important;
    }}

    .stSelectbox [data-baseweb="select"]:focus-within {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(109, 40, 217, 0.1) !important;
    }}

    .stSelectbox [data-baseweb="select"] div,
    .stSelectbox [data-baseweb="select"] span {{
        font-size: 1.1rem !important;
        color: var(--text-primary) !important;
        font-weight: 400 !important;
        visibility: visible !important;
        opacity: 1 !important;
        white-space: normal !important;
    }}

    [data-baseweb="popover"] [role="listbox"] {{
        background-color: white !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }}

    [data-baseweb="popover"] li {{
        font-size: 1rem !important;
        color: var(--text-primary) !important;
        padding: 12px 16px !important;
        border-bottom: 1px solid var(--bg-tertiary) !important;
        line-height: 1.4 !important;
    }}

    [data-baseweb="popover"] li:hover {{
        background-color: var(--bg-secondary) !important;
    }}

    /* === FORMS & INPUTS (Clean, Professional) === */
    .stTextInput input, .stNumberInput input, .stTextArea textarea {{
        border: 2px solid var(--border-medium) !important;
        border-radius: 6px !important;
        padding: 0.75rem !important;
        font-size: clamp(1rem, 1.5vw, 1.125rem) !important;
        color: var(--text-primary) !important;
        background: white !important;
        transition: border-color var(--transition) !important;
        box-shadow: none !important;
        min-height: 44px !important;
    }}

    .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(82, 25, 36, 0.08) !important;
        outline: none !important;
    }}

    .stTextInput label, .stNumberInput label, .stTextArea label {{
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
        margin-bottom: 0.5rem !important;
    }}

    /* === METRICS (Clean Cards) === */
    [data-testid="stMetric"] {{
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
        padding: 1.25rem !important;
        transition: all var(--transition) !important;
    }}

    [data-testid="stMetric"]:hover {{
        border-color: var(--border-medium) !important;
    }}

    [data-testid="stMetric"] label {{
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        margin-bottom: 0.5rem !important;
    }}

    [data-testid="stMetric"] [data-testid="stMetricValue"] {{
        font-size: 2rem !important;
        font-weight: 600 !important;
        color: var(--primary) !important;
        line-height: 1.2 !important;
    }}

    /* === CARDS & CONTAINERS (Minimal, Scientific) === */
    .card {{
        background: white !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
        padding: 1.5rem !important;
        margin: 1rem 0 !important;
        box-shadow: none !important;
    }}

    .highlight-card {{
        border-left: 4px solid var(--primary) !important;
        background: var(--bg-secondary) !important;
    }}

    /* === ALERTS & MESSAGES (Minimal Design) === */
    .stSuccess, [data-testid="stAlert"][data-baseweb="notification"][kind="success"] {{
        background: var(--success-light) !important;
        border: none !important;
        border-left: 4px solid var(--success) !important;
        border-radius: 6px !important;
        padding: 1rem 1.25rem !important;
        color: var(--text-primary) !important;
    }}

    .stError, [data-testid="stAlert"][data-baseweb="notification"][kind="error"] {{
        background: var(--error-light) !important;
        border: none !important;
        border-left: 4px solid var(--error) !important;
        border-radius: 6px !important;
        padding: 1rem 1.25rem !important;
        color: var(--text-primary) !important;
    }}

    .stWarning, [data-testid="stAlert"][data-baseweb="notification"][kind="warning"] {{
        background: var(--warning-light) !important;
        border: none !important;
        border-left: 4px solid var(--warning) !important;
        border-radius: 6px !important;
        padding: 1rem 1.25rem !important;
        color: var(--text-primary) !important;
    }}

    .stInfo, [data-testid="stAlert"][data-baseweb="notification"][kind="info"] {{
        background: var(--info-light) !important;
        border: none !important;
        border-left: 4px solid var(--info) !important;
        border-radius: 6px !important;
        padding: 1rem 1.25rem !important;
        color: var(--text-primary) !important;
    }}

    /* === LOADING SCREEN STYLING === */
    .stSpinner {{
        text-align: center !important;
        margin: var(--spacing-xl) 0 !important;
    }}

    .stSpinner > div {{
        font-size: 1.5rem !important;
        font-weight: 300 !important;
        color: var(--text-primary) !important;
        letter-spacing: 0.05em !important;
    }}

    /* Progress bar - clean, minimal styling */
    .stProgress > div > div {{
        background: linear-gradient(90deg, var(--primary) 0%, var(--primary-light) 100%) !important;
        height: 8px !important;
        border-radius: 4px !important;
        transition: width 0.3s ease !important;
    }}

    .stProgress > div {{
        background-color: var(--border-light) !important;
        border-radius: 4px !important;
        height: 8px !important;
    }}

    /* === EXPANDERS === */
    .streamlit-expanderHeader {{
        background: var(--bg-secondary) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }}

    /* === TABLES (Clean, Scientific) === */
    .stDataFrame {{
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
    }}

    /* === HORIZONTAL DIVIDERS === */
    hr {{
        border: none !important;
        border-top: 1px solid var(--border-light) !important;
        margin: var(--spacing-lg) 0 !important;
    }}

    /* === PHASE TRANSITION ANIMATIONS === */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(5px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}

    .element-container {{
        animation: fadeIn 0.3s ease-in !important;
    }}

    /* === DEVICE-SPECIFIC ADJUSTMENTS === */

    /* 11" Tablet (Subject Interface) */
    @media (max-width: 1024px) {{
        .main .block-container {{
            padding: var(--spacing-sm) var(--spacing-md) !important;
        }}

        /* Larger touch targets */
        .stButton > button {{
            min-height: 48px !important;
            padding: 1rem 2rem !important;
        }}

        /* Optimize canvas for tablet */
        .canvas-container {{
            max-width: 95vw !important;
        }}
    }}

    /* 13" Laptop (Moderator Interface) */
    @media (max-width: 1440px) and (min-width: 1025px) {{
        .main .block-container {{
            max-width: 1300px !important;
            margin: 0 auto !important;
        }}

        /* Optimize sidebar width */
        section[data-testid="stSidebar"] {{
            width: 250px !important;
            min-width: 250px !important;
        }}
    }}

    /* Short screens (optimize vertical space) */
    @media (max-height: 800px) {{
        h1 {{
            margin-top: var(--spacing-sm) !important;
            margin-bottom: var(--spacing-xs) !important;
        }}

        .main .block-container {{
            padding-top: var(--spacing-sm) !important;
        }}

        [data-testid="stMetric"] {{
            padding: 0.75rem !important;
        }}
    }}

    /* Mobile fallback */
    @media (max-width: 480px) {{
        h1 {{ font-size: 1.75rem !important; }}
        .card {{ padding: 1rem !important; }}
    }}

    /* === CANVAS CONTAINER === */
    .canvas-container {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: var(--spacing-lg) 0 !important;
    }}

    /* === FORCE LIGHT MODE === */
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
