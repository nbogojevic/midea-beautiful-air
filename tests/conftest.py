"""Fixtures and setup for tests."""

import logging
from unittest.mock import patch

import pytest
from pytest_socket import disable_socket

from midea_beautiful.util import clear_sensitive, very_verbose

# pylint: disable=missing-function-docstring


def pytest_runtest_setup():
    disable_socket()


@pytest.fixture(autouse=True)
def log_warning(caplog):
    """Automatically set log level to WARNING"""
    caplog.set_level(logging.WARNING)


@pytest.fixture(name="mock_cloud")
def mock_cloud():
    """Fixture that mocks Midea cloud API client"""
    with patch("midea_beautiful.cloud.MideaCloud") as cloud:
        return cloud


@pytest.fixture(autouse=True)
def clean_logging_setup_state():
    # Code that will run before your test, for example:
    clear_sensitive()
    very_verbose(False)
    # A test function will be run at this point
    yield
    # Code that will run after your test, for example:
    clear_sensitive()
