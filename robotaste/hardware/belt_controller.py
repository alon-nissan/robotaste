"""
Conveyor Belt Controller for RoboTaste

Provides a Python interface for controlling the conveyor belt system
via Arduino serial communication.

The belt positions cups under the pump spout for dispensing, performs
mixing via oscillation, then delivers cups to the display area.

Physical Model:
    [DISPLAY AREA] ← cup1 ← [SPOUT] ← cup2 ← cup3 ← ... (queue)

Protocol (proposed - will be finalized when Arduino firmware is ready):
    Commands (software → Arduino):
        MOVE_TO_SPOUT      - Advance belt to position next cup at spout
        MOVE_TO_DISPLAY    - Move current cup from spout to display
        MIX <count>        - Perform back-and-forth oscillations
        STOP               - Emergency stop
        STATUS             - Query current state

    Responses (Arduino → software):
        OK                 - Command completed
        AT_SPOUT           - Cup is at spout position
        AT_DISPLAY         - Cup is at display position
        MIXING             - Currently mixing
        ERROR:<msg>        - Error occurred

Author: RoboTaste Team
Version: 1.0
"""

import serial
import time
import logging
from typing import Optional, Literal
from threading import RLock
from enum import Enum

logger = logging.getLogger(__name__)

# Global lock to prevent multiple belt controllers from conflicting
_belt_serial_lock = RLock()


class BeltConnectionError(Exception):
    """Raised when serial port connection fails."""
    pass


class BeltCommandError(Exception):
    """Raised when belt controller returns an error response."""
    pass


class BeltTimeoutError(Exception):
    """Raised when belt doesn't respond within timeout period."""
    pass


class BeltPosition(Enum):
    """Belt anchor positions."""
    SPOUT = "spout"
    DISPLAY = "display"
    UNKNOWN = "unknown"
    MOVING = "moving"


