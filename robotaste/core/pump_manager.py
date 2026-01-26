"""
Global pump manager for session-persistent connections.

This module manages NE-4000 pump connections across multiple experiment cycles.
Instead of creating and destroying pump connections every cycle, we cache them
per session and reuse them, significantly reducing cycle time.

Performance Impact:
- Without caching: ~21 seconds overhead per cycle (connect + set_diameter)
- With caching: 21 seconds on first cycle only, 0 seconds on subsequent cycles
- Savings: ~21 seconds per cycle from cycle 2 onwards (25% improvement)

Note: Parallel initialization was attempted but disabled due to serial port
conflicts with daisy-chained pumps. Future optimization: share a single serial
connection across all pumps.

Author: RoboTaste Team
Version: 1.0 (Session-persistent caching)
"""

import logging
import time
from typing import Dict, Optional, Any, Tuple, List
from robotaste.hardware.pump_controller import (
    NE4000Pump,
    PumpConnectionError,
    PumpBurstConfig,
    SeparatedBurstCommandBuilder,
)

logger = logging.getLogger(__name__)

# Global cache: {session_id: {ingredient: NE4000Pump}}
_pump_cache: Dict[str, Dict[str, NE4000Pump]] = {}

# Track which sessions have completed pump parameter initialization
_pump_init_complete: Dict[str, bool] = {}


def get_or_create_pumps(session_id: str, pump_config: Dict[str, Any]) -> Dict[str, NE4000Pump]:
    """
    Get existing pumps for session or create new ones.

    This function checks if pumps are already initialized for the given session.
    If they exist and are still connected, they are reused. Otherwise, new
    pumps are initialized.

    Args:
        session_id: Session identifier
        pump_config: Pump configuration from protocol with keys:
            - serial_port: Serial port path
            - baud_rate: Baud rate (default 19200)
            - pumps: List of pump configurations with:
                - address: Pump network address
                - ingredient: Ingredient name
                - syringe_diameter_mm: Syringe diameter

    Returns:
        Dict of {ingredient: NE4000Pump} instances

    Example:
        >>> pump_config = {
        ...     "serial_port": "/dev/cu.PL2303G-USBtoUART120",
        ...     "baud_rate": 19200,
        ...     "pumps": [
        ...         {"address": 0, "ingredient": "Sugar", "syringe_diameter_mm": 26.7},
        ...         {"address": 1, "ingredient": "Water", "syringe_diameter_mm": 26.7}
        ...     ]
        ... }
        >>> pumps = get_or_create_pumps("session-123", pump_config)
        >>> pumps.keys()
        dict_keys(['Sugar', 'Water'])
    """
    if session_id in _pump_cache:
        # Verify pumps are still connected
        cached_pumps = _pump_cache[session_id]
        all_connected = all(p.is_connected() for p in cached_pumps.values())

        if all_connected:
            logger.info(f"Reusing existing pump connections for session {session_id} ({len(cached_pumps)} pumps)")
            return cached_pumps
        else:
            logger.warning(f"Cached pumps for session {session_id} are disconnected, reinitializing")
            cleanup_pumps(session_id)

    # Initialize new pumps
    logger.info(f"Initializing new pumps for session {session_id}")
    pumps = _initialize_pumps(pump_config)
    _pump_cache[session_id] = pumps
    logger.info(f"Cached {len(pumps)} pump(s) for session {session_id}")

    return pumps


