from binascii import unhexlify
import socket
from typing import Final
from unittest.mock import MagicMock, patch
import pytest
from midea_beautiful.crypto import Security
from midea_beautiful.exceptions import MideaError
import midea_beautiful.scanner as scanner

BROADCAST_PAYLOAD: Final = (
    "020100c02c190000"
    "3030303030305030303030303030513131323334353637383941424330303030"
    "0b6e65745f61315f394142430000000001000000040000000000"
    "a1"
    "00000000000000"
    "123456789abc069fcd0300080103010000000000000000000000000000000000000000"
)


def test_get_broadcast_addresses():
    networks = scanner._get_broadcast_addresses(["192.0.1.2"])
    assert len(networks) == 1
    assert networks[0] == "192.0.1.2"


def test_get_broadcast_addresses_range():
    networks = scanner._get_broadcast_addresses(["192.0.2.0/27"])
    assert len(networks) == 1
    assert networks[0] == "192.0.2.31"


def test_get_broadcast_addresses_multiple_provided():
    networks = scanner._get_broadcast_addresses(
        [
            "192.0.1.0/27",
            "127.0.0.1",
            "192.0.2.0/26",
        ]
    )
    assert len(networks) == 2
    assert networks[0] == "192.0.1.31"
    assert networks[1] == "192.0.2.63"


def test_can_specify_public_address():
    networks = scanner._get_broadcast_addresses(["8.8.8.8"])
    assert len(networks) == 1
    assert networks[0] == "8.8.8.8"


def test_no_adapters():
    with patch("midea_beautiful.scanner.get_adapters", return_value=[]):
        with pytest.raises(MideaError) as ex:
            scanner._get_broadcast_addresses([])
        assert ex.value.message == "No valid networks to send broadcast to"


@pytest.fixture(name="adapter_10_1_2_0")
def adapter_10_1_2_0():
    ip1 = MagicMock()
    ip1.is_IPv4 = True
    ip1.ip = "10.1.2.0"
    ip1.network_prefix = 25
    adapter = MagicMock()
    adapter.ips = [ip1]
    return adapter


@pytest.fixture(name="adapter_192_0_2_0")
def adapter_192_0_2_0():
    ip1 = MagicMock()
    ip1.is_IPv4 = True
    ip1.ip = "192.0.2.0"
    ip1.network_prefix = 25
    adapter = MagicMock()
    adapter.ips = [ip1]
    return adapter


@pytest.fixture(name="adapter_8_8_8_0")
def adapter_8_8_8_0():
    ip1 = MagicMock()
    ip1.is_IPv4 = True
    ip1.ip = "8.8.8.0"
    ip1.network_prefix = 25
    adapter = MagicMock()
    adapter.ips = [ip1]
    return adapter


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


@pytest.fixture(name="lan_device_mocking")
def lan_device_mocking():
    x = MagicMock()
    x.id = "456"
    x.sn = "X0456"
    y = MagicMock()
    y.id = "999"
    y.sn = "X0999"
    y.__str__.return_value = "appliance-999"
    z = MagicMock()
    z.id = "123"
    z.sn = "X0123"
    z.__str__.return_value = "appliance-123"
    return [x, y, z]


def test_one_adapter(adapter_10_1_2_0):
    with patch("midea_beautiful.scanner.get_adapters", return_value=[adapter_10_1_2_0]):
        networks = scanner._get_broadcast_addresses([])
        assert len(networks) == 1


def test_two_adapters(adapter_10_1_2_0, adapter_192_0_2_0, adapter_8_8_8_0):
    with patch(
        "midea_beautiful.scanner.get_adapters",
        return_value=[adapter_10_1_2_0, adapter_192_0_2_0, adapter_8_8_8_0],
    ):
        networks = scanner._get_broadcast_addresses([])
        assert len(networks) == 2


def test_get_broadcast_addresses_raise_on_local_only():
    with pytest.raises(MideaError) as ex:
        scanner._get_broadcast_addresses(["127.0.0.2", "127.0.0.1"])

    assert ex.value.message == "No valid networks to send broadcast to"


def test_create_MideaDiscovery():
    with patch("socket.socket") as mock_socket:
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        discovery = scanner.MideaDiscovery(None)
        assert discovery._socket == mocked_socket


def test_create_find_appliances(
    mock_cloud, caplog: pytest.LogCaptureFixture, broadcast_packet, lan_device_mocking
):
    with (
        patch("midea_beautiful.scanner.LanDevice", side_effect=lan_device_mocking),
        patch("socket.socket") as mock_socket,
    ):
        mocked_socket = MagicMock()
        mock_socket.return_value = mocked_socket
        mocked_socket.recvfrom.side_effect = [
            (unhexlify(broadcast_packet), ["192.0.4.5"]),
            (unhexlify(broadcast_packet), ["192.0.4.1"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.4.6"]),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "123", "name": "name-123", "type": "0xa1", "sn": "X0123"},
        ]
        caplog.clear()
        res = scanner.find_appliances(cloud=mock_cloud)
        assert len(res) == 2
        assert res[0].id == "456"
        assert res[1].id == "123"
        assert len(caplog.messages) == 1
        assert (
            str(caplog.messages[0])
            == "Found an appliance that is not registered to the account: appliance-999"  # noqa: E501
        )


def test_create_find_appliances_changed_id(
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
            (unhexlify(broadcast_packet), ["192.0.4.5"]),
            (unhexlify(broadcast_packet), ["192.0.4.1"]),
            socket.timeout("timeout"),
            socket.timeout("timeout"),
            (unhexlify(broadcast_packet), ["192.0.4.6"]),
            socket.timeout("timeout"),
        ]
        mock_cloud.list_appliances.return_value = [
            {"id": "456", "name": "name-456", "type": "0xa1", "sn": "X0456"},
            {"id": "124", "name": "name-124", "type": "0xa1", "sn": "X0123"},
        ]
        caplog.clear()
        res = scanner.find_appliances(cloud=mock_cloud)
        assert len(res) == 2
        assert res[0].id == "456"
        assert res[1].id == "123"
        assert res[1].name == "name-124"
        assert res[1].sn == "X0123"
        assert len(caplog.messages) == 1
        assert (
            str(caplog.messages[0])
            == "Found an appliance that is not registered to the account: appliance-999"  # noqa: E501
        )


def test_create_find_appliances_missing(mock_cloud, caplog: pytest.LogCaptureFixture):
    x = MagicMock()
    x.id = "456"
    y = MagicMock()
    y.id = "999"
    y.__str__.return_value = "appliance-999"
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
            res = scanner.find_appliances(cloud=mock_cloud)
            assert len(res) == 1
            assert res[0].id == "456"
            assert len(caplog.messages) == 2
            assert (
                str(caplog.messages[0])
                == "Some appliance(s) where not discovered on local network(s): 0 discovered out of 1"  # noqa: E501
            )
            assert (
                str(caplog.messages[1])
                == "Unable to discover registered appliance {'id': '456', 'name': 'name-456', 'type': '0xa1', 'sn': 'X0456'}"  # noqa: E501
            )
