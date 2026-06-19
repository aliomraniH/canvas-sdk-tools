"""structlog JSON logging.

PHI / code hygiene: tool inputs (submitted code, manifests) are NEVER logged.
Only metadata — tool name, sdk_version, finding counts — is emitted.
"""

from __future__ import annotations

import logging

import structlog


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog to emit JSON to stdout."""
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "canvas_sdk_tools") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
