"""Test command line interface and global functions"""
from argparse import Namespace
import logging
from unittest.mock import MagicMock, call, patch

import pytest
import pytest_socket

from midea_beautiful import connect_to_cloud
from midea_beautiful.cli import (
    _configure_argparser,
    _logs_install,
    _output,
    _run_discover_command,
    _run_set_command,
    _run_status_command,
    cli,
)
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import LanDevice

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name line-too-long


def test_argparser():
    parser = _configure_argparser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--test"])


def test_argparser_set():
    parser = _configure_argparser()
    with pytest.raises(SystemExit):
        parser.parse_args(["set", "--test"])


def test_output(capsys: pytest.CaptureFixture):
    lan = LanDevice(appliance_id="456", appliance_type="a1")
    _output(lan, True)
    captured = capsys.readouterr()
    assert "token" in captured.out
    assert "key" in captured.out
    assert "Dehumidifier" in captured.out
    assert "humid%" in captured.out
    assert "Air conditioner" not in captured.out

    _output(lan, False)
    captured = capsys.readouterr()
    assert "token" not in captured.out
    assert "humid%" in captured.out
    assert "Air conditioner" not in captured.out

    lan = LanDevice(appliance_id="123", appliance_type="ac")
    _output(lan, True)
    captured = capsys.readouterr()
    assert "token" in captured.out
    assert "key" in captured.out
    assert "target" in captured.out
    assert "indoor" in captured.out
    assert "outdoor" in captured.out
    assert "Dehumidifier" not in captured.out
    assert "Air conditioner" in captured.out

    _output(lan, False)
    captured = capsys.readouterr()
    assert "token" not in captured.out
    assert "key" not in captured.out
    assert "target" in captured.out
    assert "indoor" in captured.out
    assert "outdoor" in captured.out
    assert "Dehumidifier" not in captured.out
    assert "Air conditioner" in captured.out


def test_status():
    namespace = Namespace(ip=None, id=None)
    ret = _run_status_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="123")
    ret = _run_status_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="", token=None, account=None)
    ret = _run_status_command(namespace)
    assert ret == 8
    namespace = Namespace(
        ip="1.2.3.4",
        id="",
        token="45",
        key="24",
        account=None,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        _run_status_command(namespace)
    namespace = Namespace(
        ip=None,
        id="45",
        token=None,
        key=None,
        account="user@example.com",
        password="test",
        appkey="876",
        appid="1000",
        cloud=True,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        _run_status_command(namespace)


def test_status_ok(
    mock_cloud: MideaCloud,
    capsys: pytest.CaptureFixture,
):
    namespace = Namespace(
        ip=None,
        id="45",
        token=None,
        key=None,
        account="user@example.com",
        password="test",
        appkey="876",
        appid="1000",
        cloud=True,
        credentials=False,
    )
    with patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud):
        res = _run_status_command(namespace)
        assert res == 0
        captured = capsys.readouterr()
        assert "id      = 45" in captured.out


def test_status_no_appliance(
    mock_cloud: MideaCloud,
    caplog: pytest.LogCaptureFixture,
):
    with (
        patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud),
        patch("midea_beautiful.cli.appliance_state", return_value=None),
    ):
        namespace = Namespace(
            ip=None,
            id="46",
            token=None,
            key=None,
            account="user@example.com",
            password="test",
            appkey="876",
            appid="1000",
            cloud=True,
            credentials=False,
        )
        caplog.clear()
        res = _run_status_command(namespace)
        assert res == 9
        assert len(caplog.records) == 1
        assert caplog.messages[0], "Unable to get appliance status for '46'"


def test_run_discover_command(capsys: pytest.CaptureFixture):
    mock_device = MagicMock()
    with patch("midea_beautiful.cli.find_appliances", side_effect=[[mock_device]]):
        namespace = Namespace(
            account="user@example.com",
            password="test",
            appkey="876",
            appid="1000",
            address=None,
            credentials=False,
        )
        res = _run_discover_command(namespace)
        assert res == 0
        captured = capsys.readouterr()
        assert "target" not in captured.out
        assert "token" not in captured.out
        assert "s/n" in captured.out
        assert res == 0


def test_run_cli(caplog: pytest.LogCaptureFixture):
    with pytest.raises(SystemExit):
        cli(["set", "--not-existing"])

    with pytest.raises(SystemExit):
        cli(["no-command", "--test"])

    # Missing command
    with pytest.raises(SystemExit):
        cli(["--test"])

    caplog.clear()

    ret = cli(
        [
            "--log",
            "5",
            "status",
            "--account",
            "user@example.com",
            "--password",
            "test",
        ]
    )
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "Missing ip address or appliance id"
    assert ret == 7


def test_set_command():
    namespace = Namespace(ip=None, id=None)
    ret = _run_set_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="123")
    ret = _run_set_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="", token=None, account=None)
    ret = _run_set_command(namespace)
    assert ret == 8
    namespace = Namespace(
        ip="1.2.3.4",
        id="",
        token="45",
        key="24",
        account=None,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        _run_set_command(namespace)
    namespace = Namespace(
        ip=None,
        id="45",
        token=None,
        key=None,
        account="user@example.com",
        password="test",
        appkey="876",
        appid="1000",
        cloud=True,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        _run_set_command(namespace)


def test_set_with_cloud(
    mock_cloud: MideaCloud,
    capsys: pytest.CaptureFixture,
):
    namespace = Namespace(
        ip=None,
        id="411",
        token=None,
        key=None,
        account="user@example.com",
        password="test",
        appkey="876",
        appid="1000",
        cloud=True,
        credentials=False,
        command="set",
        loglevel="INFO",
    )
    with patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud):
        _run_set_command(namespace)
        captured = capsys.readouterr()
        assert "id      = 411" in captured.out


def test_set_no_status(
    mock_cloud: MideaCloud,
    caplog: pytest.LogCaptureFixture,
):

    with (
        patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud),
        patch("midea_beautiful.cli.appliance_state", return_value=None),
    ):
        namespace = Namespace(
            ip=None,
            id="416",
            token=None,
            key=None,
            account="user@example.com",
            password="test",
            appkey="876",
            appid="1000",
            cloud=True,
            credentials=False,
        )
        caplog.clear()
        res = _run_set_command(namespace)
        assert res == 9
        assert len(caplog.records) == 1
        assert caplog.messages[0], "Unable to get appliance status for '416'"


def test_connect_to_cloud(mock_cloud: MagicMock):
    with patch("midea_beautiful.MideaCloud", return_value=mock_cloud) as constructor:
        cloud = connect_to_cloud("user@example.com", "pa55w0rd")
        assert cloud is mock_cloud
        assert mock_cloud.mock_calls[0] == call.authenticate()
        assert constructor.mock_calls[0] == call(
            appkey="3742e9e5842d4ad59c2db887e12449f9",
            account="user@example.com",
            password="pa55w0rd",
            appid=1017,
        )


def test_coloredlogs():
    with patch("midea_beautiful.cli.logging", return_value=MagicMock()) as log:
        _logs_install(logging.DEBUG, logmodule="notexisting")
        assert log.mock_calls == [call.basicConfig(level=10)]
    # coloredlogs must be installed otherwise this will fail
    with patch("midea_beautiful.cli.logging", return_value=MagicMock()) as log:
        _logs_install(logging.DEBUG)
        assert log.mock_calls == []
