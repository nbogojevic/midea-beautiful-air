"""Test local network appliance scanner class"""
from binascii import unhexlify
import logging
import socket
from typing import Final
from unittest.mock import MagicMock, patch
import pytest
from midea_beautiful import find_appliances
from midea_beautiful.crypto import Security
import midea_beautiful.scanner as scanner
from midea_beautiful.util import Redacted, very_verbose

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name line-too-long
# pylint: disable=redefined-outer-name

BROADCAST_PAYLOAD: Final = (
    "020100c02c190000"
    "3030303030305030303030303030513131323334353637383941424330303030"
    "0b6e65745f61315f394142430000000001000000040000000000"
    "a1"
    "00000000000000"
    "123456789abc069fcd0300080103010000000000000000000000000000000000000000"
)

BROADCAST_PAYLOAD_AC: Final = (
    "020100c02c190000"
    "3030303030305030303030303030513131323334353637383941424330303030"
    "0b6e65745f61315f394142430000000001000000040000000000"
    "ac"
    "00000000000000"
    "123456789abc069fcd0300080103010000000000000000000000000000000000000000"
)

BROADCAST_PAYLOAD_NOT_SUPPORTED: Final = (
    "020100c02c190000"
    "3030303030305030303030303030513131323334353637383941424330303030"
    "0b6e65745f61315f394142430000000001000000040000000000"
    "a0"
    "00000000000000"
    "123456789abc069fcd0300080103010000000000000000000000000000000000000000"
)


class _TestException(Exception):
    pass


@pytest.fixture(name="broadcast_packet")
def broadcast_packet():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD))
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    return msg


@pytest.fixture(name="broadcast_packet_ac")
def broadcast_packet_ac():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD_AC))
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    return msg


@pytest.fixture(name="broadcast_packet_not_supported")
def broadcast_packet_not_supported():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD_NOT_SUPPORTED))
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    return msg


@pytest.fixture(name="lan_device_mocking")
def lan_device_mocking():
    x = MagicMock(appliance_id="456", type="a1", serial_number="X0456")
    y = MagicMock(appliance_id="999", type="a1", serial_number="X0999")
    y.__str__.return_value = "appliance-999"
    z = MagicMock(appliance_id="123", type="a1", serial_number="X0123")
    z.__str__.return_value = "appliance-123"
    q = MagicMock(appliance_id="345", type="ac", serial_number="X0345")
    q.__str__.return_value = "appliance-345"
    return [x, y, z, q]


@pytest.fixture(name="lan_device_not_supported")
def lan_device_not_supported():
    x = MagicMock(appliance_id="456", type="a0", serial_number="X0456")
    y = MagicMock(appliance_id="999", type="a1", serial_number="X0999")
    y.__str__.return_value = "appliance-999"
    z = MagicMock(appliance_id="123", type="a1", serial_number="X0123")
    z.__str__.return_value = "appliance-123"
    q = MagicMock(appliance_id="456", type="a1", serial_number="X0456")

    return [x, y, z, q]


@pytest.fixture(name="lan_device_with_update")
def lan_device_with_update():
    x = MagicMock(appliance_id="456", type="a0", serial_number="X0456")
    x.__str__.return_value = "appliance-456"
    y = MagicMock(appliance_id="999", type="a1", serial_number="X0999")
    y.__str__.return_value = "appliance-999"
    z = MagicMock(appliance_id="123", type="a1", serial_number="X0123")
    z.__str__.return_value = "appliance-123"
    q = MagicMock(appliance_id="123", type="a1", serial_number="X0123")
    q.__str__.return_value = "appliance-123-2"
    return [x, y, z, q, x]


def test_create_MideaDiscovery():
    with patch("socket.socket") as mock_socket:
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        discovery = scanner._MideaDiscovery(None)
        assert discovery._socket == mocked_socket


