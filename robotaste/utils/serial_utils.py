"""
Serial port detection and validation utilities.

Provides functions to discover available serial ports, validate port access,
and test pump connectivity.
"""

import serial
import serial.tools.list_ports
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def list_available_ports() -> List[Dict[str, str]]:
    """
    Detect all available serial ports on the system.

    Returns:
        List of dictionaries with port information:
        - device: Port name (e.g., "/dev/ttyUSB0", "COM3")
        - description: Human-readable description
        - hwid: Hardware ID
    """
    ports = serial.tools.list_ports.comports()

    port_list = []
    for port in sorted(ports):
        port_info = {
            'device': port.device,
            'description': port.description,
            'hwid': port.hwid if port.hwid else "Unknown"
        }
        port_list.append(port_info)
        logger.debug(f"Found port: {port.device} - {port.description}")

    return port_list


def get_port_names() -> List[str]:
    """
    Get list of available serial port names only.

    Returns:
        List of port device names
    """
    ports = list_available_ports()
    return [port['device'] for port in ports]


def validate_port(port_name: str, baud: int = 19200, timeout: float = 2.0) -> Tuple[bool, Optional[str]]:
    """
    Check if a serial port is accessible.

    Args:
        port_name: Port device name (e.g., "/dev/ttyUSB0", "COM3")
        baud: Baud rate to test with
        timeout: Connection timeout in seconds

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        # Try to open the port
        with serial.Serial(
            port=port_name,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout
        ) as ser:
            # Port opened successfully
            logger.debug(f"Port {port_name} is accessible")
            return (True, None)

    except serial.SerialException as e:
        error_msg = f"Cannot access port {port_name}: {str(e)}"
        logger.warning(error_msg)
        return (False, error_msg)

    except Exception as e:
        error_msg = f"Unexpected error validating port {port_name}: {str(e)}"
        logger.error(error_msg)
        return (False, error_msg)


def detect_pump(
    port: str,
    address: int = 0,
    baud: int = 19200,
    timeout: float = 5.0
) -> Tuple[bool, Optional[str]]:
    """
    Test if a NE-4000 pump responds on the specified port and address.

    Args:
        port: Serial port name
        address: Pump network address (0-99)
        baud: Baud rate
        timeout: Command timeout in seconds

    Returns:
        Tuple of (detected: bool, error_message: Optional[str])
    """
    try:
        import time
        from robotaste.hardware.pump_controller import NE4000Pump, PumpConnectionError

        # Create pump instance
        pump = NE4000Pump(port=port, address=address, baud=baud, timeout=timeout)

        # Try to connect
        pump.connect()

        # Try a safe command (stop)
        pump.stop()

        # Try to get status
        status = pump.get_status()

        # Disconnect
        pump.disconnect()

        logger.info(f"Pump detected at {port} address {address}: status={status['status']}")
        return (True, None)

    except PumpConnectionError as e:
        error_msg = f"Pump connection failed: {str(e)}"
        logger.warning(error_msg)
        return (False, error_msg)

    except Exception as e:
        error_msg = f"Pump detection error: {str(e)}"
        logger.error(error_msg)
        return (False, error_msg)


def auto_detect_pumps(
    addresses: List[int] = [0, 1],
    baud: int = 19200,
    timeout: float = 3.0
) -> List[Dict[str, any]]:
    """
    Automatically detect pumps on all available serial ports.

    Tests each available port with each specified address to find connected pumps.

    Args:
        addresses: List of pump addresses to test (default [0, 1])
        baud: Baud rate
        timeout: Command timeout in seconds

    Returns:
        List of detected pump configurations:
        - port: Serial port name
        - address: Pump address
        - status: Current pump status
    """
    detected_pumps = []

    # Get all available ports
    ports = get_port_names()

    if not ports:
        logger.warning("No serial ports detected")
        return detected_pumps

    logger.info(f"Scanning {len(ports)} port(s) for pumps at addresses {addresses}")

    # Test each port with each address
    for port in ports:
        for address in addresses:
            logger.debug(f"Testing {port} address {address}")

            success, error = detect_pump(port, address, baud, timeout)

            if success:
                pump_info = {
                    'port': port,
                    'address': address,
                    'baud': baud
                }
                detected_pumps.append(pump_info)
                logger.info(f"Found pump: {pump_info}")

    return detected_pumps


def get_pump_info(port: str, address: int = 0, baud: int = 19200) -> Optional[Dict[str, any]]:
    """
    Get detailed information about a pump (if connected).

    Args:
        port: Serial port name
        address: Pump network address
        baud: Baud rate

    Returns:
        Dictionary with pump info or None if not accessible
    """
    from robotaste.hardware.pump_controller import NE4000Pump

    try:
        pump = NE4000Pump(port=port, address=address, baud=baud)
        pump.connect()

        status = pump.get_status()

        info = {
            'port': port,
            'address': address,
            'baud': baud,
            'status': status['status'],
            'connected': True
        }

        pump.disconnect()

        return info

    except Exception as e:
        logger.error(f"Error getting pump info: {e}")
        return None


def format_port_list() -> str:
    """
    Get a formatted string listing all available ports.

    Returns:
        Formatted string for display
    """
    ports = list_available_ports()

    if not ports:
        return "No serial ports detected"

    lines = ["Available serial ports:"]
    for i, port in enumerate(ports, 1):
        lines.append(f"  {i}. {port['device']} - {port['description']}")

    return "\n".join(lines)


def recommend_port() -> Optional[str]:
    """
    Recommend a likely serial port for pump connection.

    Uses heuristics to identify USB serial adapters.

    Returns:
        Recommended port name or None if no suitable port found
    """
    ports = list_available_ports()

    if not ports:
        return None

    # Heuristics for USB serial adapters
    usb_keywords = ['USB', 'UART', 'Serial', 'FTDI', 'Prolific', 'CH340']

    # First, try to find a port with USB-related keywords
    for port in ports:
        description = port['description'].upper()
        hwid = port['hwid'].upper()

        for keyword in usb_keywords:
            if keyword.upper() in description or keyword.upper() in hwid:
                logger.info(f"Recommended port: {port['device']} ({port['description']})")
                return port['device']

    # If no USB-specific port found, return first available port
    logger.info(f"No USB port found, using first available: {ports[0]['device']}")
    return ports[0]['device']