class BeltStatus(Enum):
    """Belt operational status."""
    IDLE = "idle"
    MOVING = "moving"
    MIXING = "mixing"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class ConveyorBelt:
    """
    Controller for the conveyor belt system.

    Provides methods for:
    - Moving cups to spout/display positions
    - Performing mixing oscillations
    - Querying status

    Args:
        port: Serial port (e.g., '/dev/tty.usbmodem14101')
        baud: Baud rate (default 9600)
        timeout: Serial read timeout in seconds
        mock_mode: If True, simulate hardware without actual serial connection

    Example:
        >>> belt = ConveyorBelt('/dev/tty.usbmodem14101')
        >>> belt.connect()
        >>> belt.move_to_spout()
        >>> belt.mix(oscillations=5)
        >>> belt.move_to_display()
        >>> belt.disconnect()
    """

    # Command strings (will be finalized when Arduino firmware is ready)
    CMD_MOVE_TO_SPOUT = "MOVE_TO_SPOUT"
    CMD_MOVE_TO_DISPLAY = "MOVE_TO_DISPLAY"
    CMD_MIX = "MIX"
    CMD_STOP = "STOP"
    CMD_STATUS = "STATUS"

    # Response strings
    RESP_OK = "OK"
    RESP_AT_SPOUT = "AT_SPOUT"
    RESP_AT_DISPLAY = "AT_DISPLAY"
    RESP_MIXING = "MIXING"
    RESP_ERROR_PREFIX = "ERROR:"

    def __init__(
        self,
        port: str,
        baud: int = 9600,
        timeout: float = 10.0,
        mock_mode: bool = False
    ):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.mock_mode = mock_mode

        self._serial: Optional[serial.Serial] = None
        self._connected = False
        self._current_position = BeltPosition.UNKNOWN
        self._status = BeltStatus.DISCONNECTED

        # Mock mode state
        self._mock_position = BeltPosition.SPOUT

    def connect(self) -> None:
        """
        Open serial connection to the belt controller.

        Raises:
            BeltConnectionError: If connection fails
        """
        if self.mock_mode:
            logger.info("Belt controller running in MOCK mode")
            self._connected = True
            self._status = BeltStatus.IDLE
            return

        with _belt_serial_lock:
            try:
                logger.info(f"Connecting to belt controller on {self.port} at {self.baud} baud")

                self._serial = serial.Serial(
                    port=self.port,
                    baudrate=self.baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.timeout,
                    write_timeout=self.timeout
                )

                # Wait for Arduino to reset after serial connection
                time.sleep(2.0)

                # Flush any startup messages
                self._serial.reset_input_buffer()
                self._serial.reset_output_buffer()

                self._connected = True
                self._status = BeltStatus.IDLE

                # Query initial status
                try:
                    self._update_status()
                except Exception as e:
                    logger.warning(f"Could not query initial status: {e}")

                logger.info(f"Belt controller connected on {self.port}")

            except serial.SerialException as e:
                self._connected = False
                self._status = BeltStatus.DISCONNECTED
                raise BeltConnectionError(f"Failed to connect to belt on {self.port}: {e}")

    def disconnect(self) -> None:
        """Close serial connection."""
        if self.mock_mode:
            self._connected = False
            self._status = BeltStatus.DISCONNECTED
            logger.info("Belt controller (mock) disconnected")
            return

        if self._serial and self._serial.is_open:
            try:
                self._serial.close()
                logger.info("Belt controller disconnected")
            except Exception as e:
                logger.warning(f"Error closing belt serial port: {e}")

        self._connected = False
        self._status = BeltStatus.DISCONNECTED

    def is_connected(self) -> bool:
        """Check if belt is connected."""
        if self.mock_mode:
            return self._connected

        return self._connected and self._serial is not None and self._serial.is_open

    def move_to_spout(self, wait: bool = True) -> bool:
        """
        Advance belt to position next cup under the spout.

        Args:
            wait: If True, block until movement completes

        Returns:
            True if successful

        Raises:
            BeltCommandError: If movement fails
            BeltTimeoutError: If movement times out
        """
        logger.info("Moving cup to spout position")

        if self.mock_mode:
            time.sleep(0.5)  # Simulate movement time
            self._mock_position = BeltPosition.SPOUT
            self._current_position = BeltPosition.SPOUT
            logger.info("Cup at spout (mock)")
            return True

        self._send_command(self.CMD_MOVE_TO_SPOUT)

        if wait:
            return self._wait_for_position(BeltPosition.SPOUT)

        return True

    def move_to_display(self, wait: bool = True) -> bool:
        """
        Move current cup from spout to display area.

        Args:
            wait: If True, block until movement completes

        Returns:
            True if successful

        Raises:
            BeltCommandError: If movement fails
            BeltTimeoutError: If movement times out
        """
        logger.info("Moving cup to display position")

        if self.mock_mode:
            time.sleep(0.5)  # Simulate movement time
            self._mock_position = BeltPosition.DISPLAY
            self._current_position = BeltPosition.DISPLAY
            logger.info("Cup at display (mock)")
            return True

        self._send_command(self.CMD_MOVE_TO_DISPLAY)

        if wait:
            return self._wait_for_position(BeltPosition.DISPLAY)

        return True

    def mix(self, oscillations: int = 5, wait: bool = True) -> bool:
        """
        Perform mixing by oscillating belt back and forth.

        Args:
            oscillations: Number of back-and-forth movements
            wait: If True, block until mixing completes

        Returns:
            True if successful

        Raises:
            BeltCommandError: If mixing fails
            BeltTimeoutError: If mixing times out
        """
        if oscillations <= 0:
            logger.warning("Mix called with oscillations <= 0, skipping")
            return True

        logger.info(f"Starting mixing with {oscillations} oscillations")

        if self.mock_mode:
            # Simulate mixing time (~0.5s per oscillation)
            time.sleep(oscillations * 0.5)
            logger.info(f"Mixing complete (mock): {oscillations} oscillations")
            return True

        self._send_command(f"{self.CMD_MIX} {oscillations}")

        if wait:
            return self._wait_for_mixing_complete(oscillations)

        return True

    def stop(self) -> None:
        """Emergency stop - halt all belt movement immediately."""
        logger.warning("Emergency stop requested")

        if self.mock_mode:
            self._status = BeltStatus.IDLE
            return

        try:
            self._send_command(self.CMD_STOP)
        except Exception as e:
            logger.error(f"Error sending stop command: {e}")

        self._status = BeltStatus.IDLE

    def get_status(self) -> BeltStatus:
        """Get current belt status."""
        if self.mock_mode:
            return self._status

        try:
            self._update_status()
        except Exception as e:
            logger.warning(f"Could not update status: {e}")

        return self._status

    def get_position(self) -> BeltPosition:
        """Get current cup position."""
        if self.mock_mode:
            return self._mock_position

        return self._current_position

    def _send_command(self, command: str) -> str:
        """
        Send command to belt controller and read response.

        Args:
            command: Command string to send

        Returns:
            Response string from controller

        Raises:
            BeltConnectionError: If not connected
            BeltCommandError: If controller returns error
            BeltTimeoutError: If no response within timeout
        """
        if not self.is_connected():
            raise BeltConnectionError("Belt not connected")

        with _belt_serial_lock:
            try:
                # Send command with newline terminator
                cmd_bytes = f"{command}\n".encode('utf-8')
                self._serial.write(cmd_bytes)
                self._serial.flush()

                logger.debug(f"Sent: {command}")

                # Read response
                response = self._serial.readline().decode('utf-8').strip()

                if not response:
                    raise BeltTimeoutError(f"No response to command: {command}")

                logger.debug(f"Received: {response}")

                # Check for error response
                if response.startswith(self.RESP_ERROR_PREFIX):
                    error_msg = response[len(self.RESP_ERROR_PREFIX):]
                    raise BeltCommandError(f"Belt error: {error_msg}")

                return response

            except serial.SerialException as e:
                self._status = BeltStatus.ERROR
                raise BeltConnectionError(f"Serial error: {e}")

    def _update_status(self) -> None:
        """Query and update current status from controller."""
        response = self._send_command(self.CMD_STATUS)

        if response == self.RESP_AT_SPOUT:
            self._current_position = BeltPosition.SPOUT
            self._status = BeltStatus.IDLE
        elif response == self.RESP_AT_DISPLAY:
            self._current_position = BeltPosition.DISPLAY
            self._status = BeltStatus.IDLE
        elif response == self.RESP_MIXING:
            self._status = BeltStatus.MIXING
        elif response == self.RESP_OK:
            self._status = BeltStatus.IDLE
        else:
            logger.warning(f"Unknown status response: {response}")

    def _wait_for_position(self, target: BeltPosition, poll_interval: float = 0.5) -> bool:
        """
        Wait for belt to reach target position.

        Args:
            target: Target position to wait for
            poll_interval: Time between status polls

        Returns:
            True if position reached

        Raises:
            BeltTimeoutError: If position not reached within timeout
        """
        start_time = time.time()
        target_response = (
            self.RESP_AT_SPOUT if target == BeltPosition.SPOUT else self.RESP_AT_DISPLAY
        )

        while time.time() - start_time < self.timeout:
            try:
                self._update_status()

                if self._current_position == target:
                    logger.info(f"Belt reached {target.value} position")
                    return True

                if self._status == BeltStatus.ERROR:
                    raise BeltCommandError("Belt in error state")

            except BeltTimeoutError:
                pass  # Continue polling

            time.sleep(poll_interval)

        raise BeltTimeoutError(f"Timeout waiting for {target.value} position")

    def _wait_for_mixing_complete(
        self,
        oscillations: int,
        poll_interval: float = 0.5
    ) -> bool:
        """
        Wait for mixing to complete.

        Args:
            oscillations: Expected number of oscillations
            poll_interval: Time between status polls

        Returns:
            True if mixing completed
        """
        # Estimate mixing time (~1s per oscillation + buffer)
        estimated_time = oscillations * 1.0 + 2.0
        timeout = max(estimated_time * 1.5, self.timeout)

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                self._update_status()

                if self._status == BeltStatus.IDLE:
                    logger.info(f"Mixing complete: {oscillations} oscillations")
                    return True

                if self._status == BeltStatus.ERROR:
                    raise BeltCommandError("Belt error during mixing")

            except BeltTimeoutError:
                pass  # Continue polling

            time.sleep(poll_interval)

        raise BeltTimeoutError(f"Timeout waiting for mixing to complete")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
        return False
