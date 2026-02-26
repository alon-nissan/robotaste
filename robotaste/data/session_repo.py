"""
RoboTaste Session Repository - High-Level Session Management

Provides high-level abstractions for session operations, including:
- Session info retrieval

This layer sits above database.py and provides business logic for session management.

Author: RoboTaste Team
Version: 4.0 (React + API Architecture)
"""

from typing import Optional, Dict, Any
import logging

# Import database layer
from robotaste.data import database as db

# Setup logging
logger = logging.getLogger(__name__)


def get_session_info(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get session information directly from database.

    Args:
        session_id: Session UUID

    Returns:
        Session dict from database, or None if not found
    """
    try:
        return db.get_session(session_id)
    except Exception as e:
        logger.error(f"Error getting session info: {e}")
        return None
