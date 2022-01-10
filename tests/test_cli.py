from argparse import Namespace
from unittest.mock import MagicMock, patch
import pytest
import pytest_socket
from midea_beautiful.cli import (
    cli,
    configure_argparser,
    output,
    run_discover_command,
    run_status_command,
    run_watch_command,
)
from midea_beautiful.lan import LanDevice


def test_argparser():
    parser = configure_argparser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--test"])


def test_argparser_set():
    parser = configure_argparser()
    with pytest.raises(SystemExit):
        parser.parse_args(["set", "--test"])


def test_output(capsys: pytest.CaptureFixture):
    lan = LanDevice(id="456", appliance_type="a1")
    output(lan, True)
    captured = capsys.readouterr()
    assert "token" in captured.out
    assert "k1" in captured.out
    assert "Dehumidifier" in captured.out
    assert "humid%" in captured.out
    assert "Air conditioner" not in captured.out

    output(lan, False)
    captured = capsys.readouterr()
    assert "token" not in captured.out
    assert "humid%" in captured.out
    assert "Air conditioner" not in captured.out

    lan = LanDevice(id="123", appliance_type="ac")
    output(lan, True)
    captured = capsys.readouterr()
    assert "token" in captured.out
    assert "k1" in captured.out
    assert "target" in captured.out
    assert "indoor" in captured.out
    assert "outdoor" in captured.out
    assert "Dehumidifier" not in captured.out
    assert "Air conditioner" in captured.out

    output(lan, False)
    captured = capsys.readouterr()
    assert "token" not in captured.out
    assert "k1" not in captured.out
    assert "target" in captured.out
    assert "indoor" in captured.out
    assert "outdoor" in captured.out
    assert "Dehumidifier" not in captured.out
    assert "Air conditioner" in captured.out


def test_watch():
    namespace = Namespace(ip="1.2.3.4", id="123")
    ret = run_watch_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="", token=None, account=None)
    ret = run_watch_command(namespace)
    assert ret == 8
    namespace = Namespace(
        ip="1.2.3.4",
        id="",
        token="45",
        key="24",
        account=None,
        watchlevel=6,
        interval=20,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        run_watch_command(namespace)
    namespace = Namespace(
        ip=None,
        id="45",
        token=None,
        key=None,
        account="user@example.com",
        password="test",
        appkey="45",
        appid="1000",
        watchlevel=6,
        interval=20,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        run_watch_command(namespace)


def test_status():
    namespace = Namespace(ip=None, id=None)
    ret = run_watch_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="123")
    ret = run_status_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="", token=None, account=None)
    ret = run_status_command(namespace)
    assert ret == 8
    namespace = Namespace(
        ip="1.2.3.4",
        id="",
        token="45",
        key="24",
        account=None,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        run_status_command(namespace)
    namespace = Namespace(
        ip=None,
        id="45",
        token=None,
        key=None,
        account="user@example.com",
        password="test",
        appkey="45",
        appid="1000",
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        run_status_command(namespace)


def test_run_discover_command(capsys: pytest.CaptureFixture):
    mock_device = MagicMock()
    with patch("midea_beautiful.cli.find_appliances", side_effect=[[mock_device]]):
        namespace = Namespace(
            account="user@example.com",
            password="test",
            appkey="45",
            appid="1000",
            network=None,
            credentials=False,
        )
        res = run_discover_command(namespace)
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
    assert len(caplog.messages) == 1
    assert caplog.messages[0] == "Missing ip or appliance id"
    assert ret == 7
