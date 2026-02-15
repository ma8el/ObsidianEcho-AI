"""Logging configuration."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings


class RequestIDFilter(logging.Filter):
    """Filter to inject request ID into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add request ID to log record if available.

        Args:
            record: Log record to modify

        Returns:
            True to allow the record to be logged
        """
        # Import here to avoid circular dependency
        from app.api.middleware.request_id import get_request_id

        # Add request_id to record if not already present
        if not hasattr(record, "request_id"):
            request_id = get_request_id()
            record.request_id = request_id if request_id else None

        return True


class JSONFormatter(logging.Formatter):
    """JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON formatted log string
        """
        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add request_id if available
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields (excluding built-in attributes)
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
                "request_id",
            }:
                log_data[key] = value

        return json.dumps(log_data)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter."""

    def __init__(self) -> None:
        """Initialize text formatter."""
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        super().__init__(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with request ID if available.

        Args:
            record: Log record to format

        Returns:
            Formatted log string
        """
        # Add request_id to message if available
        if hasattr(record, "request_id") and record.request_id:
            original_msg = record.getMessage()
            record.msg = f"[{record.request_id}] {original_msg}"
            record.args = ()  # Clear args since we've already formatted the message

        return super().format(record)


def setup_logging(settings: Settings) -> None:
    """
    Configure application logging.

    Args:
        settings: Application settings
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))

    # Add request ID filter to automatically inject request IDs
    request_id_filter = RequestIDFilter()
    console_handler.addFilter(request_id_filter)

    formatter: logging.Formatter
    if settings.log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = TextFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
