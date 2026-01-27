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
import re
from typing import Optional, Literal, List, Tuple
from threading import RLock
from dataclasses import dataclass

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


@dataclass
class PumpBurstConfig:
    """Configuration for a single pump in burst operation."""
    address: int  # 0-9 only (burst mode constraint)
    rate_ul_min: float
    volume_ul: float
    diameter_mm: float
    volume_unit: Literal["ML", "UL"] = "ML"
    direction: Literal["INF", "WDR"] = "INF"


@dataclass
class BurstCommandSet:
    """Complete set of burst commands for multi-pump operation."""
    config_command: str      # e.g., "0 RAT 60 MM * 0 DIR INF * 0 VOL ML * 0 VOL 3.0 * 1 RAT 30 MM * 1 DIR INF * 1 VOL ML * 1 VOL 1.0 *"
    validation_command: str  # e.g., "0 RAT * 0 VOL * 1 RAT * 1 VOL *"
    run_command: str        # e.g., "0 RUN * 1 RUN *"


class _BurstCommandFormatter:
    """Helper for burst command formatting without serial setup."""

    @staticmethod
    def format_rate(rate: float, unit: str) -> tuple[str, str]:
        if unit == "UM" and rate > 9999:
            rate = rate / 1000.0
            unit = "MM"

        if unit in ["UM", "UH"]:
            if rate >= 1000:
                rate_str = f"{rate:.0f}"
            elif rate >= 100:
                rate_str = f"{rate:.1f}"
            else:
                rate_str = f"{rate:.2f}"
        else:
            rate_str = f"{rate:.2f}"

        return rate_str, unit

    @staticmethod
    def format_volume_ml(volume_ml: float) -> str:
        if volume_ml >= 100:
            return f"{volume_ml:.1f}"
        if volume_ml >= 10:
            return f"{volume_ml:.2f}"
        if volume_ml >= 1:
            return f"{volume_ml:.3f}"
        if volume_ml == 0:
            return "0.000"
        return f"{volume_ml:.3f}"

    @staticmethod
    def format_volume_ul(volume_ul: float) -> str:
        if volume_ul >= 1000:
            return f"{volume_ul:.0f}"
        if volume_ul >= 100:
            return f"{volume_ul:.1f}"
        return f"{volume_ul:.2f}"

    @staticmethod
    def calculate_max_rate_for_diameter(diameter_mm: float) -> float:
        """
        Calculate maximum flow rate (mL/min) for a given syringe diameter.
        
        Based on NE-4000 Multi-Phaser User Manual, Section 11.7:
        "Syringe Diameters and Rate Limits"
        
        The pump has a maximum linear velocity that translates to different
        flow rates depending on syringe cross-sectional area.
        
        Args:
            diameter_mm: Syringe inner diameter in mm
            
        Returns:
            Maximum flow rate in mL/min
            
        Note:
            Values from B-D (Becton-Dickinson) syringe table in manual.
            Other manufacturers (HSW, Terumo, etc.) have similar limits.
        """
        # From NE-4000 manual Table 11.7 - B-D Syringes
        # Format: (diameter_mm, max_rate_ml_min)
        BD_SYRINGE_RATE_TABLE = [
            (4.699, 3.135),    # 1mL BD syringe
            (8.585, 10.46),    # 3mL BD
            (11.99, 20.41),    # 5mL BD
            (14.43, 29.56),    # 10mL BD
            (19.05, 51.53),    # 20mL BD
            (21.59, 66.19),    # 30mL BD
            (26.59, 100.3),    # 60mL BD (pump absolute max is ~95, but spec shows 100.3)
        ]
        
        # Find closest diameter and interpolate
        for i, (d, rate) in enumerate(BD_SYRINGE_RATE_TABLE):
            if diameter_mm <= d:
                if i == 0:
                    # Below smallest syringe - use smallest rate
                    return rate
                # Linear interpolation between this and previous entry
                prev_d, prev_rate = BD_SYRINGE_RATE_TABLE[i - 1]
                ratio = (diameter_mm - prev_d) / (d - prev_d)
                return prev_rate + ratio * (rate - prev_rate)
        
        # Above largest diameter in table - extrapolate but cap at absolute max
        # The pump absolute max is 95 mL/min (hardware limit)
        last_d, last_rate = BD_SYRINGE_RATE_TABLE[-1]
        if diameter_mm > last_d:
            # Extrapolate assuming linear relationship with diameter^2
            # But cap at 95 mL/min (NE-4000 absolute hardware limit)
            return min(95.0, last_rate)


