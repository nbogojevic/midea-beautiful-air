"""Connects to Midea appliances on local network."""
from __future__ import annotations

from binascii import unhexlify
import binascii
from datetime import datetime
from hashlib import sha256
import logging
import socket
from threading import RLock
from time import sleep
from typing import Final

from midea_beautiful_dehumidifier.appliance import Appliance
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.command import MideaCommand
from midea_beautiful_dehumidifier.crypto import Security
from midea_beautiful_dehumidifier.exceptions import (
    AuthenticationError,
    MideaError,
    MideaNetworkError,
    UnsupportedError,
)
from midea_beautiful_dehumidifier.midea import (
    DISCOVERY_PORT,
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_HANDSHAKE_REQUEST,
)
from midea_beautiful_dehumidifier.util import _Hex


_LOGGER = logging.getLogger(__name__)

_STATE_SOCKET_TIMEOUT: Final = 3

_SUPPORTED_VERSION: Final = 3

DISCOVERY_MSG: Final = bytes(
    [
        0x5A,
        0x5A,
        0x01,
        0x11,
        0x48,
        0x00,
        0x92,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x7F,
        0x75,
        0xBD,
        0x6B,
        0x3E,
        0x4F,
        0x8B,
        0x76,
        0x2E,
        0x84,
        0x9C,
        0x6E,
        0x57,
        0x8D,
        0x65,
        0x90,
        0x03,
        0x6E,
        0x9D,
        0x43,
        0x42,
        0xA5,
        0x0F,
        0x1F,
        0x56,
        0x9E,
        0xB8,
        0xEC,
        0x91,
        0x8E,
        0x92,
        0xE5,
    ]
)


def _get_udp_id(data) -> str:
    b = sha256(data).digest()
    b1, b2 = b[:16], b[16:]
    b3 = bytearray(16)
    for i in range(16):
        b3[i] = b1[i] ^ b2[i]
    return b3.hex()


