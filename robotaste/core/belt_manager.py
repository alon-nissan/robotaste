"""
Global belt manager for session-persistent connections.

This module manages conveyor belt connections across multiple experiment cycles.
Similar to pump_manager.py, it caches connections per session to avoid
repeated serial port initialization.

Performance Impact:
- Arduino may reset on serial connection (~2 seconds delay)
- With caching: 2 seconds on first cycle only, 0 seconds on subsequent cycles

Author: RoboTaste Team
Version: 1.0
"""

import logging
from typing import Dict, Optional, Any

from robotaste.hardware.belt_controller import (
    ConveyorBelt,
    BeltConnectionError,
    BeltPosition,
    BeltStatus
)

logger = logging.getLogger(__name__)

# Global cache: {session_id: ConveyorBelt}
_belt_cache: Dict[str, ConveyorBelt] = {}


def get_or_create_belt(
    session_id: str,
    belt_config: Dict[str, Any]
) -> ConveyorBelt:
    """
    Get existing belt for session or create a new one.

    This function checks if a belt is already initialized for the given session.
    If it exists and is still connected, it is reused. Otherwise, a new
    belt connection is initialized.

    Args:
        session_id: Session identifier
        belt_config: Belt configuration from protocol with keys:
            - serial_port: Serial port path
            - baud_rate: Baud rate (default 9600)
            - timeout_seconds: Operation timeout (default 30)

    Returns:
        ConveyorBelt instance

    Example:
        >>> belt_config = {
        ...     "enabled": True,
        ...     "serial_port": "/dev/tty.usbmodem14101",
        ...     "baud_rate": 9600,
        ...     "timeout_seconds": 30
        ... }
        >>> belt = get_or_create_belt("session-123", belt_config)
        >>> belt.is_connected()
        True
    """
    if session_id in _belt_cache:
        cached_belt = _belt_cache[session_id]
        
        if cached_belt.is_connected():
            logger.info(f"Reusing existing belt connection for session {session_id}")
            return cached_belt
        else:
            logger.warning(f"Cached belt for session {session_id} is disconnected, reinitializing")
            cleanup_belt(session_id)

    # Initialize new belt connection
    logger.info(f"Initializing new belt connection for session {session_id}")
    belt = _initialize_belt(belt_config)
    _belt_cache[session_id] = belt
    logger.info(f"Cached belt for session {session_id}")

    return belt


def _initialize_belt(belt_config: Dict[str, Any]) -> ConveyorBelt:
    """
    Initialize belt with configuration.

    Args:
        belt_config: Belt configuration dictionary

    Returns:
        ConveyorBelt instance

    Raises:
        BeltConnectionError: If connection fails
        ValueError: If configuration is invalid
    """
    serial_port = belt_config.get("serial_port")
    baud_rate = belt_config.get("baud_rate", 9600)
    timeout = belt_config.get("timeout_seconds", 30)
    
    # Check if we should use mock mode
    mock_mode = belt_config.get("mock_mode", False)

    if not serial_port and not mock_mode:
        raise ValueError("serial_port is required in belt_config (or enable mock_mode)")

    logger.info(f"Connecting to belt on {serial_port} at {baud_rate} baud (timeout: {timeout}s)")

    belt = ConveyorBelt(
        port=serial_port or "",
        baud=baud_rate,
        timeout=timeout,
        mock_mode=mock_mode
    )

    belt.connect()

    logger.info(f"Belt connected: position={belt.get_position().value}, status={belt.get_status().value}")

    return belt


def cleanup_belt(session_id: str) -> None:
    """
    Disconnect and remove belt for a session.

    Should be called when a session completes to free hardware resources.

    Args:
        session_id: Session identifier

    Example:
        >>> cleanup_belt("session-123")
        # Disconnects belt and removes from cache
    """
    if session_id not in _belt_cache:
        logger.debug(f"No cached belt to cleanup for session {session_id}")
        return

    belt = _belt_cache[session_id]
    logger.info(f"Cleaning up belt for session {session_id}")

    try:
        if belt.is_connected():
            belt.disconnect()
            logger.debug(f"Disconnected belt for session {session_id}")
    except Exception as e:
        logger.warning(f"Error disconnecting belt: {e}")

    del _belt_cache[session_id]
    logger.info(f"Cleaned up belt for session {session_id}")


def get_cached_belt_count() -> int:
    """
    Get the number of sessions with cached belts.

    Useful for monitoring and debugging.

    Returns:
        Number of sessions in cache
    """
    return len(_belt_cache)


def get_session_belt_info(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about cached belt for a session.

    Args:
        session_id: Session identifier

    Returns:
        Dict with belt info or None if no cached belt
    """
    if session_id not in _belt_cache:
        return None

    belt = _belt_cache[session_id]

    return {
        "session_id": session_id,
        "connected": belt.is_connected(),
        "position": belt.get_position().value,
        "status": belt.get_status().value,
        "port": belt.port,
    }


def cleanup_all_belts() -> None:
    """
    Cleanup all cached belts across all sessions.

    Emergency cleanup function. Use with caution as it will disconnect
    belts for all active sessions.
    """
    session_ids = list(_belt_cache.keys())

    if not session_ids:
        logger.debug("No belts to cleanup")
        return

    logger.warning(f"Cleaning up ALL cached belts ({len(session_ids)} sessions)")

    for session_id in session_ids:
        cleanup_belt(session_id)

    logger.info("All belts cleaned up")


def is_belt_enabled(protocol: Dict[str, Any]) -> bool:
    """
    Check if belt is enabled in protocol configuration.

    Args:
        protocol: Protocol dictionary

    Returns:
        True if belt is enabled
    """
    belt_config = protocol.get("belt_config", {})
    return belt_config.get("enabled", False)


def get_belt_config(protocol: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get belt configuration from protocol.

    Args:
        protocol: Protocol dictionary

    Returns:
        Belt config dict if enabled, None otherwise
    """
    belt_config = protocol.get("belt_config", {})
    
    if not belt_config.get("enabled", False):
        return None
    
    return belt_config
