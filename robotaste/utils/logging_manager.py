"""
Centralized logging configuration for RoboTaste.
Single source of truth for all logging setup across app, service, and pump components.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional


def setup_logging(
    component: str,
    log_level: str = "INFO",
    log_dir: Optional[Path] = None
) -> Path:
    """
    Configure comprehensive logging for RoboTaste components.

    Args:
        component: Component type - "app", "service", or "pump"
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Optional custom log directory (defaults to project/logs)

    Returns:
        Path to the primary log file for this component

    Creates:
        - Console handler with INFO level (or specified level)
        - File handler with DEBUG level and daily rotation (7-day retention)
        - Consistent format across all components
    """
    # Validate component
    valid_components = {"app", "service", "pump", "api"}
    if component not in valid_components:
        raise ValueError(f"Invalid component '{component}'. Must be one of {valid_components}")

    # Validate log level
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {log_level}')

    # Setup log directory
    if log_dir is None:
        log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Define component-specific log files
    log_files = {
        "app": log_dir / f"session_log_{datetime.now().strftime('%d%m%y')}.txt",
        "service": log_dir / "pump_control_service.log",
        "pump": log_dir / f"pump_operations_{datetime.now().strftime('%Y%m%d')}.log",
        "api": log_dir / f"api_server_{datetime.now().strftime('%d%m%y')}.log",
    }
    log_file = log_files[component]

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(console_formatter)

    # File handler with daily rotation (7-day retention)
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when='midnight',
        interval=1,
        backupCount=7,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set to DEBUG, handlers will filter
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Component-specific logger configuration
    if component in ("pump", "api"):
        # Configure pump-specific loggers for detailed hardware tracing
        pump_loggers = [
            "robotaste.hardware.pump_controller",
            "robotaste.core.pump_integration",
            "robotaste.core.pump_manager"
        ]
        for logger_name in pump_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.DEBUG)

    logging.info(f"Logging configured for {component}: {log_file}")
    logging.info(f"Console level: {log_level}, File level: DEBUG, Rotation: daily (7-day retention)")

    return log_file


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.

    Args:
        name: Logger name (typically __name__ from the calling module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