class BurstCommandBuilder:
    """Builds Network Command Burst commands for NE-4000 pumps."""

    @staticmethod
    def validate_burst_config(configs: List[PumpBurstConfig]) -> List[str]:
        """
        Validate configurations are compatible with burst mode.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check address range (0-9 for burst mode)
        for config in configs:
            if config.address < 0 or config.address > 9:
                errors.append(
                    f"Pump address {config.address} out of range. "
                    f"Burst mode requires addresses 0-9."
                )

        # Check for duplicate addresses
        addresses = [c.address for c in configs]
        if len(addresses) != len(set(addresses)):
            errors.append("Duplicate pump addresses detected")

        # Validate rates and volumes
        for config in configs:
            if config.rate_ul_min <= 0:
                errors.append(f"Pump {config.address}: Rate must be positive")
            if config.volume_ul <= 0:
                errors.append(f"Pump {config.address}: Volume must be positive")
            if config.diameter_mm <= 0:
                errors.append(f"Pump {config.address}: Diameter must be positive")
            if config.diameter_mm < 0.1 or config.diameter_mm > 50.0:
                errors.append(
                    f"Pump {config.address}: Diameter must be 0.1-50.0 mm"
                )
            if config.volume_unit not in ["ML", "UL"]:
                errors.append(
                    f"Pump {config.address}: Volume unit must be ML or UL"
                )
            if config.volume_unit == "UL" and config.volume_ul > 9999:
                errors.append(
                    f"Pump {config.address}: Volume exceeds UL limit (max 9999 UL)"
                )

        return errors

    @staticmethod
    def build_burst_commands(configs: List[PumpBurstConfig]) -> BurstCommandSet:
        """
        Build three command strings for burst mode operation.

        Args:
            configs: List of pump configurations

        Returns:
            BurstCommandSet with config, validation, and run commands

        Example output for 2 pumps (3mL @ 60mL/min, 1mL @ 30mL/min):
            config: "0 DIA 29.00 * 0 RAT 60.00 MM * 0 DIR INF * 0 VOL ML * 0 VOL 3.000 * 1 DIA 29.00 * 1 RAT 30.00 MM * 1 DIR INF * 1 VOL ML * 1 VOL 1.000 *"
            validation: "0 RAT * 0 VOL * 1 RAT * 1 VOL *"
            run: "0 RUN * 1 RUN *"
        """
        # Validate first
        errors = BurstCommandBuilder.validate_burst_config(configs)
        if errors:
            raise ValueError(f"Invalid burst configuration: {'; '.join(errors)}")

        config_parts = []
        validation_parts = []
        run_parts = []

        # Create a temporary pump instance to access formatting methods
        # (we'll use address 0, but we only need the formatting logic)
        temp_pump = _BurstCommandFormatter()

        for config in configs:
            addr = config.address

            # Format rate (auto-converts to MM if needed)
            rate_str, rate_unit = temp_pump.format_rate(
                config.rate_ul_min, "UM"
            )

            # Format volume
            if config.volume_unit == "UL":
                volume_str = temp_pump.format_volume_ul(config.volume_ul)
            else:
                volume_ml = config.volume_ul / 1000.0
                volume_str = temp_pump.format_volume_ml(volume_ml)

            # Direction
            direction = config.direction

            # Build config command parts
            # Format: <addr> DIA <value> * <addr> RAT <value> <unit> * <addr> DIR <direction> * <addr> VOL <unit> * <addr> VOL <value> *
            config_parts.append(f"{addr} DIA {config.diameter_mm:.2f}")
            config_parts.append(f"{addr} RAT {rate_str} {rate_unit}")
            config_parts.append(f"{addr} DIR {direction}")
            config_parts.append(f"{addr} VOL {config.volume_unit}")
            config_parts.append(f"{addr} VOL {volume_str}")

            # Build validation command parts
            validation_parts.append(f"{addr} RAT")
            validation_parts.append(f"{addr} VOL")

            # Build run command parts
            run_parts.append(f"{addr} RUN")

        # Join with " * " separator and add trailing " *"
        config_cmd = " * ".join(config_parts) + " *"
        validation_cmd = " * ".join(validation_parts) + " *"
        run_cmd = " * ".join(run_parts) + " *"

        return BurstCommandSet(
            config_command=config_cmd,
            validation_command=validation_cmd,
            run_command=run_cmd
        )


class SeparatedBurstCommandBuilder:
    """
    Builds single-parameter burst commands for NE-4000 pumps.
    
    The NE-4000 burst mode only applies ONE parameter per command when
    multiple parameters are sent. This builder creates separate commands
    for each parameter type to ensure all settings are applied correctly.
    
    Usage:
        configs = [PumpBurstConfig(...), PumpBurstConfig(...)]
        
        # Init phase (once per session)
        pump._send_burst_command(SeparatedBurstCommandBuilder.build_diameter_command(configs))
        pump._send_burst_command(SeparatedBurstCommandBuilder.build_rate_command(configs))
        pump._send_burst_command(SeparatedBurstCommandBuilder.build_volume_unit_command(configs))
        pump._send_burst_command(SeparatedBurstCommandBuilder.build_direction_command(configs))
        
        # Per-cycle
        pump._send_burst_command(SeparatedBurstCommandBuilder.build_volume_value_command(configs))
        pump._send_burst_command(SeparatedBurstCommandBuilder.build_run_command(configs))
    """

    @staticmethod
    def validate_rate_for_diameter(configs: List[PumpBurstConfig]) -> List[str]:
        """
        Validate that rates are within limits for each pump's syringe diameter.
        
        Args:
            configs: List of pump configurations
            
        Returns:
            List of warning messages (empty if all valid)
        """
        warnings = []
        for c in configs:
            # Convert rate to mL/min for comparison
            rate_ml_min = c.rate_ul_min / 1000.0
            max_rate = _BurstCommandFormatter.calculate_max_rate_for_diameter(c.diameter_mm)
            
            if rate_ml_min > max_rate:
                warnings.append(
                    f"Pump {c.address}: Rate {rate_ml_min:.1f} mL/min exceeds "
                    f"max rate {max_rate:.1f} mL/min for {c.diameter_mm:.2f}mm diameter syringe. "
                    f"Pump will return OOR error."
                )
        return warnings

    @staticmethod
    def build_diameter_command(configs: List[PumpBurstConfig]) -> str:
        """Build diameter command: 0 DIA xx.xx * 1 DIA yy.yy *"""
        parts = [f"{c.address} DIA {c.diameter_mm:.2f}" for c in configs]
        return " * ".join(parts) + " *"

    @staticmethod
    def build_rate_command(configs: List[PumpBurstConfig], validate: bool = True) -> str:
        """
        Build rate command: 0 RAT xx.xx MM * 1 RAT yy.yy MM *
        
        Args:
            configs: List of pump configurations
            validate: If True, log warnings for rates that may cause OOR
        """
        if validate:
            warnings = SeparatedBurstCommandBuilder.validate_rate_for_diameter(configs)
            for warning in warnings:
                logger.warning(f"⚠️ {warning}")
        
        parts = []
        for c in configs:
            rate_str, unit = _BurstCommandFormatter.format_rate(c.rate_ul_min, "UM")
            parts.append(f"{c.address} RAT {rate_str} {unit}")
        return " * ".join(parts) + " *"

    @staticmethod
    def build_volume_unit_command(configs: List[PumpBurstConfig]) -> str:
        """Build volume unit command: 0 VOL ML * 1 VOL ML *"""
        parts = [f"{c.address} VOL {c.volume_unit}" for c in configs]
        return " * ".join(parts) + " *"

    @staticmethod
    def build_direction_command(configs: List[PumpBurstConfig]) -> str:
        """Build direction command: 0 DIR INF * 1 DIR INF *"""
        parts = [f"{c.address} DIR {c.direction}" for c in configs]
        return " * ".join(parts) + " *"

    @staticmethod
    def build_volume_value_command(configs: List[PumpBurstConfig]) -> str:
        """Build volume value command: 0 VOL xx.xxx * 1 VOL yy.yyy *"""
        parts = []
        for c in configs:
            if c.volume_unit == "UL":
                vol_str = _BurstCommandFormatter.format_volume_ul(c.volume_ul)
            else:
                vol_str = _BurstCommandFormatter.format_volume_ml(c.volume_ul / 1000.0)
            parts.append(f"{c.address} VOL {vol_str}")
        return " * ".join(parts) + " *"

    @staticmethod
    def build_run_command(configs: List[PumpBurstConfig]) -> str:
        """Build run command: 0 RUN * 1 RUN *"""
        parts = [f"{c.address} RUN" for c in configs]
        return " * ".join(parts) + " *"

    @staticmethod
    def build_stop_command(configs: List[PumpBurstConfig]) -> str:
        """Build stop command: 0 STP * 1 STP *"""
        parts = [f"{c.address} STP" for c in configs]
        return " * ".join(parts) + " *"

    @staticmethod
    def build_verification_command(configs: List[PumpBurstConfig], param: str) -> str:
        """
        Build verification query for one parameter type.
        
        Args:
            configs: List of pump configurations
            param: Parameter to query (DIA, RAT, VOL, DIR)
        """
        parts = [f"{c.address} {param}" for c in configs]
        return " * ".join(parts) + " *"


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
        self._current_rate_ul_min: Optional[float] = (
            None  # Track current rate for time calculations
        )

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
        logger.info(
            f"[Pump {self.address}] Attempting connection to {self.port} at {self.baud} baud"
        )

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
                    logger.info(
                        f"[Pump {self.address}] ✅ Serial connection established"
                    )

                    # Small delay for pump to be ready
                    time.sleep(0.1)

                # Verify connection by stopping pump (safe command)
                # This can run outside the global lock since we now have our own connection
                self._send_command(self.CMD_STOP)
                logger.info(
                    f"[Pump {self.address}] ✅ Connection verified (test command successful)"
                )

            except serial.SerialException as e:
                logger.error(
                    f"[Pump {self.address}] ❌ Connection failed: {e}", exc_info=True
                )
                raise PumpConnectionError(f"Failed to connect to {self.port}: {e}")
            except Exception as e:
                if self.serial:
                    self.serial.close()
                    self.serial = None
                self._connected = False
                logger.error(
                    f"[Pump {self.address}] ❌ Connection error: {e}", exc_info=True
                )
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
        Set syringe diameter with verification.

        Args:
            diameter_mm: Syringe inner diameter in millimeters (0.1 - 50.0)

        Raises:
            ValueError: If diameter out of range
            PumpCommandError: If pump rejects command
        """
        if not 0.1 <= diameter_mm <= 50.0:
            raise ValueError(f"Diameter must be 0.1-50.0 mm, got {diameter_mm}")

        logger.info(
            f"[Pump {self.address}] Setting syringe diameter: {diameter_mm:.2f} mm"
        )
        # Format to 2 decimal places (max 4 digits) for NE-4000 constraint
        cmd = f"{self.CMD_DIAMETER} {diameter_mm:.2f}"
        response = self._send_command(cmd)
        logger.info(f"[Pump {self.address}] Set diameter response: {response}")

        # Check if command was rejected
        if response == "S?":
            error_msg = (
                f"[Pump {self.address}] ❌ DIAMETER COMMAND REJECTED (S?) - "
                f"Value {diameter_mm:.3f} mm may be out of range or invalid"
            )
            logger.error(error_msg)
            raise PumpCommandError(error_msg)

        # VERIFY: Query diameter back
        actual_diameter = self.get_diameter()
        if actual_diameter is not None:
            if abs(actual_diameter - diameter_mm) < 0.01:  # Within 0.01mm tolerance
                logger.info(
                    f"[Pump {self.address}] ✅ Diameter verified: {actual_diameter:.3f} mm"
                )
            else:
                logger.error(
                    f"[Pump {self.address}] ⚠️  DIAMETER MISMATCH! "
                    f"Set: {diameter_mm:.3f} mm, Got: {actual_diameter:.3f} mm"
                )
        else:
            logger.warning(f"[Pump {self.address}] Could not verify diameter")

    def set_rate(
        self, rate: float, unit: Literal["UM", "MM", "UH", "MH"] = "UM"
    ) -> None:
        """
        Set pumping rate with verification.

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

        logger.info(f"[Pump {self.address}] Setting rate: {rate:.1f} {unit}")

        # Format rate and potentially convert units for NE-4000's 4-digit constraint
        rate_str, final_unit = self._format_rate_for_pump(rate, unit)
        cmd = f"{self.CMD_RATE} {rate_str} {final_unit}"
        response = self._send_command(cmd)
        logger.info(f"[Pump {self.address}] Set rate response: {response}")

        # Check if command was rejected
        if response == "S?":
            error_msg = (
                f"[Pump {self.address}] ❌ RATE COMMAND REJECTED (S?) - "
                f"Value {rate_str} {final_unit} may be out of range for configured syringe diameter"
            )
            logger.error(error_msg)
            raise PumpCommandError(error_msg)

        # Store rate in µL/min for time calculations (use converted values)
        # Need to convert the ORIGINAL rate value based on FINAL unit
        if final_unit == "UM":
            # If we kept UM, use the original or formatted rate
            self._current_rate_ul_min = float(rate_str)
        elif final_unit == "MM":
            # If we converted to MM, rate_str is in mL/min
            self._current_rate_ul_min = float(rate_str) * 1000
        elif unit == "UH":
            self._current_rate_ul_min = rate / 60
        elif unit == "MH":
            self._current_rate_ul_min = (rate * 1000) / 60

        # VERIFY: Query rate back
        actual_rate, actual_unit = self.get_rate()
        if actual_rate is not None:
            # Convert actual rate to µL/min for comparison
            actual_rate_ul_min = actual_rate
            if actual_unit == "MM":
                actual_rate_ul_min = actual_rate * 1000
            elif actual_unit == "UH":
                actual_rate_ul_min = actual_rate / 60
            elif actual_unit == "MH":
                actual_rate_ul_min = (actual_rate * 1000) / 60

            # Compare in µL/min (with 1% tolerance for rounding)
            if self._current_rate_ul_min is not None:
                tolerance = self._current_rate_ul_min * 0.01
                if abs(actual_rate_ul_min - self._current_rate_ul_min) < max(
                    tolerance, 1.0
                ):
                    logger.info(
                        f"[Pump {self.address}] ✅ Rate verified: {actual_rate:.3f} {actual_unit} "
                        f"({self._current_rate_ul_min:.1f} µL/min)"
                    )
                else:
                    logger.error(
                        f"[Pump {self.address}] ⚠️  RATE MISMATCH! "
                        f"Set: {self._current_rate_ul_min:.1f} µL/min, "
                        f"Got: {actual_rate_ul_min:.1f} µL/min ({actual_rate:.3f} {actual_unit})"
                    )
            else:
                logger.warning(
                    f"[Pump {self.address}] Cannot verify rate - stored rate is None"
                )
        else:
            logger.warning(f"[Pump {self.address}] Could not verify rate")

    def set_volume(
        self, volume_ul: float, volume_unit: Literal["ML", "UL"] = "ML"
    ) -> None:
        """
        Set volume to dispense with verification (does not start pumping).

        Args:
            volume_ul: Volume in microliters
            volume_unit: "ML" or "UL" for pump volume units

        Raises:
            ValueError: If volume is negative
            PumpCommandError: If pump rejects command
        """
        if volume_ul <= 0:
            raise ValueError(f"Volume must be positive, got {volume_ul}")

        if volume_unit not in ["ML", "UL"]:
            raise ValueError(f"Volume unit must be 'ML' or 'UL', got {volume_unit}")

        if volume_unit == "UL" and volume_ul > 9999:
            raise ValueError(
                f"Volume exceeds UL limit (max 9999 UL), got {volume_ul}"
            )

        volume_ml = volume_ul / 1000.0
        if volume_unit == "UL":
            volume_str = self._format_volume_ul_for_pump(volume_ul)
        else:
            # Convert to mL and format for NE-4000's 4-digit constraint
            volume_str = self._format_volume_for_pump(volume_ml)

        logger.info(
            f"[Pump {self.address}] Programming volume: {volume_ul:.1f} µL "
            f"({volume_str} {volume_unit})"
        )
        response = self._send_command(f"{self.CMD_VOLUME} {volume_unit}")
        logger.debug(f"[Pump {self.address}] Set volume unit response: {response}")
        response = self._send_command(f"{self.CMD_VOLUME} {volume_str}")
        logger.info(f"[Pump {self.address}] Set volume response: {response}")

        # Check if command was rejected
        if response == "S?":
            error_msg = (
                f"[Pump {self.address}] ❌ VOLUME COMMAND REJECTED (S?) - "
                f"Value {volume_str} mL may be out of range"
            )
            logger.error(error_msg)
            raise PumpCommandError(error_msg)

        # VERIFY: Query volume back
        actual_volume_ml = self.get_volume()
        if actual_volume_ml is not None:
            expected_volume_ml = volume_ul / 1000.0
            if (
                abs(actual_volume_ml - expected_volume_ml) < 0.001
            ):  # Within 1µL tolerance
                logger.info(
                    f"[Pump {self.address}] ✅ Volume verified: {actual_volume_ml:.6f} mL "
                    f"({actual_volume_ml * 1000:.1f} µL)"
                )
            else:
                logger.error(
                    f"[Pump {self.address}] ⚠️  VOLUME MISMATCH! "
                    f"Set: {expected_volume_ml:.6f} mL, Got: {actual_volume_ml:.6f} mL"
                )
        else:
            logger.warning(f"[Pump {self.address}] Could not verify volume")

    def set_direction(self, direction: Literal["INF", "WDR"]) -> None:
        """
        Set pumping direction with verification.

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
        logger.info(f"[Pump {self.address}] Set direction response: {response}")

        # VERIFY: Query direction back
        actual_direction = self.get_direction()
        if actual_direction is not None:
            if actual_direction == direction:
                logger.info(
                    f"[Pump {self.address}] ✅ Direction verified: {actual_direction}"
                )
            else:
                logger.error(
                    f"[Pump {self.address}] ⚠️  DIRECTION MISMATCH! "
                    f"Set: {direction}, Got: {actual_direction}"
                )
        else:
            logger.warning(f"[Pump {self.address}] Could not verify direction")

    def _format_rate_for_pump(self, rate: float, unit: str) -> tuple[str, str]:
        """
        Format rate value and select optimal unit to fit NE-4000's 4-digit constraint.

        The NE-4000 pump accepts maximum 4 digits for numeric values.
        This method auto-converts large UM values to MM and formats appropriately.

        Args:
            rate: Rate value
            unit: Original unit (UM, MM, UH, MH)

        Returns:
            Tuple of (formatted_rate_string, final_unit)

        Examples:
            (60000, "UM") → ("60.00", "MM")  # Auto-convert to mL/min
            (2000, "UM") → ("2000", "UM")    # Keep as µL/min
            (95, "MM") → ("95.00", "MM")     # Format mL/min
        """
        # Auto-convert UM to MM if exceeds 4 digits
        if unit == "UM" and rate > 9999:
            rate = rate / 1000.0
            unit = "MM"
            logger.debug(
                f"[Pump {self.address}] Auto-converting rate to {rate:.2f} {unit}"
            )

        # Validate max rate (95 mL/min hardware limit)
        if unit == "MM" and rate > 95.0:
            logger.warning(
                f"[Pump {self.address}] Rate {rate:.2f} MM exceeds pump maximum (95 MM). "
                f"Command may be rejected."
            )

        # Format with appropriate precision for 4-digit limit
        if unit in ["UM", "UH"]:
            # Microliters: use integer format if >= 1000, else use decimals
            if rate >= 1000:
                rate_str = f"{rate:.0f}"  # "9999" (4 digits max)
            elif rate >= 100:
                rate_str = f"{rate:.1f}"  # "999.9" (4 digits)
            else:
                rate_str = f"{rate:.2f}"  # "99.99" (4 digits)
        else:  # MM or MH
            # Milliliters: always use 2 decimal places
            rate_str = f"{rate:.2f}"  # "95.00" (4 digits max for rate <= 95)

        return rate_str, unit

    def _format_volume_for_pump(self, volume_ml: float) -> str:
        """
        Format volume to fit NE-4000's 4-digit constraint.

        The NE-4000 pump accepts maximum 4 digits for numeric values.
        The VOL command always uses milliliters (does not accept unit suffix).
        Precision is adjusted based on magnitude to stay within limit.

        Args:
            volume_ml: Volume in milliliters

        Returns:
            Formatted volume string (always in mL)

        Examples:
            10.0 → "10.00" (4 digits)
            1.0 → "1.000" (4 digits)
            0.1 → "0.1000" (4 digits after decimal)
            0.001 → "0.0010" (4 digits after decimal)
        """
        if volume_ml >= 100:
            # 100-9999 mL: use 1 decimal place "100.0" to "999.9"
            return f"{volume_ml:.1f}"
        elif volume_ml >= 10:
            # 10-99.99 mL: use 2 decimals "10.00" to "99.99"
            return f"{volume_ml:.2f}"
        elif volume_ml >= 1:
            # 1-9.999 mL: use 3 decimals "1.000" to "9.999"
            return f"{volume_ml:.3f}"
        elif volume_ml == 0:
            return "0.000"
        else:
            # 0.001-0.999 mL: use 4 decimals "0.001" to "0.999"
            return f"{volume_ml:.3f}"

    def _format_volume_ul_for_pump(self, volume_ul: float) -> str:
        """
        Format volume in microliters to fit NE-4000's 4-digit constraint.

        Args:
            volume_ul: Volume in microliters

        Returns:
            Formatted volume string (always in µL)

        Examples:
            1000 → "1000"
            250.5 → "250.5"
            25.12 → "25.12"
        """
        if volume_ul >= 1000:
            return f"{volume_ul:.0f}"
        if volume_ul >= 100:
            return f"{volume_ul:.1f}"
        return f"{volume_ul:.2f}"

    def get_diameter(self) -> Optional[float]:
        """
        Query current syringe diameter setting from pump.

        Returns:
            Current diameter in mm, or None if query fails

        Actual NE-4000 response format: "S33.00" (S prefix + value)
        """
        logger.debug(f"[Pump {self.address}] Querying syringe diameter...")
        response = self._send_command(self.CMD_DIAMETER)  # Send without parameters

        # Parse response - NE-4000 format: "S<value>"
        # After stripping frames/address: 'S33.00'
        try:
            # Remove 'S' status prefix if present
            if response.startswith("S"):
                diameter_str = response[1:].strip()
                diameter = float(diameter_str)
                logger.debug(
                    f"[Pump {self.address}] Current diameter: {diameter:.3f} mm"
                )
                return diameter
            logger.warning(
                f"[Pump {self.address}] Unexpected diameter response format: {response}"
            )
        except (ValueError, IndexError) as e:
            logger.error(f"[Pump {self.address}] Error parsing diameter response: {e}")

        return None

    def get_rate(self) -> tuple[Optional[float], Optional[str]]:
        """
        Query current rate setting from pump.

        Returns:
            Tuple of (rate_value, unit) e.g. (100.0, "UM"), or (None, None) if query fails

        Actual NE-4000 response format: "S40.00MM" (S prefix + value + unit)
        """
        logger.debug(f"[Pump {self.address}] Querying rate...")
        response = self._send_command(self.CMD_RATE)

        try:
            # Parse NE-4000 format: "S40.00MM" or "S100.000UM"
            if response.startswith("S"):
                # Remove 'S' prefix
                value_and_unit = response[1:].strip()

                # Extract numeric part and unit (e.g., "40.00MM" → 40.00, MM)
                # Unit is the last 2 characters (UM, MM, UH, MH)
                if len(value_and_unit) >= 2:
                    # Try to find where the unit starts (first non-digit/non-decimal character after numbers)
                    match = re.match(r"([\d.]+)([A-Z]{2})", value_and_unit)
                    if match:
                        rate = float(match.group(1))
                        unit = match.group(2)
                        logger.debug(
                            f"[Pump {self.address}] Current rate: {rate:.3f} {unit}"
                        )
                        return (rate, unit)

            logger.warning(
                f"[Pump {self.address}] Unexpected rate response format: {response}"
            )
        except (ValueError, IndexError) as e:
            logger.error(f"[Pump {self.address}] Error parsing rate response: {e}")

        return (None, None)

    def get_volume(self) -> Optional[float]:
        """
        Query current volume setting from pump.

        Returns:
            Current programmed volume in mL, or None if query fails

        Actual NE-4000 response format: "S21.10ML" or "S500UL" (S prefix + value + unit)
        """
        logger.debug(f"[Pump {self.address}] Querying volume...")
        response = self._send_command(self.CMD_VOLUME)

        try:
            # Parse NE-4000 format: "S21.10ML", "S500UL", or "S10.00"
            # Convert UL responses to mL for consistent return value
            if response.startswith("S"):
                # Remove 'S' prefix
                value_and_unit = response[1:].strip()

                # Extract numeric value (remove unit suffix if present)
                match = re.match(r"([\d.]+)([A-Z]{2})?", value_and_unit)
                if match:
                    volume_value = float(match.group(1))
                    unit = match.group(2) or "ML"
                    if unit == "UL":
                        volume_ml = volume_value / 1000.0
                    else:
                        volume_ml = volume_value
                    logger.debug(
                        f"[Pump {self.address}] Current volume: {volume_ml:.6f} mL"
                    )
                    return volume_ml

            logger.warning(
                f"[Pump {self.address}] Unexpected volume response format: {response}"
            )
        except (ValueError, IndexError) as e:
            logger.error(f"[Pump {self.address}] Error parsing volume response: {e}")

        return None


    def get_direction(self) -> Optional[str]:
        """
        Query current direction setting from pump.

        Returns:
            "INF" for infuse or "WDR" for withdraw, or None if query fails

        Actual NE-4000 response format: "SINF" or "SWDR" (S prefix + direction)
        """
        logger.debug(f"[Pump {self.address}] Querying direction...")
        response = self._send_command(self.CMD_DIRECTION)

        try:
            # Parse NE-4000 format: "SINF" or "SWDR"
            if response.startswith("S"):
                # Remove 'S' prefix
                direction = response[1:].strip()
                logger.debug(f"[Pump {self.address}] Current direction: {direction}")
                return direction

            logger.warning(
                f"[Pump {self.address}] Unexpected direction response format: {response}"
            )
        except (ValueError, IndexError) as e:
            logger.error(f"[Pump {self.address}] Error parsing direction response: {e}")

        return None

    def start(self) -> None:
        """
        Start pumping with current settings.

        Raises:
            PumpCommandError: If pump rejects command
        """
        logger.info(f"[Pump {self.address}] ▶️  Starting pump motor...")
        response = self._send_command(self.CMD_RUN)
        logger.info(
            f"[Pump {self.address}] ✅ Pump motor running (response: {response})"
        )

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
        self,
        volume_ul: float,
        rate_ul_min: Optional[float] = None,
        wait: bool = True,
        volume_unit: Literal["ML", "UL"] = "ML",
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
            volume_unit: "ML" or "UL" for pump volume units

        Raises:
            ValueError: If rate is not specified and no current rate is set
            PumpCommandError: If any command fails
        """
        logger.info(f"[Pump {self.address}] ━━━ Starting dispense operation ━━━")
        logger.info(f"[Pump {self.address}] Volume: {volume_ul:.1f} µL")

        # Safety check: Prevent continuous pumping if volume is 0
        if volume_ul <= 0.001:
            logger.warning(
                f"[Pump {self.address}] Volume is ~0 ({volume_ul} µL), skipping dispense to prevent continuous flow."
            )
            return

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
        self.set_volume(volume_ul, volume_unit=volume_unit)

        # Start pumping
        self.start()

        # Wait for completion if requested
        if wait:
            logger.info(f"[Pump {self.address}] ⏳ Dispensing... ({wait_time:.2f}s)")
            time.sleep(wait_time)

            # Explicitly stop the pump
            self.stop()
            logger.info(
                f"[Pump {self.address}] ✅ Dispense complete: {volume_ul:.1f} µL delivered"
            )
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

        if self.serial is None:
            raise PumpConnectionError("Serial connection not available")

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
                    logger.debug(
                        f"[Pump {self.address}] → Sending: {full_command.strip()!r}"
                    )

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
                        logger.debug(
                            f"[Pump {self.address}] After stripping frames and address: {response!r}"
                        )

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
                    logger.error(
                        f"[Pump {self.address}] ❌ All {attempts} attempts failed"
                    )
                    raise

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error: {e}")
                raise PumpCommandError(f"Command failed: {e}")

        # Should not reach here, but just in case
        if last_error:
            raise last_error

        return ""

    def _send_burst_command(self, command: str, check_errors: bool = True) -> str:
        """
        Send Network Command Burst (responses will be gibberish per manual).

        Args:
            command: Pre-formatted burst command (e.g., "0 RAT 60 MM * 1 RAT 30 MM *")
            check_errors: If True, parse response for error indicators (default True)

        Returns:
            Raw response string (for logging only - content is gibberish)

        Raises:
            PumpCommandError: If response contains error indicators like ?OOR

        Note:
            Per NE-4000 manual page 44: "all of the pumps will be responding
            simultaneously, and therefore the communications response to a
            Network Command Burst will be gibberish and should be ignored."
            
            However, error indicators like ?OOR (out of range) can still be detected.
        """
        if not self.is_connected():
            raise PumpConnectionError("Not connected to pump")

        if self.serial is None:
            raise PumpConnectionError("Serial connection not available")

        # Burst commands don't use address prefix - they're already in the command
        full_command = f"{command}\r"

        logger.info(f"[Burst Mode] Sending: {command}")

        try:
            with self._lock:
                # Clear input buffer
                self.serial.reset_input_buffer()

                # Send command
                self.serial.write(full_command.encode("ascii"))

                # Read response (will be gibberish, but read it anyway to clear buffer)
                response = self.serial.read_until(b"\r").decode("ascii", errors="ignore").strip()

                if not response:
                    response = self.serial.read_until(b"\n").decode("ascii", errors="ignore").strip()

                logger.info(f"[Burst Mode] Response (gibberish): {response!r}")

                # Check for error indicators in the response
                if check_errors:
                    self._check_burst_response_for_errors(command, response)

                return response

        except PumpCommandError:
            raise  # Re-raise our own errors
        except Exception as e:
            logger.error(f"[Burst Mode] Command failed: {e}")
            raise PumpCommandError(f"Burst command failed: {e}")

    def _check_burst_response_for_errors(self, command: str, response: str) -> None:
        """
        Check burst response for error indicators.
        
        Args:
            command: The command that was sent
            response: The raw response from the pump
            
        Raises:
            PumpCommandError: If error indicators are detected
        """
        # Common error patterns in NE-4000 responses
        # ?OOR = Out Of Range
        # ? alone = Command error
        # These can appear even in "gibberish" burst responses
        
        if "?OOR" in response or "OOR" in response:
            logger.error(f"[Burst Mode] ❌ OUT OF RANGE error detected!")
            logger.error(f"  Command: {command}")
            logger.error(f"  Response: {response!r}")
            raise PumpCommandError(
                f"Pump returned OOR (Out Of Range) error. "
                f"Check that rate/volume/diameter values are within pump limits. "
                f"Command: {command}"
            )
        
        # Check for standalone error indicator (? followed by non-alphanumeric)
        # This is trickier because '?' can appear in gibberish
        # Only flag if we see clear error pattern like "0S?" or similar
        if "S?" in response and "S?O" not in response:
            logger.warning(f"[Burst Mode] ⚠️ Possible command error detected: {response!r}")
            # Don't raise - this might be false positive in gibberish

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
