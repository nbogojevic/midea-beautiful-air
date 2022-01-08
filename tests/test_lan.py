from binascii import unhexlify
from datetime import datetime
from pytest import LogCaptureFixture
import socket
from typing import Final
from unittest.mock import patch

import pytest

from midea_beautiful.crypto import Security
from midea_beautiful.exceptions import MideaError, MideaNetworkError
from midea_beautiful.lan import LanDevice, get_appliance_state
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APPKEY,
)

APP_KEY: Final = DEFAULT_APPKEY


BROADCAST_PAYLOAD: Final = (
    "020100c02c190000"
    "3030303030305030303030303030513131323334353637383941424330303030"
    "0b6e65745f61315f394142430000000001000000040000000000"
    "a1"
    "00000000000000"
    "123456789abc069fcd0300080103010000000000000000000000000000000000000000"
)


def test_lan_packet_header_ac() -> None:
    expected_header = unhexlify("5a5a01116800200000000000")

    device = LanDevice(id=str(0x12345), appliance_type=APPLIANCE_TYPE_AIRCON)
    cmd = device.state.refresh_command()
    now = datetime.now()
    res = device._lan_packet(cmd)
    assert expected_header == res[: len(expected_header)]
    if now.minute < 59:
        assert now.hour == res[15]
        if now.hour < 23:
            assert now.day == res[16]
            assert now.month == res[17]
            assert now.year % 100 == res[18]
            assert int(now.year / 100) == res[19]

    assert 0x45 == res[20]
    assert 0x23 == res[21]
    assert 0x01 == res[22]
    assert 0x00 == res[23]


def test_lan_packet_header_dehumidifier() -> None:
    expected_header = unhexlify("5a5a01116800200000000000")

    device = LanDevice(id=str(0x12345), appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
    cmd = device.state.refresh_command()
    now = datetime.now()
    res = device._lan_packet(cmd)
    assert expected_header == res[: len(expected_header)]
    if now.minute < 59:
        assert now.hour == res[15]
        if now.hour < 23:
            assert now.day == res[16]
            assert now.month == res[17]
            assert now.year % 100 == res[18]
            assert int(now.year / 100) == res[19]

    assert 0x45 == res[20]
    assert 0x23 == res[21]
    assert 0x01 == res[22]
    assert 0x00 == res[23]


def test_appliance_from_broadcast():
    msg = (
        "837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        "0000000000000000000000000000"
        "c136771d628d08f90ca694ad1a5893b77c7ea4ac6fed1dc7e2670058df2f44675638"
        "d33cddd5727c581d84b87f54b944bbc7440daf21c3fa9cab7b342b84ac6a630967cd"
        "7d9364d23d4d7a91591e277d90b13be000894715b606127e07c2fecff31443d17c3a"
        "ac03a7656614ae1dca44"
        "8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    response = unhexlify(msg)
    token = "TOKEN"
    key = "KEY"
    appliance = LanDevice(data=response, token=token, key=key)
    assert "123456789abc" == appliance.mac
    assert "000000P0000000Q1123456789ABC0000" == appliance.sn
    assert "net_a1_9ABC" == appliance.ssid
    assert "0xa1" == appliance.type


def test_appliance_from_broadcast_dehumidifier():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD))
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    response = unhexlify(msg)
    token = "TOKEN"
    key = "KEY"
    appliance = LanDevice(data=response, token=token, key=key)
    assert "123456789abc" == appliance.mac
    assert "000000P0000000Q1123456789ABC0000" == appliance.sn
    assert "net_a1_9ABC" == appliance.ssid
    assert "0xa1" == appliance.type


def test_appliance_repr():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD))
    payload[46] = 0x63  # Letter c
    payload[66] = int(APPLIANCE_TYPE_AIRCON, base=16)
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    response = unhexlify(msg)
    token = "TOKEN"
    key = "KEY"
    appliance = LanDevice(data=response, token=token, key=key)
    assert str(appliance) == "id=6618611909121 ip=192.0.1.2:6444 version=3"
    assert repr(appliance)[:31], "{id=6618611909121 == ip=192.0.1.2"


def test_appliance_from_broadcast_ac():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD))
    payload[46] = 0x63  # Letter c
    payload[66] = int(APPLIANCE_TYPE_AIRCON, base=16)
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    response = unhexlify(msg)
    token = "TOKEN"
    key = "KEY"
    appliance = LanDevice(data=response, token=token, key=key)
    assert 3 == appliance.version
    assert "123456789abc" == appliance.mac
    assert "000000P0000000Q1123456789ABC0000" == appliance.sn
    assert "net_ac_9ABC" == appliance.ssid
    assert "0xac" == appliance.type
    assert "Air conditioner" == appliance.state.model


def test_appliance_from_broadcast_unknown_protocol():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD))
    payload[46] = 0x63  # Letter c
    payload[66] = int(APPLIANCE_TYPE_AIRCON, base=16)
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"830000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    response = unhexlify(msg)
    token = "TOKEN"
    key = "KEY"
    appliance = LanDevice(data=response, token=token, key=key)
    assert 0 == appliance.version


