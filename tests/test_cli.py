from argparse import Namespace
from unittest.mock import MagicMock, patch
import pytest
import pytest_socket
from midea_beautiful.cli import (
    cli,
    configure_argparser,
    output,
    run_discover_command,
    run_set_command,
    run_status_command,
)
from midea_beautiful.cloud import MideaCloud
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


def test_status():
    namespace = Namespace(ip=None, id=None)
    ret = run_status_command(namespace)
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
        appkey="876",
        appid="1000",
        cloud=True,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        run_status_command(namespace)


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
        res = run_status_command(namespace)
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
        res = run_status_command(namespace)
        assert res == 9
        assert len(caplog.messages) == 1
        assert caplog.messages[0], "Unable to get appliance status for '46'"


def test_run_discover_command(capsys: pytest.CaptureFixture):
    mock_device = MagicMock()
    with patch("midea_beautiful.cli.find_appliances", side_effect=[[mock_device]]):
        namespace = Namespace(
            account="user@example.com",
            password="test",
            appkey="876",
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


def test_set_command():
    namespace = Namespace(ip=None, id=None)
    ret = run_set_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="123")
    ret = run_set_command(namespace)
    assert ret == 7
    namespace = Namespace(ip="1.2.3.4", id="", token=None, account=None)
    ret = run_set_command(namespace)
    assert ret == 8
    namespace = Namespace(
        ip="1.2.3.4",
        id="",
        token="45",
        key="24",
        account=None,
    )
    with pytest.raises(pytest_socket.SocketBlockedError):
        run_set_command(namespace)
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
        run_set_command(namespace)


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
        run_set_command(namespace)
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
        res = run_set_command(namespace)
        assert res == 9
        assert len(caplog.messages) == 1
        assert caplog.messages[0], "Unable to get appliance status for '416'"
