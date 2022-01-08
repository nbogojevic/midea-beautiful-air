from unittest.mock import patch
import logging
import pytest

from pytest_socket import disable_socket


def pytest_runtest_setup():
    disable_socket()


@pytest.fixture(autouse=True)
def log_warning(caplog):
    caplog.set_level(logging.WARNING)


@pytest.fixture(name="mock_cloud")
def mock_cloud():
    with patch("midea_beautiful.cloud.MideaCloud") as mc:
        return mc
