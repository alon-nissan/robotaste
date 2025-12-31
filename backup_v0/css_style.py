import streamlit as st
from viewport_utils import initialize_viewport_detection, get_responsive_font_scale

# Page configuration
st.set_page_config(
    page_title="Taste Experiment System",
    page_icon="",
    layout="centered",
    initial_sidebar_state="auto",
)

# Initialize viewport detection EARLY (before CSS)
# This must be done before rendering CSS that depends on viewport
if "viewport_initialized" not in st.session_state:
    viewport = initialize_viewport_detection()
    st.session_state.viewport_initialized = True
else:
    viewport = st.session_state.viewport_data

# Get font scale for responsive typography
font_scale = get_responsive_font_scale()

STYLE = f"""
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
