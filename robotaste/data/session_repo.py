"""
RoboTaste Session Repository - High-Level Session Management

Provides high-level abstractions for session operations, including:
- Session info retrieval
- Joinable session queries

This layer sits above database.py and provides business logic for session management.

Author: RoboTaste Team
Version: 4.0 (React + API Architecture)
"""

from typing import Optional, Dict, Any, List
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


def get_joinable_sessions(filter_phase: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get list of sessions that subjects can join.
    
    Business logic wrapper around database.get_available_sessions().
    Optionally filters by phase (e.g., only show 'waiting' phase).
    
    Args:
        filter_phase: Optional phase filter (e.g., 'waiting', 'registration')
    
    Returns:
        List of joinable sessions with metadata
    """
    try:
        sessions = db.get_available_sessions()
        
        if filter_phase:
            sessions = [s for s in sessions if s.get("current_phase") == filter_phase]
            logger.info(f"Filtered to {len(sessions)} sessions in phase '{filter_phase}'")
        
        return sessions
        
    except Exception as e:
        logger.error(f"Error getting joinable sessions: {e}")
        return []