def test_MideaDiscovery_broadcast_message(caplog: pytest.LogCaptureFixture):
    with patch("socket.socket") as mock_socket:
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.sendto = MagicMock()
        discovery = scanner._MideaDiscovery(None)
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            discovery._broadcast_message(["255.255.255.255", "192.0.2.1"])
        assert len(caplog.records) == 2
        assert mocked_socket.sendto.call_count == 2
        mocked_socket.sendto.side_effect = ["", Exception("test")]
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            discovery._broadcast_message(["255.255.255.255", "192.0.2.1"])
        assert len(caplog.records) == 3
        assert caplog.messages[2] == "Unable to send broadcast to: 192.0.2.1 cause test"


def test_discover_appliances(
    mock_cloud,
    caplog: pytest.LogCaptureFixture,
    broadcast_packet,
    broadcast_packet_ac,
    lan_device_mocking,
):
    # This is same as test_scanner_find_appliances
    with (
        patch("midea_beautiful.scanner.LanDevice", side_effect=lan_device_mocking),
        patch("socket.socket") as mock_socket,
        caplog.at_level(logging.DEBUG),
    ):
        very_verbose(True)
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet), ["192.0.2.5"]),
            (unhexlify(broadcast_packet), ["192.0.2.1"]),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.2.6"]),
            (unhexlify(broadcast_packet_ac), ["192.0.2.7"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "123", "name": "name-123", "type": "0xa1", "sn": "X0123"},
            {"id": "345", "name": "name-345", "type": "0xac", "sn": "X0345"},
        ]
        caplog.clear()
        res = find_appliances(cloud=mock_cloud)
        assert len(res) == 3
        assert res[0].appliance_id == "456"
        assert res[1].appliance_id == "123"
        assert res[2].appliance_id == "345"
        assert len(caplog.records) == 20
        assert "the account: appliance-999" in str(caplog.messages[10])


def test_discover_appliances_no_cloud(
    caplog: pytest.LogCaptureFixture,
    broadcast_packet,
    broadcast_packet_ac,
    lan_device_mocking,
):
    # This is same as test_scanner_find_appliances
    with (
        patch("midea_beautiful.scanner.LanDevice", side_effect=lan_device_mocking),
        patch("socket.socket") as mock_socket,
    ):
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet), ["192.0.2.5"]),
            (unhexlify(broadcast_packet), ["192.0.2.1"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet_ac), ["192.0.2.7"]),
            (unhexlify(broadcast_packet), ["192.0.2.6"]),
            socket.timeout("timeout"),
        ]

        caplog.clear()
        res = find_appliances()
        assert len(res) == 4
        assert res[0].appliance_id == "456"
        assert res[1].appliance_id == "999"
        assert res[2].appliance_id == "123"
        assert res[3].appliance_id == "345"
        assert len(caplog.records) == 0


