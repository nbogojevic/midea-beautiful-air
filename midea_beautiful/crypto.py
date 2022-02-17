"""Cryptographic tools."""
from __future__ import annotations

from binascii import hexlify, unhexlify
import collections
from hashlib import md5, sha256
import hmac
import logging
from os import urandom
from typing import Any, Final, Tuple
from urllib.parse import unquote_plus, urlencode, urlparse

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from midea_beautiful.exceptions import AuthenticationError, MideaError, ProtocolError
from midea_beautiful.midea import (
    DEFAULT_APPKEY,
    DEFAULT_HMACKEY,
    DEFAULT_IOTKEY,
    DEFAULT_SIGNKEY,
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_ENCRYPTED_RESPONSE,
)
from midea_beautiful.util import HDR_8370

_LOGGER = logging.getLogger(__name__)

ENCRYPTED_MESSAGE_TYPES: Final = (MSGTYPE_ENCRYPTED_RESPONSE, MSGTYPE_ENCRYPTED_REQUEST)


def _strxor(plain_text: bytes, key: bytes) -> bytes:
    """returns encrypted plain text by repeatedly xoring it with key"""
    len_key = len(key)
    encoded = bytearray(len(plain_text))

    for i, k in enumerate(plain_text):
        encoded[i] = k ^ key[i % len_key]
    return bytes(encoded)


