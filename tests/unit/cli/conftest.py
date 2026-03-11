"""Shared fixtures for CLI tests."""

from __future__ import annotations

import logging

import pytest
import structlog


@pytest.fixture(autouse=True)
def _suppress_structlog() -> None:
    """Suppress structlog console output during CLI tests.

    The CLI tests capture stdout via CliRunner, and structlog's
    default console renderer writes there too, corrupting JSON output.
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.CRITICAL),
    )
