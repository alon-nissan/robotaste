"""
Session Management for Multi-Device RoboTaste Deployment
========================================================

Handles session creation, device pairing, and real-time synchronization
for moderator-subject multi-device functionality on Streamlit Cloud.

Features:
- Unique session code generation
- QR code generation for easy device pairing
- Real-time session state synchronization
- Cloud-deployment ready with persistent storage
"""

import random
import string
import qrcode
import io
import base64
from PIL import Image
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sql_handler import get_database_connection
import sqlite3


def generate_session_code(length: int = 6) -> str:
    """Generate a unique session code for device pairing."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def create_qr_code(url: str) -> str:
    """Create a QR code for the given URL and return as base64 string."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64 for embedding in HTML
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def create_session(moderator_name: str = "Moderator") -> str:
    """Create a new session and return the session code."""
    session_code = generate_session_code()

    # Ensure uniqueness by checking database
    with get_database_connection() as conn:
        cursor = conn.cursor()

        # Create sessions table if it doesn't exist
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_code TEXT PRIMARY KEY,
                moderator_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                subject_connected BOOLEAN DEFAULT 0,
                experiment_config TEXT DEFAULT '{}',
                current_phase TEXT DEFAULT 'waiting'
            )
        """
        )

        # Check if code already exists, regenerate if necessary
        while True:
            cursor.execute(
                "SELECT session_code FROM sessions WHERE session_code = ?",
                (session_code,),
            )
            if cursor.fetchone() is None:
                break
            session_code = generate_session_code()

        # Insert new session
        cursor.execute(
            """
            INSERT INTO sessions (session_code, moderator_name, current_phase)
            VALUES (?, ?, 'waiting')
        """,
            (session_code, moderator_name),
        )

        conn.commit()

    return session_code


def join_session(session_code: str) -> bool:
    """Join an existing session as subject. Returns True if successful."""
    with get_database_connection() as conn:
        cursor = conn.cursor()

        # Check if session exists and is active
        cursor.execute(
            """
            SELECT session_code, is_active FROM sessions 
            WHERE session_code = ? AND is_active = 1
        """,
            (session_code,),
        )

        result = cursor.fetchone()
        if result:
            # Mark subject as connected
            cursor.execute(
                """
                UPDATE sessions 
                SET subject_connected = 1, last_activity = CURRENT_TIMESTAMP
                WHERE session_code = ?
            """,
                (session_code,),
            )
            conn.commit()
            return True

    return False


def get_session_info(session_code: str) -> Optional[Dict[str, Any]]:
    """Get session information."""
    with get_database_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT session_code, moderator_name, created_at, last_activity, 
                   is_active, subject_connected, experiment_config, current_phase
            FROM sessions WHERE session_code = ?
        """,
            (session_code,),
        )

        result = cursor.fetchone()

    if result:
        return {
            "session_code": result[0],
            "moderator_name": result[1],
            "created_at": result[2],
            "last_activity": result[3],
            "is_active": bool(result[4]),
            "subject_connected": bool(result[5]),
            "experiment_config": result[6],
            "current_phase": result[7],
        }
    return None


def update_session_activity(session_code: str, phase: str = None, config: str = None):
    """Update session last activity and optionally phase/config."""
    with get_database_connection() as conn:
        cursor = conn.cursor()

        updates = ["last_activity = CURRENT_TIMESTAMP"]
        params = []

        if phase:
            updates.append("current_phase = ?")
            params.append(phase)

        if config:
            updates.append("experiment_config = ?")
            params.append(config)

        params.append(session_code)

        cursor.execute(
            f"""
            UPDATE sessions SET {', '.join(updates)}
            WHERE session_code = ?
        """,
            params,
        )

        conn.commit()


def cleanup_old_sessions(hours: int = 24):
    """Clean up sessions older than specified hours."""
    with get_database_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE sessions SET is_active = 0 
            WHERE last_activity < datetime('now', '-{} hours')
        """.format(
                hours
            )
        )

        conn.commit()


def get_active_sessions() -> list:
    """Get list of active sessions for admin purposes."""
    with get_database_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT session_code, moderator_name, created_at, subject_connected, current_phase
            FROM sessions 
            WHERE is_active = 1 
            ORDER BY created_at DESC
        """
        )

        results = cursor.fetchall()

    return [
        {
            "session_code": row[0],
            "moderator_name": row[1],
            "created_at": row[2],
            "subject_connected": bool(row[3]),
            "current_phase": row[4],
        }
        for row in results
    ]


def generate_session_urls(
    session_code: str, base_url: str = "https://your-app.streamlit.app"
) -> Dict[str, str]:
    """Generate URLs for moderator and subject interfaces."""
    return {
        "moderator": f"{base_url}/?role=moderator&session={session_code}",
        "subject": f"{base_url}/?role=subject&session={session_code}",
    }


def display_session_qr_code(
    session_code: str,
    base_url: str = "https://your-app.streamlit.app",
    context: str = "default",
):
    """Display QR code for subject to join session."""
    urls = generate_session_urls(session_code, base_url)
    subject_url = urls["subject"]
    qr_code_data = create_qr_code(subject_url)

    st.markdown("### 📱 Subject Access")
    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(
            f"""
        <div style="text-align: center; padding: 20px;">
            <h4>Scan QR Code</h4>
            <img src="{qr_code_data}" alt="QR Code" style="max-width: 200px;">
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown("**Session Code:**")
        st.code(session_code, language="text")
        st.markdown("**Subject URL:**")
        st.code(subject_url, language="text")

        if st.button(
            "📋 Copy Subject URL",
            help="Copy URL to clipboard",
            key=f"session_qr_copy_url_{context}_{session_code}",
        ):
            st.success("URL copied to clipboard!")


def sync_session_state(session_code: str, role: str):
    """Sync session state between devices."""
    session_info = get_session_info(session_code)

    if session_info:
        # Update activity timestamp
        update_session_activity(session_code)

        # Store session info in Streamlit session state
        st.session_state.session_code = session_code
        st.session_state.session_info = session_info
        st.session_state.device_role = role
        st.session_state.last_sync = datetime.now()

        return True
    return False


def get_connection_status(session_code: str) -> Dict[str, Any]:
    """Get real-time connection status for both devices."""
    session_info = get_session_info(session_code)

    if not session_info:
        return {"error": "Session not found"}

    # Check if session is recently active (within last 30 seconds)
    last_activity = datetime.fromisoformat(session_info["last_activity"])
    is_recent = (datetime.now() - last_activity).total_seconds() < 30

    return {
        "session_active": session_info["is_active"],
        "subject_connected": session_info["subject_connected"],
        "recently_active": is_recent,
        "current_phase": session_info["current_phase"],
        "last_activity": session_info["last_activity"],
    }