def test_scanner_find_appliances(
    mock_cloud, caplog: pytest.LogCaptureFixture, broadcast_packet, lan_device_mocking
):
    with (
        patch("midea_beautiful.scanner.LanDevice", side_effect=lan_device_mocking),
        patch("socket.socket") as mock_socket,
    ):
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet), ["192.0.2.5"]),
            (unhexlify(broadcast_packet), ["192.0.2.1"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.2.6"]),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "123", "name": "name-123", "type": "0xa1", "sn": "X0123"},
        ]
        caplog.clear()
        res = find_appliances(cloud=mock_cloud)
        assert len(res) == 2
        assert res[0].appliance_id == "456"
        assert res[1].appliance_id == "123"
        assert len(caplog.records) == 1
        assert "the account: appliance-999" in str(caplog.messages[0])


def test_scanner_find_appliances_changed_id(
    mock_cloud, caplog: pytest.LogCaptureFixture, broadcast_packet, lan_device_mocking
):
    with (
        patch("midea_beautiful.scanner.LanDevice", side_effect=lan_device_mocking),
        patch("socket.socket") as mock_socket,
    ):
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        # mock_socket.timeout = socket.timeout
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet), ["192.0.2.5"]),
            (unhexlify(broadcast_packet), ["192.0.2.1"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.2.6"]),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "124", "name": "name-124", "type": "0xa1", "sn": "X0123"},
        ]
        caplog.clear()
        res = find_appliances(cloud=mock_cloud)
        assert len(res) == 2
        assert res[0].appliance_id == "456"
        assert res[1].appliance_id == "123"
        assert res[1].name == "name-124"
        assert res[1].serial_number == "X0123"
        assert len(caplog.records) == 1
        assert "the account: appliance-999" in str(caplog.messages[0])


def test_scanner_find_appliances_missing(mock_cloud, caplog: pytest.LogCaptureFixture):
    x = MagicMock()
    x.appliance_id = "456"
    y = MagicMock()
    y.appliance_id = "999"
    y.__str__.return_value = "appliance-999"
    Redacted.redacting = False

    with patch("midea_beautiful.scanner.LanDevice", side_effect=[x, y]):
        with patch("socket.socket") as mock_socket:
            mocked_socket = MagicMock()
            mock_socket.return_value = mocked_socket
            mocked_socket.recvfrom.side_effect = [
                socket.timeout("timeout"),
                socket.timeout("timeout"),
                socket.timeout("timeout"),
            ]
            mock_cloud.list_appliances.return_value = [
                {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"}
            ]
            caplog.clear()
            res = find_appliances(cloud=mock_cloud)
            assert len(res) == 1
            assert res[0].appliance_id == "456"
            assert len(caplog.records) == 2
            assert (
                str(caplog.messages[0])
                == "Some appliance(s) where not discovered on local network: 0 discovered out of 1"  # noqa: E501
            )
            assert (
                str(caplog.messages[1])
                == "Unable to discover registered appliance {'id': '456', 'name': 'name-456', 'type': '0xa1', 'sn': 'X0456'}"  # noqa: E501
            )


def test_find_appliances_cloud(mock_cloud: MagicMock):
    """This tests function from main module"""
    with (
        patch("midea_beautiful.MideaCloud", return_value=mock_cloud) as mc,
        patch.object(mock_cloud, "authenticate", side_effect=_TestException()) as auth,
    ):
        with pytest.raises(_TestException):
            find_appliances(account="user@example.com", password="wordpass")
        mc.assert_called()
        auth.assert_called()


def test_scanner_find_appliances_not_supported(
    mock_cloud,
    caplog: pytest.LogCaptureFixture,
    broadcast_packet,
    broadcast_packet_not_supported,
    lan_device_not_supported,
):
    with (
        patch(
            "midea_beautiful.scanner.LanDevice", side_effect=lan_device_not_supported
        ),
        patch("socket.socket") as mock_socket,
    ):
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet_not_supported), ["192.0.2.5"]),
            (unhexlify(broadcast_packet_not_supported), ["192.0.2.1"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.2.6"]),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "123", "name": "name-123", "type": "0xa1", "sn": "X0123"},
        ]
        caplog.clear()
        res = find_appliances(cloud=mock_cloud)
        assert len(res) == 2
        assert res[0].appliance_id == "123"
        assert res[1].appliance_id == "456"
        assert len(caplog.records) == 3
        assert "the account: appliance-999" in str(caplog.messages[0])


def test_scanner_find_appliances_with_update(
    mock_cloud,
    caplog: pytest.LogCaptureFixture,
    broadcast_packet,
    broadcast_packet_not_supported,
    lan_device_with_update,
):
    with (
        patch("midea_beautiful.scanner.LanDevice", side_effect=lan_device_with_update),
        patch("socket.socket") as mock_socket,
    ):
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet_not_supported), ["192.0.2.5"]),
            (unhexlify(broadcast_packet_not_supported), ["192.0.2.1"]),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.2.6"]),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.2.7"]),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "123", "name": "name-123", "type": "0xa1", "sn": "X0123"},
        ]
        caplog.clear()
        res = find_appliances(cloud=mock_cloud)
        assert len(res) == 2
        print(res)
        assert res[0].appliance_id == "123"
        assert res[1].appliance_id == "456"
        assert len(caplog.records) == 3
        assert "the account: appliance-999" in str(caplog.messages[0])
