"""
New Era NE-4000 Syringe Pump Controller

Provides a Python interface for controlling NE-4000 programmable syringe pumps
via RS-232 serial communication.

Protocol details from NE-4000 User Manual:
- Communication: RS-232, 8N1 data frame
- Baud rates: 300, 1200, 2400, 9600, 19200
- Network addressing: 0-99 for multi-pump setups
- Safe mode with CRC checking and timeout detection
"""

import serial
import time
import logging
from typing import Optional, Literal
from threading import Lock

# Set up logging
logger = logging.getLogger(__name__)


class PumpConnectionError(Exception):
    """Raised when serial port connection fails."""
    pass


class PumpCommandError(Exception):
    """Raised when pump returns an error response."""
    pass


class PumpTimeoutError(Exception):
    """Raised when pump doesn't respond within timeout period."""
    pass


class NE4000Pump:
    """
    Interface for New Era NE-4000 programmable syringe pump.

    Supports network addressing for multi-pump setups on a single serial port.
    All commands are sent with automatic retry logic and error handling.

    Example usage:
        pump = NE4000Pump(port="/dev/ttyUSB0", address=0)
        pump.connect()
        pump.set_diameter(14.567)  # BD 10mL syringe
        pump.set_rate(2000, "UM")  # 2000 µL/min
        pump.dispense_volume(125.5)  # Dispense 125.5 µL
        status = pump.get_status()
        pump.disconnect()
    """

    # Command constants
    CMD_DIAMETER = "DIA"
    CMD_RATE = "RAT"
    CMD_VOLUME = "VOL"
    CMD_DIRECTION = "DIR"
    CMD_RUN = "RUN"
    CMD_STOP = "STP"
    CMD_ADDRESS = "ADR"

    # Direction constants
    DIR_INFUSE = "INF"
    DIR_WITHDRAW = "WDR"

    # Rate units
    UNIT_UL_MIN = "UM"  # µL/min
    UNIT_ML_MIN = "MM"  # mL/min
    UNIT_UL_HR = "UH"   # µL/hr
    UNIT_ML_HR = "MH"   # mL/hr

    # Status responses
    STATUS_IDLE = ":"
    STATUS_RUNNING = ">"
    STATUS_STALLED = "*"
    STATUS_PAUSED = "T"

    def __init__(
        self,
        port: str,
        address: int = 0,
        baud: int = 19200,
        timeout: float = 5.0,
        max_retries: int = 3
    ):
        """
        Initialize pump controller.

        Args:
            port: Serial port name (e.g., "/dev/ttyUSB0", "COM3")
            address: Network address (0-99) for multi-pump setups
            baud: Baud rate (300, 1200, 2400, 9600, or 19200)
            timeout: Command timeout in seconds
            max_retries: Number of retry attempts for failed commands
        """
        self.port = port
        self.address = address
        self.baud = baud
        self.timeout = timeout
        self.max_retries = max_retries

        self.serial: Optional[serial.Serial] = None
        self._lock = Lock()  # Thread-safe operation
        self._connected = False

        # Validate parameters
        if not 0 <= address <= 99:
            raise ValueError(f"Address must be 0-99, got {address}")

        valid_bauds = [300, 1200, 2400, 9600, 19200]
        if baud not in valid_bauds:
            raise ValueError(f"Baud rate must be one of {valid_bauds}, got {baud}")

    def connect(self) -> None:
        """
        Open serial port connection to pump.

        Raises:
            PumpConnectionError: If connection fails
        """
        with self._lock:
            if self._connected:
                logger.warning(f"Pump {self.address} already connected")
                return

            try:
                self.serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout
                )
                self._connected = True
                logger.info(f"Connected to pump {self.address} on {self.port} at {self.baud} baud")

                # Small delay for pump to be ready
                time.sleep(0.1)

                # Verify connection by stopping pump (safe command)
                self._send_command(self.CMD_STOP)

            except serial.SerialException as e:
                raise PumpConnectionError(f"Failed to connect to {self.port}: {e}")
            except Exception as e:
                if self.serial:
                    self.serial.close()
                    self.serial = None
                self._connected = False
                raise PumpConnectionError(f"Connection error: {e}")

    def disconnect(self) -> None:
        """Close serial port connection."""
        with self._lock:
            if self.serial and self._connected:
                try:
                    # Safety: stop pump before disconnecting
                    self._send_command(self.CMD_STOP, retry=False)
                except Exception as e:
                    logger.warning(f"Error stopping pump before disconnect: {e}")

                self.serial.close()
                self._connected = False
                logger.info(f"Disconnected from pump {self.address}")

    def is_connected(self) -> bool:
        """Check if pump is connected."""
        return self._connected and self.serial is not None and self.serial.is_open

    def set_diameter(self, diameter_mm: float) -> None:
        """
        Set syringe diameter.

        Args:
            diameter_mm: Syringe inner diameter in millimeters (0.1 - 50.0)

        Raises:
            ValueError: If diameter out of range
            PumpCommandError: If pump rejects command
        """
        if not 0.1 <= diameter_mm <= 50.0:
            raise ValueError(f"Diameter must be 0.1-50.0 mm, got {diameter_mm}")

        cmd = f"{self.CMD_DIAMETER} {diameter_mm:.3f}"
        self._send_command(cmd)
        logger.info(f"Pump {self.address}: Set diameter to {diameter_mm:.3f} mm")

    def set_rate(
        self,
        rate: float,
        unit: Literal["UM", "MM", "UH", "MH"] = "UM"
    ) -> None:
        """
        Set pumping rate.

        Args:
            rate: Pumping rate value
            unit: Rate unit - "UM" (µL/min), "MM" (mL/min), "UH" (µL/hr), "MH" (mL/hr)

        Raises:
            ValueError: If rate is negative or unit invalid
            PumpCommandError: If pump rejects command
        """
        if rate < 0:
            raise ValueError(f"Rate must be positive, got {rate}")

        valid_units = ["UM", "MM", "UH", "MH"]
        if unit not in valid_units:
            raise ValueError(f"Unit must be one of {valid_units}, got {unit}")

        cmd = f"{self.CMD_RATE} {rate:.3f} {unit}"
        self._send_command(cmd)
        logger.info(f"Pump {self.address}: Set rate to {rate:.3f} {unit}")

    def set_volume(self, volume_ul: float) -> None:
        """
        Set volume to dispense (does not start pumping).

        Args:
            volume_ul: Volume in microliters

        Raises:
            ValueError: If volume is negative
            PumpCommandError: If pump rejects command
        """
        if volume_ul < 0:
            raise ValueError(f"Volume must be positive, got {volume_ul}")

        # Convert µL to mL for pump command
        volume_ml = volume_ul / 1000.0

        cmd = f"{self.CMD_VOLUME} {volume_ml:.6f}"
        self._send_command(cmd)
        logger.info(f"Pump {self.address}: Set volume to {volume_ul:.3f} µL ({volume_ml:.6f} mL)")

    def set_direction(self, direction: Literal["INF", "WDR"]) -> None:
        """
        Set pumping direction.

        Args:
            direction: "INF" for infuse (dispense), "WDR" for withdraw

        Raises:
            ValueError: If direction invalid
            PumpCommandError: If pump rejects command
        """
        if direction not in [self.DIR_INFUSE, self.DIR_WITHDRAW]:
            raise ValueError(f"Direction must be 'INF' or 'WDR', got {direction}")

        cmd = f"{self.CMD_DIRECTION} {direction}"
        self._send_command(cmd)
        logger.info(f"Pump {self.address}: Set direction to {direction}")

    def start(self) -> None:
        """
        Start pumping with current settings.

        Raises:
            PumpCommandError: If pump rejects command
        """
        self._send_command(self.CMD_RUN)
        logger.info(f"Pump {self.address}: Started pumping")

    def stop(self) -> None:
        """
        Stop pumping immediately.

        Raises:
            PumpCommandError: If pump rejects command
        """
        self._send_command(self.CMD_STOP)
        logger.info(f"Pump {self.address}: Stopped")

    def get_status(self) -> dict:
        """
        Query current pump status.

        Returns:
            dict with keys:
                - status: "idle", "running", "stalled", or "paused"
                - raw_response: Raw status character from pump

        Raises:
            PumpCommandError: If communication fails
        """
        # Send empty command to get status prompt
        response = self._send_command("")

        # Parse status character
        status_char = response[0] if response else "?"

        status_map = {
            self.STATUS_IDLE: "idle",
            self.STATUS_RUNNING: "running",
            self.STATUS_STALLED: "stalled",
            self.STATUS_PAUSED: "paused",
        }

        status_text = status_map.get(status_char, "unknown")

        return {
            "status": status_text,
            "raw_response": response
        }

    def is_running(self) -> bool:
        """Check if pump is currently running."""
        try:
            status = self.get_status()
            return status["status"] == "running"
        except Exception as e:
            logger.error(f"Error checking pump status: {e}")
            return False

    def dispense_volume(
        self,
        volume_ul: float,
        rate_ul_min: Optional[float] = None,
        wait: bool = True
    ) -> None:
        """
        Dispense a specific volume (high-level convenience method).

        This method combines multiple commands:
        1. Set direction to infuse
        2. Set rate (if specified)
        3. Set volume
        4. Start pumping
        5. Optionally wait for completion

        Args:
            volume_ul: Volume to dispense in microliters
            rate_ul_min: Pumping rate in µL/min (optional, uses current rate if None)
            wait: If True, block until dispensing completes

        Raises:
            PumpCommandError: If any command fails
        """
        logger.info(f"Pump {self.address}: Dispensing {volume_ul:.3f} µL")

        # Set direction to infuse
        self.set_direction(self.DIR_INFUSE)

        # Set rate if specified
        if rate_ul_min is not None:
            self.set_rate(rate_ul_min, self.UNIT_UL_MIN)

        # Set volume
        self.set_volume(volume_ul)

        # Start pumping
        self.start()

        # Wait for completion if requested
        if wait:
            self.wait_until_complete()

    def wait_until_complete(self, poll_interval: float = 0.5) -> None:
        """
        Block until pump completes current operation.

        Args:
            poll_interval: Time in seconds between status checks

        Raises:
            PumpCommandError: If pump stalls or errors
        """
        logger.debug(f"Pump {self.address}: Waiting for completion")

        while True:
            status = self.get_status()

            if status["status"] == "idle":
                logger.info(f"Pump {self.address}: Completed")
                break
            elif status["status"] == "stalled":
                raise PumpCommandError(f"Pump {self.address} stalled - check syringe")
            elif status["status"] == "running":
                time.sleep(poll_interval)
            else:
                # Paused or unknown - continue polling
                time.sleep(poll_interval)

    def _send_command(self, command: str, retry: bool = True) -> str:
        """
        Send command to pump with retry logic.

        Args:
            command: Command string (without address prefix or terminator)
            retry: Whether to retry on failure

        Returns:
            Response from pump (with prompt character stripped)

        Raises:
            PumpConnectionError: If not connected
            PumpTimeoutError: If pump doesn't respond
            PumpCommandError: If pump returns error
        """
        if not self.is_connected():
            raise PumpConnectionError("Not connected to pump")

        # Format command with network address
        if self.address > 0:
            full_command = f"{self.address:02d}{command}\r"
        else:
            full_command = f"{command}\r"

        attempts = self.max_retries if retry else 1
        last_error = None

        for attempt in range(1, attempts + 1):
            try:
                with self._lock:
                    # Clear input buffer
                    self.serial.reset_input_buffer()

                    # Send command
                    self.serial.write(full_command.encode('ascii'))
                    logger.debug(f"Sent: {full_command.strip()}")

                    # Read response (terminated by \r or \n)
                    response = self.serial.read_until(b'\r').decode('ascii').strip()

                    if not response:
                        # Try reading with \n terminator
                        response = self.serial.read_until(b'\n').decode('ascii').strip()

                    if not response:
                        raise PumpTimeoutError(f"No response from pump {self.address}")

                    logger.debug(f"Received: {response}")

                    # Check for error indicators
                    if response.startswith("?"):
                        raise PumpCommandError(f"Pump error: {response}")

                    # Strip prompt character (first char)
                    if len(response) > 0 and response[0] in [':', '>', '*', 'T']:
                        response = response[1:]

                    return response

            except (PumpTimeoutError, PumpCommandError) as e:
                last_error = e
                if attempt < attempts:
                    wait_time = 0.1 * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(f"Attempt {attempt}/{attempts} failed: {e}. Retrying in {wait_time:.2f}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"All {attempts} attempts failed")
                    raise

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {e}")
                raise PumpCommandError(f"Command failed: {e}")

        # Should not reach here, but just in case
        if last_error:
            raise last_error

        return ""

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False

    def __repr__(self):
        """String representation."""
        status = "connected" if self.is_connected() else "disconnected"
        return f"<NE4000Pump(address={self.address}, port={self.port}, status={status})>"
