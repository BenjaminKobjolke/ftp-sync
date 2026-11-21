"""Shared test fixtures."""

import pytest

from run_failures import run_failures


@pytest.fixture(autouse=True)
def reset_run_failures() -> None:
    """Keep operation failure counts isolated between tests."""
    run_failures.reset()