def _initialize_pumps(pump_config: Dict[str, Any]) -> Dict[str, NE4000Pump]:
    """
    Initialize pumps with configuration sequentially.

    Creates NE4000Pump instances, connects to them, and sets syringe diameter.
    Pumps are initialized one at a time to avoid serial port conflicts in
    daisy-chain configurations.

    This is an internal function called by get_or_create_pumps().

    Args:
        pump_config: Pump configuration dictionary

    Returns:
        Dict of {ingredient: NE4000Pump} instances

    Raises:
        PumpConnectionError: If pump connection fails
        ValueError: If configuration is invalid
    """
    serial_port = pump_config.get("serial_port")
    baud_rate = pump_config.get("baud_rate", 19200)
    pump_configs = pump_config.get("pumps", [])
    dispensing_rate = pump_config.get("dispensing_rate_ul_min", 2000)
    use_burst_mode = pump_config.get("use_burst_mode", False)

    if not serial_port:
        raise ValueError("serial_port is required in pump_config")

    if not pump_configs:
        raise ValueError("No pumps configured in pump_config")

    def init_single_pump(
        cfg: Dict[str, Any],
        configure_diameter: bool,
    ) -> Tuple[str, Optional[NE4000Pump], Optional[Exception]]:
        """
        Thread worker to initialize one pump.

        Args:
            cfg: Pump configuration dict

        Returns:
            Tuple of (ingredient, pump, error)
            - If successful: (ingredient, pump, None)
            - If failed: (ingredient, None, exception)
        """
        address = cfg.get("address")
        ingredient = cfg.get("ingredient") or "unknown"
        diameter = cfg.get("syringe_diameter_mm")

        try:
            if address is None:
                raise ValueError(f"Pump configuration missing 'address' for {ingredient}")
            if ingredient == "unknown":
                raise ValueError(
                    f"Pump configuration missing 'ingredient' for address {address}"
                )
            if not diameter:
                raise ValueError(f"Pump configuration missing 'syringe_diameter_mm' for {ingredient}")

            logger.info(f"  🔧 [Thread] Initializing Pump {address} ({ingredient}, {diameter}mm diameter)...")

            # Create pump instance with 2-second timeout (reduced from 5s default)
            pump = NE4000Pump(
                port=serial_port,
                address=address,
                baud=baud_rate,
                timeout=2.0
            )

            # Connect and configure
            pump.connect()
            if configure_diameter:
                pump.set_diameter(diameter)

            logger.info(f"  [Thread] Pump {address} ({ingredient}) connected and configured")

            return (ingredient, pump, None)

        except Exception as e:
            logger.error(f"  ❌ [Thread] Failed to initialize Pump {address} ({ingredient}): {e}")
            return (ingredient, None, e)

    # Initialize pumps sequentially to avoid serial port conflicts
    # NOTE: Parallel initialization is disabled because daisy-chained pumps
    # cannot have multiple simultaneous Serial() connections to the same port.
    # Future optimization: share a single serial connection across all pumps.
    logger.info(f"  Initializing {len(pump_configs)} pumps sequentially...")

    pumps = {}
    errors = []

    # Determine if pumps are burst-compatible (all addresses 0-9)
    burst_compatible = use_burst_mode and all(
        cfg.get("address", 99) <= 9 for cfg in pump_configs
    )

    for cfg in pump_configs:
        # When burst mode is enabled, skip individual diameter configuration
        # (will be configured during actual dispensing via burst command)
        configure_diameter = not burst_compatible
        ingredient, pump, error = init_single_pump(cfg, configure_diameter)

        if error:
            error_name = ingredient or "unknown"
            errors.append(f"{error_name}: {error}")
        elif pump and ingredient:
            pumps[ingredient] = pump
            # Burst configuration removed - will happen during dispensing phase

    # If any pump failed, raise combined error
    if errors:
        error_msg = "Failed to initialize pumps:\n" + "\n".join(errors)
        logger.error(error_msg)
        raise PumpConnectionError(error_msg)

    # Burst configuration removed - will happen during dispensing phase
    # If burst mode is disabled, diameters are already set via init_single_pump
    if burst_compatible:
        logger.info("  ⚡ Burst mode enabled - diameter will be configured during dispensing")
    else:
        logger.info("  Individual diameters configured during initialization")

    logger.info(f"  All {len(pumps)} pumps connected successfully")

    return pumps


def cleanup_pumps(session_id: str) -> None:
    """
    Disconnect and remove pumps for a session.

    Should be called when a session completes to free hardware resources.

    Args:
        session_id: Session identifier

    Example:
        >>> cleanup_pumps("session-123")
        # Disconnects all pumps and removes from cache
    """
    if session_id not in _pump_cache:
        logger.debug(f"No cached pumps to cleanup for session {session_id}")
        return

    pumps = _pump_cache[session_id]
    logger.info(f"Cleaning up {len(pumps)} pump(s) for session {session_id}")

    for ingredient, pump in pumps.items():
        try:
            if pump.is_connected():
                pump.disconnect()
                logger.debug(f"  Disconnected pump: {ingredient}")
        except Exception as e:
            logger.warning(f"  Error disconnecting pump {ingredient}: {e}")

    del _pump_cache[session_id]
    
    # Also clear init state
    if session_id in _pump_init_complete:
        del _pump_init_complete[session_id]
    
    logger.info(f"Cleaned up pumps for session {session_id}")


