from __future__ import annotations

import logging
from hashlib import md5, sha256
from os import urandom
from typing import Any, Final
from urllib.parse import unquote_plus, urlencode, urlparse

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from midea_beautiful_dehumidifier.util import hex4log
from midea_beautiful_dehumidifier.midea import (
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_ENCRYPTED_RESPONSE,
)

_LOGGER = logging.getLogger(__name__)


def _strxor(plain_text, key):
    # returns plain text by repeatedly xoring it with key
    pt = plain_text
    len_key = len(key)
    encoded = []

    for i in range(0, len(pt)):
        encoded.append(pt[i] ^ key[i % len_key])
    return bytes(encoded)


crc8_854_table = [
    0x00,
    0x5E,
    0xBC,
    0xE2,
    0x61,
    0x3F,
    0xDD,
    0x83,
    0xC2,
    0x9C,
    0x7E,
    0x20,
    0xA3,
    0xFD,
    0x1F,
    0x41,
    0x9D,
    0xC3,
    0x21,
    0x7F,
    0xFC,
    0xA2,
    0x40,
    0x1E,
    0x5F,
    0x01,
    0xE3,
    0xBD,
    0x3E,
    0x60,
    0x82,
    0xDC,
    0x23,
    0x7D,
    0x9F,
    0xC1,
    0x42,
    0x1C,
    0xFE,
    0xA0,
    0xE1,
    0xBF,
    0x5D,
    0x03,
    0x80,
    0xDE,
    0x3C,
    0x62,
    0xBE,
    0xE0,
    0x02,
    0x5C,
    0xDF,
    0x81,
    0x63,
    0x3D,
    0x7C,
    0x22,
    0xC0,
    0x9E,
    0x1D,
    0x43,
    0xA1,
    0xFF,
    0x46,
    0x18,
    0xFA,
    0xA4,
    0x27,
    0x79,
    0x9B,
    0xC5,
    0x84,
    0xDA,
    0x38,
    0x66,
    0xE5,
    0xBB,
    0x59,
    0x07,
    0xDB,
    0x85,
    0x67,
    0x39,
    0xBA,
    0xE4,
    0x06,
    0x58,
    0x19,
    0x47,
    0xA5,
    0xFB,
    0x78,
    0x26,
    0xC4,
    0x9A,
    0x65,
    0x3B,
    0xD9,
    0x87,
    0x04,
    0x5A,
    0xB8,
    0xE6,
    0xA7,
    0xF9,
    0x1B,
    0x45,
    0xC6,
    0x98,
    0x7A,
    0x24,
    0xF8,
    0xA6,
    0x44,
    0x1A,
    0x99,
    0xC7,
    0x25,
    0x7B,
    0x3A,
    0x64,
    0x86,
    0xD8,
    0x5B,
    0x05,
    0xE7,
    0xB9,
    0x8C,
    0xD2,
    0x30,
    0x6E,
    0xED,
    0xB3,
    0x51,
    0x0F,
    0x4E,
    0x10,
    0xF2,
    0xAC,
    0x2F,
    0x71,
    0x93,
    0xCD,
    0x11,
    0x4F,
    0xAD,
    0xF3,
    0x70,
    0x2E,
    0xCC,
    0x92,
    0xD3,
    0x8D,
    0x6F,
    0x31,
    0xB2,
    0xEC,
    0x0E,
    0x50,
    0xAF,
    0xF1,
    0x13,
    0x4D,
    0xCE,
    0x90,
    0x72,
    0x2C,
    0x6D,
    0x33,
    0xD1,
    0x8F,
    0x0C,
    0x52,
    0xB0,
    0xEE,
    0x32,
    0x6C,
    0x8E,
    0xD0,
    0x53,
    0x0D,
    0xEF,
    0xB1,
    0xF0,
    0xAE,
    0x4C,
    0x12,
    0x91,
    0xCF,
    0x2D,
    0x73,
    0xCA,
    0x94,
    0x76,
    0x28,
    0xAB,
    0xF5,
    0x17,
    0x49,
    0x08,
    0x56,
    0xB4,
    0xEA,
    0x69,
    0x37,
    0xD5,
    0x8B,
    0x57,
    0x09,
    0xEB,
    0xB5,
    0x36,
    0x68,
    0x8A,
    0xD4,
    0x95,
    0xCB,
    0x29,
    0x77,
    0xF4,
    0xAA,
    0x48,
    0x16,
    0xE9,
    0xB7,
    0x55,
    0x0B,
    0x88,
    0xD6,
    0x34,
    0x6A,
    0x2B,
    0x75,
    0x97,
    0xC9,
    0x4A,
    0x14,
    0xF6,
    0xA8,
    0x74,
    0x2A,
    0xC8,
    0x96,
    0x15,
    0x4B,
    0xA9,
    0xF7,
    0xB6,
    0xE8,
    0x0A,
    0x54,
    0xD7,
    0x89,
    0x6B,
    0x35,
]


def crc8(data):
    crc_value = 0
    for m in data:
        k = crc_value ^ m
        if k > 256:
            k -= 256
        if k < 0:
            k += 256
        crc_value = crc8_854_table[k]
    return crc_value


_default_app_key: Final = "434a209a5ce141c3b726de067835d7f0"
_default_sign_key: Final = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S"


