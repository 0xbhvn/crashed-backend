"""
Logging utilities for BC Game Crash Monitor.

This module provides standardized logging configuration for all components.
"""

import logging
import sys
from typing import Optional, Dict, Any
from .. import config


def configure_logging(
    name: str,
    level: Optional[str] = None,
    log_to_file: bool = False,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure a logger with standardized settings.

    Args:
        name: Name of the logger
        level: Log level (INFO, DEBUG, etc.). If None, uses config.LOG_LEVEL
        log_to_file: Whether to log to a file in addition to console
        log_file: Path to log file if log_to_file is True

    Returns:
        Configured logger instance
    """
    # Use provided level or get from config
    if level is None:
        level = config.LOG_LEVEL

    # Convert string level to logging level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)

    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatters
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Add file handler if requested
    if log_to_file:
        if log_file is None:
            log_file = f"logs/{name.replace('.', '_')}.log"

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def log_sensitive(
    logger: logging.Logger,
    level: int,
    message: str,
    sensitive_data: Dict[str, Any]
) -> None:
    """
    Log a message with sensitive data masked.

    Args:
        logger: Logger instance
        level: Logging level (e.g., logging.INFO)
        message: Message template with {key} placeholders
        sensitive_data: Dictionary of sensitive data to mask
    """
    # Create a copy of the sensitive data with masked values
    masked_data = {}

    for key, value in sensitive_data.items():
        if value is None:
            masked_data[key] = None
        elif isinstance(value, str):
            if len(value) > 8:
                # Mask all but first and last two characters
                masked_data[key] = f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
            else:
                # Mask the whole string for short values
                masked_data[key] = "*" * len(value)
        else:
            # For non-strings, convert to string and mask
            str_value = str(value)
            masked_data[key] = f"{'*' * len(str_value)}"

    # Format the message with masked data
    masked_message = message.format(**masked_data)

    # Log the masked message
    logger.log(level, masked_message)
