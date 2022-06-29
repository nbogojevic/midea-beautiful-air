"""Test command line interface and global functions"""
from argparse import Namespace
import logging
import sys
from unittest.mock import MagicMock, call, patch

import pytest
import pytest_socket

from midea_beautiful import connect_to_cloud, LanDevice, MideaCloud
from midea_beautiful.cli import (
    _configure_argparser,
    _logs_install,
    _output,
    _run_discover_command,
    _run_dump_command,
    _run_set_command,
    _run_status_command,
    cli,
)
from midea_beautiful.midea import (
    DEFAULT_API_SERVER_URL,
    DEFAULT_HMACKEY,
    DEFAULT_IOTKEY,
    DEFAULT_SIGNKEY,
)

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name line-too-long


def _with_defaults(namespace: Namespace) -> Namespace:
    namespace.hmackey = DEFAULT_HMACKEY
    namespace.iotkey = DEFAULT_IOTKEY
    namespace.signkey = DEFAULT_SIGNKEY
    namespace.proxied = False
    namespace.apiurl = DEFAULT_API_SERVER_URL
    return namespace


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
        app=None,
    )
    _with_defaults(namespace)
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
        app=None,
    )
    _with_defaults(namespace)
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
            app=None,
        )
        _with_defaults(namespace)
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
            app=None,
        )
        _with_defaults(namespace)
        res = _run_discover_command(namespace)
        assert res == 0
        captured = capsys.readouterr()
        assert "target" not in captured.out
        assert "token" not in captured.out
        assert "s/n" in captured.out
        assert res == 0


def test_run_cli(caplog: pytest.LogCaptureFixture):
    # Empty command
    with patch.object(sys, "argv", ["no-args"]):
        cli()

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


def test_set_command_error():
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
        app=None,
    )
    _with_defaults(namespace)
    with pytest.raises(pytest_socket.SocketBlockedError):
        _run_set_command(namespace)


def test_set_command(
    mock_cloud: MideaCloud,
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
        beep_prompt=True,
        no_redact=False,
        verbose=False,
        app=None,
    )
    _with_defaults(namespace)
    with patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud):
        res = _run_set_command(namespace)
        assert res == 0


def test_set_command_read_only(
    mock_cloud: MideaCloud,
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
        no_redact=False,
        command="set",
        loglevel="INFO",
        online=True,
        verbose=False,
        app=None,
    )
    _with_defaults(namespace)

    with patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud):
        res = _run_set_command(namespace)
        assert res == 10


def test_set_command_not_existing(
    mock_cloud: MideaCloud,
    caplog: pytest.LogCaptureFixture,
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
        no_redact=False,
        something=True,
        verbose=False,
        app=None,
    )
    _with_defaults(namespace)

    mock_cloud.appliance_transparent_send.return_value = [b"012345678\02\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"]  # noqa: E501
    with patch("midea_beautiful.cli.connect_to_cloud", return_value=mock_cloud):
        res = _run_set_command(namespace)
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"
        assert res == 11


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
        no_redact=False,
        command="set",
        loglevel="INFO",
        verbose=False,
        app=None,
    )
    _with_defaults(namespace)

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
            app=None,
        )
        _with_defaults(namespace)

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
        assert len(constructor.mock_calls) == 1


def test_coloredlogs():
    with patch("midea_beautiful.cli.logging", return_value=MagicMock()) as log:
        _logs_install(logging.DEBUG, logmodule="notexisting")
        assert log.mock_calls == [call.basicConfig(level=10)]
    # coloredlogs must be installed otherwise this will fail
    with patch("midea_beautiful.cli.logging", return_value=MagicMock()) as log:
        _logs_install(logging.DEBUG)
        assert log.mock_calls == []


def test_run_dump(capsys: pytest.CaptureFixture):
    namespace = Namespace(
        dehumidifier=True,
        payload="c80101507f7f0023000000000000004b1e580000000000080a28",
        airconditioner=False,
    )
    res = _run_dump_command(namespace)
    assert res == 0
    captured = capsys.readouterr()
    assert "'indoor_temperature': 19.0" in captured.out
    assert "15  75 4b" in captured.out


def test_run_dump_fail():
    namespace = Namespace(
        dehumidifier=False,
        payload="c80101507f7f0023000000000000004b1e580000000000080a28",
        airconditioner=False,
    )
    res = _run_dump_command(namespace)
    assert res == 21


def test_run_dump_ac(capsys: pytest.CaptureFixture):
    namespace = Namespace(
        dehumidifier=False,
        payload="c80101507f7f0023000000000000004b1e580000000000080a28",
        airconditioner=True,
    )
    res = _run_dump_command(namespace)
    assert res == 0
    captured = capsys.readouterr()
    assert "'target_temperature': 17.0" in captured.out
    assert "15  75 4b" in captured.out
