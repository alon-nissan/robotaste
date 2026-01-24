"""
Session Info Panel Component

Displays session code, QR code, and shareable URL for subject access.
Matches the clean, scientific aesthetic of mashaniv.wixsite.com/niv-taste-lab

Author: RoboTaste Team
Version: 3.0 (Refactored Architecture)
"""

import streamlit as st
import logging
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


def generate_qr_code(url: str, size: int = 250) -> Optional[BytesIO]:
    """
    Generate QR code for session URL.

    Args:
        url: URL to encode in QR code
        size: Size of QR code in pixels (box_size will be calculated)

    Returns:
        BytesIO object containing PNG image, or None if generation fails
    """
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Use clean purple color matching site aesthetic
        img = qr.make_image(fill_color="#521924", back_color="white")

        # Convert to bytes
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    except ImportError:
        logger.warning("qrcode package not installed. Run: pip install qrcode[pil]")
        return None
    except Exception as e:
        logger.error(f"Failed to generate QR code: {e}")
        return None


def get_subject_url(session_code: str) -> str:
    """
    Construct subject URL based on current host.

    Args:
        session_code: 6-character session code

    Returns:
        Full URL for subject to join session
    """
    try:
        # Try to get from query params (works in deployed environments)
        base_url = st.query_params.get("_host", "")
        if not base_url:
            # Fallback to localhost
            base_url = "localhost:8501"

        # Ensure http:// prefix
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"

    except Exception:
        base_url = "http://localhost:8501"

    return f"{base_url}/?role=subject&session={session_code}"


def render_session_info_panel(session_code: str, expanded: bool = True) -> None:
    """
    Render session info panel with clean, scientific design.
    Matches aesthetic of mashaniv.wixsite.com/niv-taste-lab

    Args:
        session_code: 6-character session code
        expanded: Whether to show expanded by default
    """
    subject_url = get_subject_url(session_code)

    with st.expander("📱 Session Information", expanded=expanded):
        # Clean header section with session code
        st.markdown(
            f"""
            <div style='text-align: center; padding: 2.5rem;
            background: #F8F9FA; border-radius: 8px;
            border-left: 4px solid #521924; margin-bottom: 2rem;'>
                <div style='font-size: 1rem; color: #7F8C8D;
                font-weight: 400; margin-bottom: 0.5rem;
                letter-spacing: 0.1em; text-transform: uppercase;'>
                Session Code
                </div>
                <div style='font-size: 3rem; color: #2C3E50;
                font-weight: 600; letter-spacing: 0.5rem;
                font-family: "Monaco", "Courier New", monospace;'>
                {session_code}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        # Two columns: QR code and URL
        col1, col2 = st.columns([1, 2])

        with col1:
            st.markdown("**Scan to Join**")
            # Generate and display QR code
            qr_buffer = generate_qr_code(subject_url, size=250)
            if qr_buffer:
                st.image(qr_buffer, use_container_width=True)
            else:
                st.info("QR code unavailable")

        with col2:
            st.markdown("**Share This Link**")
            st.code(subject_url, language=None)

            # Instructions
            st.markdown("---")
            st.caption(
                "**Instructions:** Subjects can scan the QR code or "
                "enter the session code to join the experiment."
            )