def test_appliance_from_broadcast_v2():
    payload = bytearray(unhexlify(BROADCAST_PAYLOAD))
    payload[46] = 0x63  # Letter c
    payload[66] = int(APPLIANCE_TYPE_AIRCON, base=16)
    encrypted = Security().aes_encrypt(payload)
    msg = (
        f"5a5a00b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
        f"0000000000000000000000000000"
        f"{encrypted.hex()}"
        f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
    )
    response = unhexlify(msg)
    token = ""
    key = ""
    appliance = LanDevice(data=response, token=token, key=key)
    assert 2 == appliance.version
    assert "123456789abc" == appliance.mac
    assert "000000P0000000Q1123456789ABC0000" == appliance.sn
    assert "net_ac_9ABC" == appliance.ssid
    assert "0xac" == appliance.type
    assert "Air conditioner" == appliance.state.model


def test_update():
    device1 = LanDevice(id=str(0x12345), appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
    device2 = LanDevice(id=str(0x54321), appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
    device2.ip = "192.0.100.0"
    assert device1.ip != device2.ip
    device1.update(device2)
    assert device1.ip == device2.ip


def test_get_appliance_state_cloud(mock_cloud):
    # caplog.set_level(logging.INFO)
    with pytest.raises(MideaError):
        get_appliance_state()
    with pytest.raises(MideaError):
        get_appliance_state(id="12345")

    mock_cloud.list_appliances.return_value = [{"id": "12345", "name": "name-123"}]
    device = get_appliance_state(id="12345", cloud=mock_cloud, use_cloud=True)
    assert device is not None
    assert device.id == "12345"
    assert device.name == "name-123"


def test_get_appliance_state_set_state_cloud(mock_cloud):
    device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
    device.set_state(cloud=mock_cloud)
    assert device is not None
    assert device.id == "12345"


def test_get_appliance_state_set_state_non_existing(
    mock_cloud, caplog: LogCaptureFixture
):
    device = LanDevice(id="22222", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
    # with self.assertLogs("midea_beautiful.lan", logging.WARNING):
    caplog.clear()
    device.set_state(cloud=mock_cloud, non_existing_property="12")
    assert len(caplog.messages) == 1
    assert (
        caplog.messages[0]
        == "Unknown state attribute non_existing_property for id=22222 ip=None:6444 version=3"  # noqa: E501
    )


def test_get_appliance_state_lan(mock_cloud):
    handshake_response = b"\x83p\x00@ \x01\x00\x00\xce\xa2v\x8b\xcb4\x18\xc9)tl% x\x9eB\xab\x02\xde4\x1c(\xc7U\xe8\xca\xcf\x8a%9D\xd47\x89P\x8d\x11\x8a-\xa0\xea0\x1f\xcc\xa6\xca)a\xd0i\xf7S](\xbf+\xb9k\xbb\n;\xbf\xc7\x94"  # noqa: E501
    token = "C20C7C023E1FA937BABA24D3EBABA87BABAFF07A12AA808DBABAA768BABA94130012000000000000000000003400000000000000560000000000000000000000"  # noqa: E501
    key = "0012000000000000000000003400000000000000560000000000000000000000"
    mock_cloud.get_token.return_value = (token, key)
    broadcast_packet = "8207000a2c19000030303030303050303030303030305131413036383143304137443630303030300b6e65745f61315f374436300000000001000000040000000000a100000000000000a0681c0a7d60069fcd0300080103010000000000000000000000000000000000000000"  # noqa: E501
    with patch("socket.socket") as mock_socket:

        mock_socket.return_value.recv.return_value = handshake_response
        with patch("midea_beautiful.crypto.Security") as mock_security:
            mock_security.aes_decrypt.return_value = unhexlify(broadcast_packet)
            mock_security.decode_8370.return_value = (
                [
                    b"ZZ\x01\x11X\x00 \x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xe2\xc2\x03\x00\x00\x1d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x8b\x0c\x05\x8f=\xcbml\xff\x95\x16\xd1c\x9e\xc2\xcf\xa1\xdd\xe0\x82\\\xdc\x94\x1aR\x0eFV\xecq7\xff\x96\x0c{Vdt\xde\xe0\xd2}r\xb7>B\xde\xce"  # noqa: E501
                ],
                b"",
            )
            device = get_appliance_state(
                ip="192.0.13.14", cloud=mock_cloud, security=mock_security
            )
            assert device is not None
            assert device.id == "2934580344864"
            assert device.model == "Dehumidifier"
            assert device.name == "2934580344864"


def test_get_appliance_state_socket_timeout(mock_cloud):
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.connect.side_effect = socket.timeout("test")
        with pytest.raises(MideaNetworkError) as ex:
            get_appliance_state(ip="192.0.20.21", cloud=mock_cloud)
        assert (
            "Timeout while connecting to appliance 192.0.20.21:6445" == ex.value.message
        )


def test_get_appliance_state_socket_error(mock_cloud):
    with patch("socket.socket") as mock_socket:
        mock_socket.return_value.connect.side_effect = socket.error("test")
        with pytest.raises(MideaNetworkError) as ex:
            get_appliance_state(ip="192.0.20.22", cloud=mock_cloud)
        assert "Could not connect to appliance 192.0.20.22:6445" == ex.value.message
