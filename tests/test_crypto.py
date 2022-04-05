"""Test encryption functions"""
import binascii
from typing import Final

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import pytest

from midea_beautiful.crypto import Security
from midea_beautiful.exceptions import AuthenticationError, MideaError, ProtocolError
from midea_beautiful.midea import (
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    INTERNAL_KEY,
    MSGTYPE_ENCRYPTED_REQUEST,
    decrypt_internal,
)

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name line-too-long

APP_KEY: Final = DEFAULT_APPKEY


def test_aes_encrypt_string() -> None:
    access_token = "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801"

    query = (
        "90,90,1,0,89,0,32,0,1,0,0,0,39,36,17,9,13,10,18,20,-38,73,0,0,0,16,0,0,0,"
        "0,0,0,0,0,0,0,0,0,0,0,-86,32,-95,0,0,0,0,0,3,3,65,33,0,-1,3,0,0,2,0,0,0,0,"
        "0,0,0,0,0,0,0,0,11,36,-92,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
    )
    expected_encrypted_str = (
        "7c8911b6de8e29fa9a1538def06c9018a9995980893554fb80fd87c5478ac78b360f7b3543"
        "3b8d451464bdcd3746c4f5c05a8099eceb79aeb9cc2cc712f90f1c9b3bb091bcf0e90bddf6"
        "2d36f29550796c55acf8e637f7d3d68d11be993df933d94b2b43763219c85eb21b4d9bb989"
        "1f1ab4ccf24185ccbcc78c393a9212c24bef3466f9b3f18a6aabcd58e80ce9df61ccf13885"
        "ebd714595df69709f09722ff41eb37ea5b06f727b7fab01c94588459ccf13885ebd714595d"
        "f69709f09722ff32b544a259d2fa6e7ddaac1fdff91bb0"
    )
    security = Security(APP_KEY)
    with pytest.raises(MideaError):
        security.aes_encrypt_string(query)
    security.access_token = access_token
    assert security.access_token == access_token
    encrypted_string = security.aes_encrypt_string(query)
    assert expected_encrypted_str == encrypted_string


def test_aes_decrypt_string() -> None:
    access_token = "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"

    reply = (
        "02940d3220c4a1a1fcfb4e8593a93c0facebf2d3d170c089f8c9d7274f8048462f8d8a"
        "c5ab6b8073382dbc9b9dcc63c293b3dffc38a7bb66832fb4ae3514a40873768e0b3c6c"
        "c653c5802496e2b271cba2bfc89ca102623370e8901845328834c53227ac9ea088605e"
        "e64825413692b1df952de8baf0dd76ecd34202f91dcc4908baeaf21a29ca4c11203f2c"
        "984fd282ec23185ce83c99215494482d87bebdcb3b31f06f44f810c15404be14b1ed8b"
        "f090f1e835d796869adf20bf35ff5b7ebc73768e0b3c6cc653c5802496e2b271cb6eb1"
        "66994a36e79b29551a0dc87fed53"
    )
    expected_decoded_reply = (
        "90,90,1,0,91,0,32,-128,1,0,0,0,0,0,0,0,0,0,0,0,-38,73,"
        "0,0,0,16,0,0,0,0,0,0,0,0,0,0,1,0,0,0,-86,34,-95,0,0,0,"
        "0,0,3,3,-56,1,4,80,127,127,0,35,0,64,0,0,0,0,0,0,61,86,"
        "0,0,0,0,-92,-85,-41,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
    )
    security = Security(APP_KEY)
    with pytest.raises(MideaError):
        security.aes_decrypt_string(reply)

    security.access_token = access_token
    decoded_reply = security.aes_decrypt_string(reply)
    assert expected_decoded_reply == decoded_reply


def test_encrypt_password() -> None:
    security = Security(APP_KEY)
    expected_encrypted_password = (
        "f6a8f970344eb9b84f770d8eb9e8b511f4799bbce29bdef6990277783c243b5f"
    )
    encrypted_password = security.encrypt_password(
        "592758da-e522-4263-9cea-3bac916a0416", "passwordExample"
    )
    assert expected_encrypted_password == encrypted_password


def test_sign() -> None:
    security = Security(APP_KEY)
    expected_sign = "d1d0b37a6cc407e9b8fcecc1f2e250f6a9cfd83cfbf7e4443d30a34cb4e9a62d"
    args = {
        "loginAccount": "user@example.com",
        "appId": DEFAULT_APP_ID,
        "clientType": 1,
        "format": 2,
        "language": "en_US",
        "src": 17,
        "stamp": 20211226190000,
    }
    sign = security.sign("/v1/user/login/id/get", args)
    assert expected_sign == sign


def test_data_key() -> None:
    security = Security(APP_KEY)
    security.access_token = (
        "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
    )
    assert security.data_key == "23f4b15525824bc3"


def test_decode_8730_exception() -> None:
    security = Security(APP_KEY)
    msg = "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
    with pytest.raises(ProtocolError):
        security.decode_8370(binascii.unhexlify(msg))


