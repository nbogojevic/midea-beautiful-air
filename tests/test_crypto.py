import binascii
from typing import Final
import unittest

from midea_beautiful.crypto import Security
from midea_beautiful.exceptions import AuthenticationError, MideaError, ProtocolError
from midea_beautiful.midea import (
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    MSGTYPE_ENCRYPTED_REQUEST,
)

APP_KEY: Final = DEFAULT_APPKEY


class TestSecurity(unittest.TestCase):
    def test_aes_encrypt_string(self) -> None:
        access_token = (
            "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801"
        )

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
        with self.assertRaises(MideaError):
            security.aes_encrypt_string(query)
        security.access_token = access_token
        assert security.access_token == access_token
        encrypted_string = security.aes_encrypt_string(query)
        self.assertEqual(expected_encrypted_str, encrypted_string)

    def test_aes_decrypt_string(self) -> None:
        access_token = (
            "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        )

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
        with self.assertRaises(MideaError):
            security.aes_decrypt_string(reply)

        security.access_token = access_token
        decoded_reply = security.aes_decrypt_string(reply)
        self.assertEqual(expected_decoded_reply, decoded_reply)

    def test_encrypt_password(self) -> None:
        security = Security(APP_KEY)
        expected_encrypted_password = (
            "f6a8f970344eb9b84f770d8eb9e8b511f4799bbce29bdef6990277783c243b5f"
        )
        encrypted_password = security.encrypt_password(
            "592758da-e522-4263-9cea-3bac916a0416", "passwordExample"
        )
        self.assertEqual(expected_encrypted_password, encrypted_password)

    def test_sign(self) -> None:
        security = Security(APP_KEY)
        expected_sign = (
            "d1d0b37a6cc407e9b8fcecc1f2e250f6a9cfd83cfbf7e4443d30a34cb4e9a62d"
        )
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

    def test_data_key(self) -> None:
        security = Security(APP_KEY)
        security.access_token = (
            "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        )
        self.assertEqual("23f4b15525824bc3", security.data_key)

    def test_decode_8730_exception(self) -> None:
        security = Security(APP_KEY)
        msg = "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        with self.assertRaises(ProtocolError):
            security.decode_8370(binascii.unhexlify(msg))

    def test_tcp_key(self) -> None:
        security = Security(APP_KEY)
        with self.assertRaises(AuthenticationError):
            security.tcp_key(b"ERROR", b"")
        with self.assertRaises(AuthenticationError):
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
        with self.assertRaises(AuthenticationError):
            security.tcp_key(binascii.unhexlify(msg_bad), key_bytes)

    def no_test_decode_8730(self) -> None:
        security = Security(APP_KEY)
        msg = "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        result, leftover = security.decode_8370(binascii.unhexlify(msg))
        print(result)
        print(leftover)
        assert False

    def test_encode_8730(self) -> None:
        security = Security(APP_KEY)
        msg = "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        msg_bytes = binascii.unhexlify(msg)
        with self.assertRaises(ProtocolError):
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

        assert result
        assert len(result) == 1
        assert result[0].hex() == msg
        assert len(incomplete) == 0

        extra = bytearray(encoded)
        extra.extend(b"\x00\x00")
        result, incomplete = security.decode_8370(extra)
        assert result
        assert len(result) == 1
        assert result[0].hex() == msg
        assert len(incomplete) == 2

        security._tcp_key = b""
        with self.assertRaises(ProtocolError):
            result, incomplete = security.decode_8370(msg_bytes)