class LanDevice:
    def __init__(
        self,
        id: str = "",
        ip: str = None,
        port: int | str = 6444,
        token: str = "",
        key: str = "",
        appliance_type: str = "",
        data=None,
    ):
        self._security = Security()
        self._retries = 0
        self._socket = None
        self.token = token
        self.key = key
        self._tcp_key = None
        self._last_error = ""
        self._max_retries = 3
        self._no_responses = 0
        self._lock = RLock()
        self.firmware_version = None
        self.protocol_version = None
        self.udp_version = None
        self.randomkey = None
        self.reserved = None
        self.flags = None
        self.extra = None
        self.subtype = None

        if data:
            data = bytes(data)
            if data[:2] == b"\x5a\x5a":  # 5a5a
                self.version = 2
            elif data[:2] == b"\x83\x70":  # 8370
                self.version = 3
            else:
                self.version = 0
            if data[8:10] == b"\x5a\x5a":  # 5a5a
                data = data[8:-16]
            id = str(int.from_bytes(data[20:26], "little"))
            encrypt_data = data[40:-16]
            reply = self._security.aes_decrypt(encrypt_data)
            self.ip = ".".join([str(i) for i in reply[3::-1]])
            _LOGGER.log(5, "From %s decrypted reply=%s", self.ip, _Hex(reply))
            self.port = int.from_bytes(reply[4:8], "little")
            self.sn = reply[8:40].decode("ascii")
            ssid_len = reply[40]
            # ssid like midea_xx_xxxx net_xx_xxxx
            self.ssid = reply[41 : 41 + ssid_len].decode("ascii")
            if len(reply) >= (69 + ssid_len):
                self.mac = reply[63 + ssid_len : 69 + ssid_len].hex(":")
            else:
                self.mac = self.sn[16:32]
            if len(reply) >= (56 + ssid_len) and reply[55 + ssid_len] != 0:
                # Get type
                self.type = hex(reply[55 + ssid_len])
                if len(reply) >= (59 + ssid_len):
                    self.subtype = int.from_bytes(
                        reply[57 + ssid_len : 59 + ssid_len], "little"
                    )
            else:
                # Get from SSID
                self.type = self.ssid.split("_")[1].lower()
                self.subtype = 0
            if len(reply) >= (46 + ssid_len):
                self.reserved = reply[43 + ssid_len]
                self.flags = reply[44 + ssid_len]
                self.extra = reply[45 + ssid_len]

            # m_enable_extra = (b >> 7) == 1
            # m_support_extra_auth = (b & 1) == 1
            # m_support_extra_channel = (b & 2) == 2
            # m_support_extra_last_error_code = (b & 4) == 4

            if len(reply) >= (94 + ssid_len):
                self.randomkey = reply[78 + ssid_len : 94 + ssid_len]
            if len(reply) >= (50 + ssid_len):
                self.udp_version = int.from_bytes(
                    reply[46 + ssid_len : 50 + ssid_len], "little"
                )
            if len(reply) >= (72 + ssid_len):
                self.protocol_version = reply[69 + ssid_len : 72 + ssid_len].hex()
            if len(reply) >= (75 + ssid_len):
                self.firmware_version = (
                    f"{reply[72 + ssid_len]}."
                    f"{reply[73 + ssid_len]}."
                    f"{reply[74 + ssid_len]}"
                )
            self.state = Appliance.instance(id=id, appliance_type=self.type)
            self._online = True

            _LOGGER.debug("Descriptor data from %s: %r", self, self)

        else:
            id = id
            self.ip = ip
            self.port = int(port)
            self.sn = None
            self.mac = None
            self.ssid = None
            self.type = appliance_type

            self.state = Appliance.instance(id=id, appliance_type=self.type)
            self._online = True
            # Default interface version is 3
            self.version = 3

    def update(self, other: LanDevice):
        self.token = other.token
        self.key = other.key
        self._socket = None
        self._tcp_key = other._tcp_key
        self._max_retries = other._max_retries
        self._retries = other._retries
        self.ip = other.ip
        self.port = other.port
        self.firmware_version = other.firmware_version
        self.protocol_version = other.protocol_version
        self.udp_version = other.protocol_version
        self.sn = other.sn
        self.mac = other.mac
        self.ssid = other.ssid

    def _lan_packet(self, id: int, command: MideaCommand) -> bytes:
        # Init the packet with the header data.
        packet = bytearray(
            [
                # 2 bytes - Static Header
                0x5A,
                0x5A,
                # 2 bytes - Message Type
                0x01,
                0x11,
                # 2 bytes - Packet Length
                0x00,
                0x00,
                # 2 bytes
                0x20,
                0x00,
                # 4 bytes - MessageId
                0x00,
                0x00,
                0x00,
                0x00,
                # 8 bytes - Date&Time
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                # 6 bytes - Device ID
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                # 12 bytes
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )
        t = datetime.now().strftime("%Y%m%d%H%M%S%f")[:16]
        packet_time = bytearray()
        for i in range(0, len(t), 2):
            packet_time.insert(0, int(t[i : i + 2]))
        packet[12:20] = packet_time
        packet[20:28] = id.to_bytes(8, "little")

        # Append the encrypted command data to the packet

        encrypted = self._security.aes_encrypt(command.finalize())
        packet.extend(encrypted)
        # Set packet length
        packet[4:6] = (len(packet) + 16).to_bytes(2, "little")
        # Append a checksum to the packet
        packet.extend(self._security.md5fingerprint(packet))
        return bytes(packet)

    def refresh(self) -> None:
        cmd = self.state.refresh_command()
        responses = self._status(cmd)
        if not responses:
            self._no_responses += 1
            if self._no_responses > self._max_retries:
                self._online = False
        else:
            self._no_responses = 0
            self._online = True
            for response in responses:
                self.state.process_response(response)

    def _connect(self, socket_timeout=2) -> None:
        with self._lock:
            if not self._socket:
                self._disconnect()
                _LOGGER.debug("Attempting new connection to %s", self)
                self._buffer = b""
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # set timeout
                self._socket.settimeout(socket_timeout)
                try:
                    self._socket.connect((self.ip, self.port))

                except Exception as error:
                    _LOGGER.error(
                        "Connection error: %s for %s", self, error, exc_info=True
                    )
                    self._disconnect()

    def _disconnect(self) -> None:
        with self._lock:
            if self._socket:
                self._socket.close()
            self._socket = None
            self._tcp_key = None

    def _request(self, message) -> bytes:
        with self._lock:
            # Create a TCP/IP socket
            self._connect()
            if not self._socket:
                _LOGGER.debug("Socket not open for %s", self)
                self._retries += 1
                return b""

            # Send data
            try:
                _LOGGER.log(5, "Sending to %s, message: %s", self, _Hex(message))
                self._socket.sendall(message)
            except Exception as error:
                _LOGGER.debug("Error sending to %s: %s", self, error)
                self._last_error = str(error)
                self._disconnect()
                self._retries += 1
                return b""

            # Received data
            try:
                response = self._socket.recv(1024)
            except socket.timeout as error:
                _LOGGER.debug("Timeout receiving from %s: %s", self, error)
                self._retries += 1
                return b""
            except OSError as error:
                _LOGGER.debug("Error receiving from %s: %s", self, error)
                self._disconnect()
                self._retries += 1
                return b""
            else:
                _LOGGER.log(5, "From %s, got response: %s", self, _Hex(response))
                if len(response) == 0:
                    _LOGGER.debug("Socket closed %s", self)
                    self._disconnect()
                    self._retries += 1
                    return b""
                else:
                    self._retries = 0
                    return response

    def _authenticate(self) -> bool:
        if not self.token or not self.key:
            raise AuthenticationError("missing token/key pair")
        try:
            byte_token = unhexlify(self.token)
        except binascii.Error as ex:
            raise AuthenticationError(f"Invalid token {ex}")

        response = b""
        for i in range(self._max_retries):
            request = self._security.encode_8370(byte_token, MSGTYPE_HANDSHAKE_REQUEST)
            response = self._request(request)

            if not response:
                if i > 0:
                    # Retry handshake
                    _LOGGER.debug("Handshake retry %d of %d", i + 1, self._max_retries)
                    sleep(i + 1)
            else:
                break
        else:
            _LOGGER.error("Failed to perform handshake")
            return False

        response = response[8:72]

        try:
            tcp_key = self._security.tcp_key(response, unhexlify(self.key))

            self._tcp_key = tcp_key.hex()
            _LOGGER.log(5, "Got TCP key for %s", self)
            # After authentication, don’t send data immediately,
            # so sleep 500ms.
            sleep(0.5)
            return True
        except Exception:
            _LOGGER.warning("Failed to get TCP key for %s", self)
            return False

    def _status(self, cmd: MideaCommand) -> list[bytes]:
        data = self._lan_packet(int(self.id), cmd)
        _LOGGER.log(5, "Packet for: %s data: %s", self, _Hex(data))
        responses = self._appliance_send_8370(data)

        if len(responses) == 0:
            _LOGGER.debug("Got no responses on status from: %s", self)
            self._no_responses += 1
            if self._no_responses > self._max_retries:
                self._online = False
            self._disconnect()
        else:
            self._no_responses = 0
            self._online = True
            _LOGGER.log(5, "Got response(s) from: %s", self)

        return responses

    def _appliance_send_8370(self, data: bytes | bytearray) -> list[bytes]:
        """Sends data using v3 (8370) protocol"""
        if not self._socket or not self._tcp_key:
            _LOGGER.debug("Socket %s closed, creating new socket", self)
            self._disconnect()

            for i in range(self._max_retries):
                if not self._authenticate():
                    if i == self._max_retries - 1:
                        _LOGGER.debug("Failed to authenticate %s", self)
                        raise AuthenticationError(f"Failed to authenticate {self}")
                    _LOGGER.debug(
                        "Retrying authenticate, %d out of %d: %s",
                        i + 2,
                        self._max_retries,
                        self,
                    )
                    self._disconnect()

                    sleep((i + 1) * 2)
                else:
                    break

        packets = []

        # copy from data in order to resend data
        original_data = bytes(data)
        data = self._security.encode_8370(data, MSGTYPE_ENCRYPTED_REQUEST)

        # wait few seconds before re-sending data, default is 0
        sleep(self._retries)
        response_buf = self._request(data)
        if not response_buf:
            if self._retries < self._max_retries:
                packets = self._appliance_send_8370(original_data)
                self._retries = 0
                return packets
            else:
                _LOGGER.error(
                    "Unable to send data after %d retries, last error %s",
                    self._max_retries,
                    self._last_error,
                )
                self._last_error = ""
        responses, self._buffer = self._security.decode_8370(
            self._buffer + response_buf
        )
        for response in responses:
            if len(response) > 40 + 16:
                response = self._security.aes_decrypt(response[40:-16])
            # header length is 10 bytes
            if len(response) > 10:
                packets.append(response[10:])
        return packets

    def apply(self) -> None:
        cmd = self.state.apply_command()

        responses = self._apply(cmd)
        for response in responses:
            self.state.process_response(response)

    def _apply(self, cmd: MideaCommand) -> list[bytes]:
        data = self._lan_packet(int(self.id), cmd)

        _LOGGER.log(5, "Packet for %s data: %s", self, _Hex(data))
        responses = self._appliance_send_8370(data)
        _LOGGER.debug("Got response(s) from: %s", self)

        if len(responses) == 0:
            _LOGGER.debug("Got no responses on apply from: %s", self)
            self._online = False
            self._disconnect()
        else:
            self._online = True
        return responses

    def _get_valid_token(self, cloud: MideaCloud) -> bool:
        """
        Retrieves token and authenticates connection to appliance.
        Works only with v3 appliances.

        Args:
            cloud (CloudService): interface to Midea cloud API

        Returns:
            bool: True if successful
        """
        for udp_id in [
            _get_udp_id(int(self.id).to_bytes(6, "little")),
            _get_udp_id(int(self.id).to_bytes(6, "big")),
        ]:
            self.token, self.key = cloud.get_token(udp_id)
            if self._authenticate():
                _LOGGER.debug("Token valid for %s", udp_id)
                return True
            # token/key were not valid, forget them
            self.token, self.key = "", ""
        return False

    def is_identified(self, cloud: MideaCloud = None) -> bool:
        try:
            self.identify(cloud)
            return True
        except MideaError as ex:
            _LOGGER.debug("Error identifying appliance %s", ex)
            return False

    def identify(self, cloud: MideaCloud = None):
        if self.version == _SUPPORTED_VERSION:
            if not self.token or not self.key:
                if not cloud:
                    raise MideaError(f"Provide either token/key pair or cloud {self!r}")
                if not self._get_valid_token(cloud):
                    raise AuthenticationError(f"Unable to get valid token for {self}")
            elif not self._authenticate():
                raise AuthenticationError(
                    f"Unable to authenticate with appliance {self}"
                )
        else:
            raise UnsupportedError(
                f"Appliance {self} is not supported:"
                f" needs to support protocol version {_SUPPORTED_VERSION}"
            )

        if not Appliance.supported(self.type):
            raise UnsupportedError(f"Unsupported appliance: {self!r}")

        self.refresh()
        _LOGGER.debug("Appliance data: %r", self)

    def set_state(self, **kwargs):
        for attr, value in kwargs.items():
            if hasattr(self.state, attr):
                if value is not None:
                    setattr(self.state, attr, value)
            else:
                _LOGGER.warning("Unknown state attribute %s", attr)

        return self.apply()

    def __str__(self):
        return f"id={self.id} ip={self.ip}:{self.port} version={self.version}"

    def __repr__(self) -> str:
        return (
            "{id=%s, ip=%s, port=%d, version=%d, name=%s, online=%s,"
            " type=%s, subtype=%x, flags=%x, extra=%x, reserved=%x,"
            " mac=%s, ssid=%s, udp_version=%x, protocol=%s, version=%s,"
            " sn=%s, state=%s}"
        ) % (
            self.id,
            self.ip,
            self.port,
            self.version,
            self.name,
            self.online,
            self.type,
            self.subtype,
            self.flags,
            self.extra,
            self.reserved,
            self.mac,
            self.ssid,
            self.udp_version,
            self.protocol_version,
            self.firmware_version,
            self.sn,
            self.state,
        )

    @property
    def id(self):
        return self.state.id

    @property
    def name(self) -> str:
        return self.state.name

    @property
    def model(self):
        return self.state.model

    @name.setter
    def name(self, name):
        self.state.name = name

    @property
    def is_supported(self):
        return self.version == 3

    @property
    def online(self):
        return self._online


def get_appliance_state(
    ip: str,
    port: int = DISCOVERY_PORT,
    token: str = None,
    key: str = None,
    cloud: MideaCloud = None,
) -> LanDevice:
    # Create a TCP/IP socket
    token = token or ""
    key = key or ""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(_STATE_SOCKET_TIMEOUT)

    try:
        # Connect to the appliance
        sock.connect((ip, port))

        # Send the discovery query
        _LOGGER.log(5, "Sending to %s:%d %s", ip, port, _Hex(DISCOVERY_MSG))
        sock.sendall(DISCOVERY_MSG)

        # Received data
        response = sock.recv(512)
        _LOGGER.log(5, "Received from %s:%d %s", ip, port, _Hex(response))
        appliance = LanDevice(data=response, token=token, key=key)
        _LOGGER.log(5, "Appliance %s", appliance)
        appliance.identify(cloud)
        if cloud:
            for details in cloud.list_appliances():
                if details["id"] == appliance.id:
                    appliance.name = details["name"]
                    break
        return appliance
    except socket.error:
        raise MideaNetworkError("Could not connect to appliance %s:%d")
    except socket.timeout:
        raise MideaNetworkError("Timeout while connecting to appliance %s:%d")
    finally:
        sock.close()