def test_tcp_key() -> None:
    security = Security(APP_KEY)
    with pytest.raises(AuthenticationError):
        security.tcp_key(b"ERROR", b"")
    with pytest.raises(AuthenticationError):
        security.tcp_key(b"TOOSHORT", b"")
    msg_good = (
        "d4de051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        "a2cb561936668c8f117d2ec0d5b74ba8c9a8381650c1ba2b42359af7baafdd00"
    )
    key = "a1a0b37a6cc407e9b8fcecc1f2e250f6a9cfd83cfbf7e4443d30a34cb4e9a62d"
    key_bytes = binascii.unhexlify(key)
    tcp_key = security.tcp_key(binascii.unhexlify(msg_good), key_bytes)

    assert (
        tcp_key.hex()
        == "e047884511f9504a074dfeed0451bcff4f63d8d8aa779fa03d3049027d0ac78b"
    )
    msg_bad = (
        "a4ae051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        "ffff5652c2faa70eaeae6c8b50d0af9a9a227f02cbab0161b9bd3abf59c75244"
    )
    with pytest.raises(AuthenticationError):
        security.tcp_key(binascii.unhexlify(msg_bad), key_bytes)


def test_encode_8730() -> None:
    security = Security(APP_KEY)
    msg = "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
    msg_bytes = binascii.unhexlify(msg)
    with pytest.raises(ProtocolError):
        security.encode_8370(msg_bytes, MSGTYPE_ENCRYPTED_REQUEST)
    security._tcp_key = binascii.unhexlify(
        "d1d0b37a6cc407e9b8fcecc1f2e250f6a9cfd83cfbf7e4443d30a34cb4e9a62d"
    )

    encoded = security.encode_8370(msg_bytes, MSGTYPE_ENCRYPTED_REQUEST)
    print(encoded.hex())
    result, incomplete = security.decode_8370(encoded[0:-2])
    assert len(result) == 0
    assert incomplete.hex() == encoded[0:-2].hex()

    result, incomplete = security.decode_8370(encoded)
    print(result[0].hex())

    assert result is not None
    assert len(result) == 1
    assert result[0].hex() == msg
    assert len(incomplete) == 0

    extra = bytearray(encoded)
    extra.extend(b"\x00\x00")
    result, incomplete = security.decode_8370(extra)
    assert result is not None
    assert len(result) == 1
    assert result[0].hex() == msg
    assert len(incomplete) == 2

    security._tcp_key = b""
    with pytest.raises(ProtocolError):
        result, incomplete = security.decode_8370(msg_bytes)


def test_sign_proxied() -> None:
    # spell-checker: ignore meicloud babadeda
    security = Security(
        "ac21b9f9cbfe4ca5a88562ef25e2b768",
        iotkey="meicloud",
        hmackey="PROD_VnoClJI9aikS8dyy",
    )  # noqa: E501
    data = '{"appVersion":"2.22.0","src":"10","retryCount":"3","format":2,"androidApiLevel":"27","stamp":"20220216161350","language":"en","platformId":"1","userName":"test@example.com","clientVersion":"2.22.0","deviceId":"babadeda","reqId":"d0f7eb1638e3480bbbde67a22bf41298","uid":"","clientType":1,"appId":"1010","userType":"0","appVNum":"2.22.0","deviceBrand":"Test device"}'  # noqa: E501
    random_value = "1645024430315"
    sign = security.sign_proxied(None, data, random_value)
    assert sign == "63c353e308fd7b6d1b84c55aedfbc70624974a6251d5f2992d408cd82135b812"


def _encrypt_internal(data: str) -> str:
    raw = data.encode("utf-8")
    padder = padding.PKCS7(16 * 8).padder()
    raw = padder.update(raw) + padder.finalize()
    cipher = Cipher(algorithms.AES(INTERNAL_KEY), modes.ECB())  # nosec
    encryptor = cipher.encryptor()
    result: bytes = encryptor.update(raw) + encryptor.finalize()
    return result.hex()


def test_encrypt_internal_iot_key() -> None:
    encrypted = _encrypt_internal("meicloud")
    output = decrypt_internal(encrypted)
    assert encrypted == "f4dcd1511147af45775d7e680ac5312b"
    assert output == "meicloud"


def test_encrypt_internal_hmac_key() -> None:
    encrypted = _encrypt_internal("PROD_VnoClJI9aikS8dyy")
    output = decrypt_internal(encrypted)
    assert (
        encrypted == "5018e65c32bcec087e6c01631d8cf55398308fc19344d3e130734da81ac2e162"
    )
    assert output == "PROD_VnoClJI9aikS8dyy"


def test_encrypt_m_smart_home() -> None:
    sn_str = "5c824364d8080ffcba3325fe4e795bd53fdf5ef14023f9e7a9b05035ec3e878c3f77cba43e211073d6b919d4a436675b"  # noqa: E501
    random_data = "869b74f01fc6c9cd6828ad22d408deab827337bcfd9af0b2b2af43d49390ac68"
    access_token = "81380e2c734451510a051a49f05104656eaea6a2d186e6a3596016770258dc55"
    app_key_str = "ac21b9f9cbfe4ca5a88562ef25e2b768"
    security = Security(app_key_str)
    security.set_access_token(access_token, random_data)
    assert security._data_iv == "9c997e4ec1044dc5"
    assert security._data_key == "4f6e2bf02f174807"
    sn = security.aes_decrypt_string(sn_str)
    assert "Q13C2" in sn
