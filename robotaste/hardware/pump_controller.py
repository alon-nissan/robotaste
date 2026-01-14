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

import serial  # pip install pyserial
import time
import logging
from typing import Optional, Literal
from threading import RLock

# Set up logging
logger = logging.getLogger(__name__)

# Global lock to prevent multiple pumps from opening the same serial port simultaneously
# This is critical for parallel initialization - only one pump can open the port at a time
_serial_port_lock = RLock()


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
    UNIT_UL_HR = "UH"  # µL/hr
    UNIT_ML_HR = "MH"  # mL/hr

    # Status responses (per NE-4000 manual page 33)
    STATUS_INFUSING = "I"
    STATUS_WITHDRAWING = "W"
    STATUS_STOPPED = "S"
    STATUS_PAUSED = "P"
    STATUS_TIMED_PAUSE = "T"
    STATUS_USER_WAIT = "U"
    STATUS_PURGING = "X"

    def __init__(
        self,
        port: str,
        address: int = 0,
        baud: int = 19200,
        timeout: float = 5.0,
        max_retries: int = 3,
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
        self._lock = RLock()  # Thread-safe operation
        self._connected = False
        self._current_rate_ul_min: Optional[float] = None  # Track current rate for time calculations

        # Validate parameters
        if not 0 <= address <= 99:
            raise ValueError(f"Address must be 0-99, got {address}")

        valid_bauds = [300, 1200, 2400, 9600, 19200]
        if baud not in valid_bauds:
            raise ValueError(f"Baud rate must be one of {valid_bauds}, got {baud}")

    def connect(self) -> None:
        """
        Open serial port connection to pump.

        Uses a global lock to prevent multiple pumps from opening the same
        serial port simultaneously (critical for parallel initialization).

        Raises:
            PumpConnectionError: If connection fails
        """
        logger.info(f"[Pump {self.address}] Attempting connection to {self.port} at {self.baud} baud")

        with self._lock:
            if self._connected:
                logger.warning(f"[Pump {self.address}] Already connected")
                return

            try:
                # Use global lock to serialize serial port opening across all pump instances
                # This prevents "multiple access on port" errors during parallel initialization
                with _serial_port_lock:
                    self.serial = serial.Serial(
                        port=self.port,
                        baudrate=self.baud,
                        bytesize=serial.EIGHTBITS,
                        parity=serial.PARITY_NONE,
                        stopbits=serial.STOPBITS_ONE,
                        timeout=self.timeout,
                    )
                    self._connected = True
                    logger.info(f"[Pump {self.address}] ✅ Serial connection established")

                    # Small delay for pump to be ready
                    time.sleep(0.1)

                # Verify connection by stopping pump (safe command)
                # This can run outside the global lock since we now have our own connection
                self._send_command(self.CMD_STOP)
                logger.info(f"[Pump {self.address}] ✅ Connection verified (test command successful)")

            except serial.SerialException as e:
                logger.error(f"[Pump {self.address}] ❌ Connection failed: {e}", exc_info=True)
                raise PumpConnectionError(f"Failed to connect to {self.port}: {e}")
            except Exception as e:
                if self.serial:
                    self.serial.close()
                    self.serial = None
                self._connected = False
                logger.error(f"[Pump {self.address}] ❌ Connection error: {e}", exc_info=True)
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

        logger.info(f"[Pump {self.address}] Setting syringe diameter: {diameter_mm:.3f} mm")
        cmd = f"{self.CMD_DIAMETER} {diameter_mm:.3f}"
        response = self._send_command(cmd)
        logger.info(f"[Pump {self.address}] ✅ Diameter set successfully (response: {response})")

    def set_rate(
        self, rate: float, unit: Literal["UM", "MM", "UH", "MH"] = "UM"
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

        logger.info(f"[Pump {self.address}] Setting rate: {rate:.3f} {unit}")
        cmd = f"{self.CMD_RATE} {rate:.3f} {unit}"
        response = self._send_command(cmd)

        # Store rate in µL/min for time calculations
        if unit == "UM":
            self._current_rate_ul_min = rate
        elif unit == "MM":
            self._current_rate_ul_min = rate * 1000
        elif unit == "UH":
            self._current_rate_ul_min = rate / 60
        elif unit == "MH":
            self._current_rate_ul_min = (rate * 1000) / 60

        logger.info(
            f"[Pump {self.address}] ✅ Rate set: {self._current_rate_ul_min:.1f} µL/min (response: {response})"
        )

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

        logger.info(f"[Pump {self.address}] Programming volume: {volume_ul:.1f} µL ({volume_ml:.6f} mL)")
        cmd = f"{self.CMD_VOLUME} {volume_ml:.6f}"
        response = self._send_command(cmd)
        logger.info(f"[Pump {self.address}] ✅ Volume programmed (response: {response})")

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

        direction_name = "INFUSE" if direction == self.DIR_INFUSE else "WITHDRAW"
        logger.info(f"[Pump {self.address}] Setting direction to {direction_name}")
        cmd = f"{self.CMD_DIRECTION} {direction}"
        response = self._send_command(cmd)
        logger.info(f"[Pump {self.address}] ✅ Direction set (response: {response})")

    def start(self) -> None:
        """
        Start pumping with current settings.

        Raises:
            PumpCommandError: If pump rejects command
        """
        logger.info(f"[Pump {self.address}] ▶️  Starting pump motor...")
        response = self._send_command(self.CMD_RUN)
        logger.info(f"[Pump {self.address}] ✅ Pump motor running (response: {response})")

    def stop(self) -> None:
        """
        Stop pumping immediately.

        Raises:
            PumpCommandError: If pump rejects command
        """
        logger.info(f"[Pump {self.address}] ⏹️  Stopping pump motor...")
        response = self._send_command(self.CMD_STOP)
        logger.info(f"[Pump {self.address}] ✅ Pump stopped (response: {response})")

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
            self.STATUS_INFUSING: "infusing",
            self.STATUS_WITHDRAWING: "withdrawing",
            self.STATUS_STOPPED: "stopped",
            self.STATUS_PAUSED: "paused",
            self.STATUS_TIMED_PAUSE: "timed_pause",
            self.STATUS_USER_WAIT: "user_wait",
            self.STATUS_PURGING: "purging",
        }

        status_text = status_map.get(status_char, "unknown")

        return {"status": status_text, "raw_response": response}

    def is_running(self) -> bool:
        """Check if pump is currently running."""
        try:
            status = self.get_status()
            return status["status"] == "running"
        except Exception as e:
            logger.error(f"Error checking pump status: {e}")
            return False

    def dispense_volume(
        self, volume_ul: float, rate_ul_min: Optional[float] = None, wait: bool = True
    ) -> None:
        """
        Dispense a specific volume (high-level convenience method).

        Uses time-based completion: calculates expected dispense time, waits, then
        explicitly stops the pump. The NE-4000 does NOT automatically stop after
        dispensing a programmed volume - it requires an explicit STOP command.

        Args:
            volume_ul: Volume to dispense in microliters
            rate_ul_min: Pumping rate in µL/min (optional, uses current rate if None)
            wait: If True, block until dispensing completes

        Raises:
            ValueError: If rate is not specified and no current rate is set
            PumpCommandError: If any command fails
        """
        logger.info(f"[Pump {self.address}] ━━━ Starting dispense operation ━━━")
        logger.info(f"[Pump {self.address}] Volume: {volume_ul:.1f} µL")

        # Set direction to infuse
        self.set_direction(self.DIR_INFUSE)

        # Set rate if specified
        if rate_ul_min is not None:
            self.set_rate(rate_ul_min, self.UNIT_UL_MIN)

        # Ensure rate is known for time calculation
        if self._current_rate_ul_min is None:
            raise ValueError(
                "Rate must be specified either via rate_ul_min parameter or by calling set_rate() first"
            )

        # Calculate expected dispense time
        expected_time_seconds = (volume_ul / self._current_rate_ul_min) * 60.0
        wait_time = expected_time_seconds * 1.1  # 10% buffer
        logger.info(
            f"[Pump {self.address}] Expected time: {expected_time_seconds:.2f}s (with buffer: {wait_time:.2f}s)"
        )

        # Set volume
        self.set_volume(volume_ul)

        # Start pumping
        self.start()

        # Wait for completion if requested
        if wait:
            logger.info(f"[Pump {self.address}] ⏳ Dispensing... ({wait_time:.2f}s)")
            time.sleep(wait_time)

            # Explicitly stop the pump
            self.stop()
            logger.info(f"[Pump {self.address}] ✅ Dispense complete: {volume_ul:.1f} µL delivered")
            logger.info(f"[Pump {self.address}] ━━━ Operation finished ━━━")

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

            if status["status"] == "stopped":
                logger.info(f"Pump {self.address}: Completed")
                break
            elif status["status"] in ["infusing", "withdrawing"]:
                time.sleep(poll_interval)
            else:
                # Paused, unknown, or other status - log and continue polling
                logger.warning(
                    f"Pump {self.address}: Unknown status '{status['status']}' "
                    f"(raw: {status['raw_response']})"
                )
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
                    self.serial.write(full_command.encode("ascii"))
                    logger.debug(f"[Pump {self.address}] → Sending: {full_command.strip()!r}")

                    # Read response (terminated by \r or \n)
                    response = self.serial.read_until(b"\r").decode("ascii").strip()

                    if not response:
                        # Try reading with \n terminator
                        response = self.serial.read_until(b"\n").decode("ascii").strip()

                    if not response:
                        raise PumpTimeoutError(f"No response from pump {self.address}")

                    logger.debug(f"[Pump {self.address}] ← Received: {response!r}")

                    # Strip STX/ETX framing characters (0x02 start, 0x03 end)
                    if response.startswith("\x02"):
                        response = response[1:]
                    if response.endswith("\x03"):
                        response = response[:-1]

                    # Strip 2-digit address prefix if present (e.g., "00P" -> "P")
                    if len(response) >= 2 and response[0:2].isdigit():
                        response = response[2:]
                        logger.debug(f"[Pump {self.address}] After stripping frames and address: {response!r}")

                    # Check for error indicators
                    if response.startswith("?"):
                        logger.error(f"[Pump {self.address}] ❌ Pump error: {response}")
                        raise PumpCommandError(f"Pump error: {response}")

                    return response

            except (PumpTimeoutError, PumpCommandError) as e:
                last_error = e
                if attempt < attempts:
                    wait_time = 0.1 * (2 ** (attempt - 1))  # Exponential backoff
                    logger.warning(
                        f"[Pump {self.address}] Attempt {attempt}/{attempts} failed: {e}. Retrying in {wait_time:.2f}s"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"[Pump {self.address}] ❌ All {attempts} attempts failed")
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
        return (
            f"<NE4000Pump(address={self.address}, port={self.port}, status={status})>"
        )
