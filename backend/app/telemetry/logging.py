# \backend\app\telemetry\logging.py
from __future__ import annotations

import logging
'''This module sets up logging for the application. It provides a function to configure logging with a specified level and format.
The configure_logging function takes an optional level parameter, which defaults to "INFO". It uses the logging.basicConfig function to set the logging level and format for log messages. The format includes the timestamp, log level, logger name, and the log message itself. This allows for consistent and structured logging throughout the application.
Example usage: configure_logging("DEBUG")'''

# Configure logging for the application
def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