crc8_854_table: Final = [
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


def crc8(data: bytes) -> int:
    """8-bit CRC calculation"""
    crc_value: int = 0
    for byt in data:
        crc_value = crc8_854_table[crc_value ^ byt]
    return crc_value


_BLOCKSIZE: Final = 16


class Security:
    """Various security and cryptography services for Midea protocol"""

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        appkey: str = DEFAULT_APPKEY,
        signkey: str = DEFAULT_SIGNKEY,
        iotkey: str = DEFAULT_IOTKEY,
        hmackey: str = DEFAULT_HMACKEY,
        iv: bytes = b"\x00" * _BLOCKSIZE,
    ) -> None:
        self._appkey = appkey
        self._signkey = signkey.encode()
        self._iotkey = iotkey
        self._hmackey = hmackey
        self._iv = bytes(iv)
        self._enc_key = md5(self._signkey).digest()  # nosec Midea use MD5 hashing
        self._tcp_key = b""
        self._request_count = 0
        self._response_count = 0
        self._access_token = None
        self._data_key = None

    def aes_decrypt(self, raw: bytes) -> bytes:
        """
        Decrypt raw bytes using AES/ECB

        Args:
            raw (bytes): array of bytes or bytearray to decrypted

        Returns:
            bytes: decrypted data
        """
        # Midea uses ECB mode for some exchanges
        cipher = Cipher(algorithms.AES(self._enc_key), modes.ECB())  # nosec
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(raw) + decryptor.finalize()
        # Remove the padding
        unpadder = padding.PKCS7(_BLOCKSIZE * 8).unpadder()
        return unpadder.update(decrypted) + unpadder.finalize()

    def aes_encrypt(self, raw: bytes) -> bytes:
        """
        Encrypt raw bytes using AES/ECB

        Args:
            raw (bytes): array of bytes or bytearray to encrypt

        Returns:
            bytes: encrypted array of bytes
        """
        # Pad data to 128 bit
        padder = padding.PKCS7(_BLOCKSIZE * 8).padder()
        raw = padder.update(raw) + padder.finalize()
        # Midea uses ECB mode for some exchanges
        cipher = Cipher(algorithms.AES(self._enc_key), modes.ECB())  # nosec
        encryptor = cipher.encryptor()
        return encryptor.update(raw) + encryptor.finalize()

    def aes_cbc_decrypt(self, raw: bytes, key: bytes) -> bytes:
        """
        Decrypt raw bytes using AES/CBC

        Args:
            raw (bytes): array of bytes or bytearray to decrypted

        Returns:
            bytes: decrypted data
        """
        cipher = Cipher(algorithms.AES(key), modes.CBC(self._iv))
        decryptor = cipher.decryptor()
        return decryptor.update(raw) + decryptor.finalize()

    def aes_cbc_encrypt(self, raw: bytes, key: bytes) -> bytes:
        """
        Encrypt raw bytes using AES/CBC

        Args:
            raw (bytes): array of bytes or bytearray to encrypt

        Returns:
            bytes: encrypted array of bytes
        """
        cipher = Cipher(algorithms.AES(key), modes.CBC(self._iv))
        encryptor = cipher.encryptor()
        return encryptor.update(raw) + encryptor.finalize()

    def md5fingerprint(self, raw: bytes) -> bytes:
        """Generates Midea md5 fingerprint of the raw payload"""
        return md5(raw + self._signkey).digest()  # nosec Midea use MD5 hashing

    def tcp_key(self, response: bytes, key: bytes) -> bytes:
        """Retrieves key for local network communication"""
        if response == b"ERROR":
            raise AuthenticationError("Authentication failed - error packet")
        if len(response) != 64:
            raise AuthenticationError(
                f"Packet length error: {len(response)} instead of 64)"
            )
        payload = response[:32]
        sign = response[32:]
        plain = self.aes_cbc_decrypt(payload, key)
        if sha256(plain).digest() != sign:
            raise AuthenticationError("Packet signature mismatch")
        self._tcp_key = _strxor(plain, key)
        self._request_count = 0
        self._response_count = 0
        return self._tcp_key

    def encode_8370(self, data: bytes, msgtype: int) -> bytes:
        """Encodes message in v3 (8370) protocol"""
        header = bytearray(HDR_8370)
        size, pad = len(data), 0
        if msgtype in ENCRYPTED_MESSAGE_TYPES:
            if (size + 2) % 16 != 0:
                pad = 16 - (size + 2 & 0b1111)
                size += pad + 32
                data += urandom(pad)
        header.extend(size.to_bytes(2, "big"))
        header.extend([0x20, pad << 4 | msgtype])
        if self._request_count >= 0xFFF:
            self._request_count = 0
        data = self._request_count.to_bytes(2, "big") + data
        self._request_count += 1
        if msgtype in ENCRYPTED_MESSAGE_TYPES:
            if not self._tcp_key:
                raise ProtocolError("Missing TCP key for local network access")
            sign = sha256(header + data).digest()
            data = self.aes_cbc_encrypt(data, self._tcp_key) + sign
        return bytes(header + data)

    def decode_8370(self, data: bytes) -> Tuple[list[bytes], bytes]:
        """Decodes buffer in v3 (8370) protocol"""
        if len(data) < 6:
            return [], data
        header = data[:6]
        if header[0] != 0x83 or header[1] != 0x70:
            raise ProtocolError("Message was not a v3 (8370) message")
        size = int.from_bytes(header[2:4], "big") + 8
        leftover = None
        # If there is not enough data in buffer, we need to wait for more data
        if len(data) < size:
            return [], data
        if len(data) > size:
            # If there is too much data, save the overflow
            leftover = data[size:]
            data = data[:size]
        if header[4] != 0x20:
            raise ProtocolError("Byte 4 was not 0x20")
        pad = header[5] >> 4
        msgtype = header[5] & 0xF
        data = data[6:]

        if msgtype in ENCRYPTED_MESSAGE_TYPES:
            # Decrypt encrypted messages using TCP key
            sign = data[-32:]
            data = data[:-32]
            data = self.aes_cbc_decrypt(data, self._tcp_key)
            if sha256(header + data).digest() != sign:
                raise ProtocolError("Signature does not match payload")
            if pad:
                data = data[:-pad]
        self._response_count = int.from_bytes(data[:2], "big")
        data = data[2:]
        # If we have remaining data, process it
        if leftover:
            packets, incomplete = self.decode_8370(leftover)
            return [data] + packets, incomplete
        return [data], b""

    def sign(self, url: str, payload: dict[str, Any]) -> str:
        """Signs payload for cloud API"""
        # We only need the path
        path = urlparse(url).path

        # Make sure that keys are in alphabetical order
        query = sorted(payload.items(), key=lambda x: x[0])

        # Create a query string and make sure to unescape the
        # URL encoded characters
        query_str: str = unquote_plus(urlencode(query))

        # Combine all the signing elements, then SHA256 it
        sign: str = path + query_str + self._appkey
        sha = sha256()
        sha.update(sign.encode("ascii"))

        return sha.hexdigest()

    def encrypt_password(self, login_id: str, password: str) -> str:
        """Encrypts password for cloud API"""
        # Hash the password
        sha = sha256()
        sha.update(password.encode("ascii"))

        # Create the login hash with the loginID + password hash + appKey,
        # then hash it all again
        login_hash = login_id + sha.hexdigest() + self._appkey
        sha = sha256()
        sha.update(login_hash.encode("ascii"))
        return sha.hexdigest()

    def encrypt_iam_password(self, login_id: str, password: str) -> str:
        """Encrypts password for cloud API"""
        # Hash the password
        md = md5()
        md.update(password.encode("ascii"))
        md_second = md5()
        md_second.update(md.hexdigest().encode("ascii"))
        # Create the login hash with the loginID + password hash + appKey,
        # then hash it all again
        login_hash = login_id + md_second.hexdigest() + self._appkey
        sha = sha256()
        sha.update(login_hash.encode("ascii"))

        return sha.hexdigest()

    def sign_proxied(self, query: dict[str, Any], data: str, random: str) -> str:
        msg = self._iotkey
        if data:
            msg += data

        if query:
            query = collections.OrderedDict(sorted(query.items()))
            for k, v in query.items():
                print(k)
                print(v)
                msg += k
                msg += v
        msg += random

        sign = hmac.new(self._hmackey.encode("ascii"), msg.encode("ascii"), sha256)
        return sign.hexdigest()

    @property
    def access_token(self) -> str | None:
        """Returns current access token"""
        return self._access_token

    @access_token.setter
    def access_token(self, token: str) -> None:
        self._access_token = token
        key = self.md5appkey
        self._data_key = self.aes_decrypt_string(self._access_token, key)

    def set_access_token(self, token: str, key: str) -> None:
        self._access_token = token
        key = self.md5appkey
        self._data_key = self.aes_decrypt_string_no_pad(self._access_token, key)

    @property
    def md5appkey(self) -> str:
        """Special generated key from appkey"""
        # Midea use MD5 hashing
        return md5(self._appkey.encode("utf-8")).hexdigest()[:16]  # nosec

    @property
    def data_key(self) -> str | None:
        """Returns current data encryption key"""
        return self._data_key

    def aes_decrypt_string(self, data: str, key: str | None = None) -> str:
        """
        Decrypt string data using key or data_key if key omitted
        """
        key = key or self._data_key
        if key is None:
            raise MideaError("Missing data key")
        encrypted_data = unhexlify(data)

        # Midea uses ECB mode for some exchanges
        cipher = Cipher(algorithms.AES(key.encode("utf-8")), modes.ECB())  # nosec
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
        unpadder = padding.PKCS7(_BLOCKSIZE * 8).unpadder()
        result = unpadder.update(decrypted) + unpadder.finalize()
        return result.decode("utf-8")

    def aes_decrypt_string_no_pad(self, data: str, key: str | None = None) -> str:
        """
        Decrypt string data using key or data_key if key omitted
        """
        key = key or self._data_key
        if key is None:
            raise MideaError("Missing data key")
        encrypted_data = unhexlify(data)

        # Midea uses ECB mode for some exchanges
        cipher = Cipher(algorithms.AES(key.encode("ascii")), modes.ECB())  # nosec
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(encrypted_data) + decryptor.finalize()
        # spell-checker: ignore hexlify
        return hexlify(decrypted)

    def aes_encrypt_string(self, data: str, key: str | None = None) -> str:
        """
        Encrypt string data using key or data_key if key omitted
        """
        key = key or self._data_key
        if key is None:
            raise MideaError("Missing data key")

        raw = data.encode("utf-8")

        padder = padding.PKCS7(_BLOCKSIZE * 8).padder()
        raw = padder.update(raw) + padder.finalize()

        # Midea uses ECB mode here
        cipher = Cipher(algorithms.AES(key.encode("utf-8")), modes.ECB())  # nosec
        encryptor = cipher.encryptor()
        result = encryptor.update(raw) + encryptor.finalize()

        return result.hex()