def get_cached_pump_count() -> int:
    """
    Get the number of sessions with cached pumps.

    Useful for monitoring and debugging.

    Returns:
        Number of sessions in cache

    Example:
        >>> count = get_cached_pump_count()
        >>> print(f"Active pump sessions: {count}")
    """
    return len(_pump_cache)


def get_session_pump_info(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get information about cached pumps for a session.

    Args:
        session_id: Session identifier

    Returns:
        Dict with pump info or None if no cached pumps

    Example:
        >>> info = get_session_pump_info("session-123")
        >>> info['pump_count']
        2
        >>> info['ingredients']
        ['Sugar', 'Water']
    """
    if session_id not in _pump_cache:
        return None

    pumps = _pump_cache[session_id]

    return {
        "session_id": session_id,
        "pump_count": len(pumps),
        "ingredients": list(pumps.keys()),
        "all_connected": all(p.is_connected() for p in pumps.values()),
    }


def cleanup_all_pumps() -> None:
    """
    Cleanup all cached pumps across all sessions.

    Emergency cleanup function. Use with caution as it will disconnect
    pumps for all active sessions.

    Example:
        >>> cleanup_all_pumps()
        # Disconnects and clears all cached pumps
    """
    session_ids = list(_pump_cache.keys())

    if not session_ids:
        logger.debug("No pumps to cleanup")
        return

    logger.warning(f"Cleaning up ALL cached pumps ({len(session_ids)} sessions)")

    for session_id in session_ids:
        cleanup_pumps(session_id)

    logger.info("All pumps cleaned up")


def is_pump_initialized(session_id: str) -> bool:
    """
    Check if pump parameters have been initialized for a session.
    
    Args:
        session_id: Session identifier
        
    Returns:
        True if DIA/RAT/DIR/VOL unit have been configured
    """
    return _pump_init_complete.get(session_id, False)


def _build_burst_configs(pump_config: Dict[str, Any]) -> List[PumpBurstConfig]:
    """
    Build PumpBurstConfig list from pump_config dictionary.
    
    Args:
        pump_config: Pump configuration from protocol
        
    Returns:
        List of PumpBurstConfig for burst command building
    """
    pump_configs = pump_config.get("pumps", [])
    dispensing_rate = pump_config.get("dispensing_rate_ul_min", 2000)
    
    configs = []
    for pump_cfg in pump_configs:
        address = pump_cfg.get("address")
        if address is None:
            continue
            
        configs.append(PumpBurstConfig(
            address=address,
            rate_ul_min=dispensing_rate,
            volume_ul=0,  # Will be set per-cycle
            diameter_mm=pump_cfg.get("syringe_diameter_mm", 26.7),
            volume_unit=pump_cfg.get("volume_unit", "ML"),
            direction="INF"
        ))
    
    return configs


def initialize_pump_parameters(
    session_id: str,
    pump_config: Dict[str, Any],
    command_delay: float = 0.3
) -> bool:
    """
    Send one-time pump configuration (DIA, RAT, VOL unit, DIR).
    
    Called once per session when moderator clicks "Start Experiment".
    Uses separated burst commands to ensure each parameter is applied correctly.
    
    Args:
        session_id: Session identifier
        pump_config: Pump configuration from protocol
        command_delay: Delay between commands in seconds (default 0.3s)
        
    Returns:
        True if initialization succeeded
        
    Raises:
        PumpConnectionError: If pump connection fails
    """
    if _pump_init_complete.get(session_id, False):
        logger.info(f"Pump parameters already initialized for session {session_id}")
        return True
    
    logger.info(f"🔧 Initializing pump parameters for session {session_id}...")
    
    # Get or create pumps (this handles connection)
    pumps = get_or_create_pumps(session_id, pump_config)
    
    if not pumps:
        raise PumpConnectionError("No pumps available for initialization")
    
    # Use any pump to send burst commands (they share serial port)
    any_pump = next(iter(pumps.values()))
    
    # Build burst configs
    configs = _build_burst_configs(pump_config)
    
    if not configs:
        raise ValueError("No pump configurations found")
    
    builder = SeparatedBurstCommandBuilder
    
    try:
        # 1. Set diameters
        logger.info(f"  📏 Setting diameters for {len(configs)} pumps...")
        cmd = builder.build_diameter_command(configs)
        any_pump._send_burst_command(cmd)
        time.sleep(command_delay)
        
        # 2. Set rates
        logger.info(f"  ⚡ Setting rates...")
        cmd = builder.build_rate_command(configs)
        any_pump._send_burst_command(cmd)
        time.sleep(command_delay)
        
        # 3. Set volume units
        logger.info(f"  📐 Setting volume units...")
        cmd = builder.build_volume_unit_command(configs)
        any_pump._send_burst_command(cmd)
        time.sleep(command_delay)
        
        # 4. Set directions
        logger.info(f"  ➡️ Setting directions...")
        cmd = builder.build_direction_command(configs)
        any_pump._send_burst_command(cmd)
        time.sleep(command_delay)
        
        # 5. Verify settings
        logger.info(f"  🔍 Verifying parameters...")
        verify_cmd = builder.build_verification_command(configs, "DIA")
        any_pump._send_burst_command(verify_cmd)
        time.sleep(command_delay)
        
        verify_cmd = builder.build_verification_command(configs, "RAT")
        any_pump._send_burst_command(verify_cmd)
        
        # Mark as initialized
        _pump_init_complete[session_id] = True
        logger.info(f"✅ Pump parameters initialized successfully for session {session_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Pump initialization failed: {e}")
        raise


def send_volume_and_run(
    session_id: str,
    pump_config: Dict[str, Any],
    volumes: Dict[str, float],
    command_delay: float = 0.2
) -> bool:
    """
    Send volume values and run command for a dispensing cycle.
    
    Called once per cycle after pump parameters are initialized.
    Only sends VOL values and RUN command (DIA/RAT/DIR already set).
    
    Args:
        session_id: Session identifier
        pump_config: Pump configuration from protocol
        volumes: Dict of {ingredient: volume_ul}
        command_delay: Delay between commands in seconds
        
    Returns:
        True if commands sent successfully
    """
    if session_id not in _pump_cache:
        raise PumpConnectionError(f"No pumps cached for session {session_id}")
    
    pumps = _pump_cache[session_id]
    any_pump = next(iter(pumps.values()))
    
    # Build configs with actual volumes
    pump_configs = pump_config.get("pumps", [])
    dispensing_rate = pump_config.get("dispensing_rate_ul_min", 2000)
    
    configs = []
    for pump_cfg in pump_configs:
        ingredient = pump_cfg.get("ingredient")
        address = pump_cfg.get("address")
        
        if address is None or ingredient is None:
            continue
            
        volume_ul = volumes.get(ingredient, 0)
        if volume_ul < 0.001:  # Skip ~0 volumes
            continue
            
        configs.append(PumpBurstConfig(
            address=address,
            rate_ul_min=dispensing_rate,
            volume_ul=volume_ul,
            diameter_mm=pump_cfg.get("syringe_diameter_mm", 26.7),
            volume_unit=pump_cfg.get("volume_unit", "ML"),
            direction="INF"
        ))
    
    if not configs:
        logger.warning("No volumes to dispense (all ~0)")
        return True
    
    builder = SeparatedBurstCommandBuilder
    
    # 1. Set volumes
    logger.info(f"  💧 Setting volumes for {len(configs)} pumps...")
    cmd = builder.build_volume_value_command(configs)
    any_pump._send_burst_command(cmd)
    time.sleep(command_delay)
    
    # 2. Verify volumes
    logger.info(f"  🔍 Verifying volumes...")
    verify_cmd = builder.build_verification_command(configs, "VOL")
    any_pump._send_burst_command(verify_cmd)
    time.sleep(command_delay)
    
    # 3. Run
    logger.info(f"  🚀 Starting pumps...")
    cmd = builder.build_run_command(configs)
    any_pump._send_burst_command(cmd)
    
    return True