class Security:
    def __init__(self, app_key: str = None, sign_key: str = None):
        self._app_key_str = (
            app_key if app_key is not None else _default_app_key
        )
        self._sign_key = (
            sign_key if sign_key is not None else _default_sign_key
        ).encode()
        self._block_size = 16
        self._iv = b"\0" * 16
        self._enc_key = md5(self._sign_key).digest()
        self._dynamic_key = md5(self._app_key_str.encode()).digest()[:8]
        self._tcp_key = None
        self._request_count = 0
        self._response_count = 0
        self.access_token = ""

    def aes_decrypt(self, raw):
        try:
            cipher = Cipher(algorithms.AES(self._enc_key), modes.ECB())
            decryptor = cipher.decryptor()
            decrypted = decryptor.update(bytes(raw)) + decryptor.finalize()
            # Remove the padding
            unpadder = padding.PKCS7(self._block_size * 8).unpadder()
            decrypted = (
                unpadder.update(bytes(decrypted)) + unpadder.finalize()
            )
            return decrypted
        except ValueError as e:
            _LOGGER.error(
                "Error during AES decryption: %s - data: %s",
                repr(e),
                hex4log(raw, _LOGGER, logging.ERROR),
            )
            return bytearray(0)

    def aes_encrypt(self, raw):
        # Make sure to pad the data
        padder = padding.PKCS7(self._block_size * 8).padder()
        raw = padder.update(raw) + padder.finalize()
        cipher = Cipher(algorithms.AES(self._enc_key), modes.ECB())
        encryptor = cipher.encryptor()
        encrypted = encryptor.update(bytes(raw)) + encryptor.finalize()

        return encrypted

    def aes_cbc_decrypt(self, raw, key):
        cipher = Cipher(algorithms.AES(key), modes.CBC(self._iv))
        decryptor = cipher.decryptor()
        return decryptor.update(bytes(raw)) + decryptor.finalize()

    def aes_cbc_encrypt(self, raw, key):
        cipher = Cipher(algorithms.AES(key), modes.CBC(self._iv))
        encryptor = cipher.encryptor()
        return encryptor.update(bytes(raw)) + encryptor.finalize()

    def encode32_data(self, raw):
        return md5(raw + self._sign_key).digest()

    def tcp_key(self, response, key):
        if response == b"ERROR":
            _LOGGER.error("Authentication failed")
            return b"", False
        if len(response) != 64:
            _LOGGER.error(
                f"Unexpected data length (expecter 64, was {len(response)})"
            )
            return b"", False
        payload = response[:32]
        sign = response[32:]
        plain = self.aes_cbc_decrypt(payload, key)
        if sha256(plain).digest() != sign:
            _LOGGER.error("sign does not match")
            return b"", False
        self._tcp_key = _strxor(plain, key)
        self._request_count = 0
        self._response_count = 0
        return self._tcp_key, True

    def encode_8370(self, data, msgtype):
        header = bytes([0x83, 0x70])
        size, padding = len(data), 0
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            if (size + 2) % 16 != 0:
                padding = 16 - (size + 2 & 0xF)
                size += padding + 32
                data += urandom(padding)
        header += size.to_bytes(2, "big")
        header += bytes([0x20, padding << 4 | msgtype])
        data = self._request_count.to_bytes(2, "big") + data
        self._request_count += 1
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            if self._tcp_key is None:
                raise Exception("Missing tcp key")
            sign = sha256(header + data).digest()
            data = self.aes_cbc_encrypt(data, self._tcp_key) + sign
        return header + data

    def decode_8370(self, data):
        if len(data) < 6:
            return [], data
        header = data[:6]
        if header[0] != 0x83 or header[1] != 0x70:
            raise Exception("not an 8370 message")
        size = int.from_bytes(header[2:4], "big") + 8
        leftover = None
        if len(data) < size:
            return [], data
        elif len(data) > size:
            leftover = data[size:]
            data = data[:size]
        if header[4] != 0x20:
            raise Exception("Byte 4 was not 0x20")
        padding = header[5] >> 4
        msgtype = header[5] & 0xF
        data = data[6:]
        if msgtype in (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST):
            sign = data[-32:]
            data = data[:-32]
            data = self.aes_cbc_decrypt(data, self._tcp_key)
            if sha256(header + data).digest() != sign:
                raise Exception("Signature does not match payload")
            if padding:
                data = data[:-padding]
        self._response_count = int.from_bytes(data[:2], "big")
        data = data[2:]
        if leftover:
            packets, incomplete = self.decode_8370(leftover)
            return [data] + packets, incomplete
        return [data], b""

    def sign(self, url: str, payload: dict[str, Any]):
        # We only need the path
        path = urlparse(url).path

        # This next part cares about the field ordering in the
        # payload signature
        query = sorted(payload.items(), key=lambda x: x[0])

        # Create a query string (?!?) and make sure to unescape the
        # URL encoded characters (!!!)
        query_str: str = unquote_plus(urlencode(query))

        # Combine all the sign stuff to make one giant string, then SHA256 it
        sign: str = path + query_str + self._app_key_str
        m = sha256()
        m.update(sign.encode("ascii"))

        return m.hexdigest()

    def encrypt_password(self, loginId: str, password: str):
        # Hash the password
        m = sha256()
        m.update(password.encode("ascii"))

        # Create the login hash with the loginID + password hash + appKey,
        # then hash it all AGAIN
        loginHash = loginId + m.hexdigest() + self._app_key_str
        m = sha256()
        m.update(loginHash.encode("ascii"))
        return m.hexdigest()
