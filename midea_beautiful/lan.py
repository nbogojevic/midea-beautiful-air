"""Connects to Midea appliances on local network."""
from __future__ import annotations

import binascii
from datetime import datetime
from hashlib import sha256
import logging
import socket
from threading import RLock
from time import sleep
from typing import Any, Final

from midea_beautiful.appliance import Appliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.command import (
    DeviceCapabilitiesCommand,
    DeviceCapabilitiesCommandMore,
    MideaCommand,
)
from midea_beautiful.crypto import Security
from midea_beautiful.exceptions import (
    AuthenticationError,
    MideaError,
    MideaNetworkError,
    ProtocolError,
    UnsupportedError,
)
from midea_beautiful.midea import (
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_RETRIES,
    DISCOVERY_PORT,
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_HANDSHAKE_REQUEST,
)
from midea_beautiful.util import HDR_8370, HDR_ZZ, Redacted, is_very_verbose

# pylint: disable=too-many-arguments
# pylint: disable=duplicate-code

_LOGGER = logging.getLogger(__name__)

_STATE_SOCKET_TIMEOUT: Final = 2

_MAX_RETRIES: Final = 3


def matches_lan_cloud(device: LanDevice, cloud_details: dict[str, Any]):
    """Checks if lan device and cloud details correspond to same appliance"""
    return (
        cloud_details["id"] == device.appliance_id
        or cloud_details["sn"] == device.serial_number
    )


def _is_token_version(version: int):
    return version >= 3


def _is_no_token_version(version: int):
    return version == 2


# pylint: disable=duplicate-code


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
    digest = sha256(data).digest()
    first, second = digest[:16], digest[16:]
    result = bytearray(16)
    for i in range(16):
        result[i] = first[i] ^ second[i]
    return result.hex()


class LanDevice:
    """Represents a Midea device"""

    # pylint: disable=too-many-instance-attributes

    # Default sleep unit of time. By default 1 second.
    _DEFAULT_SLEEP_INTERVAL: Final = 1
    # Unit of time for sleep.
    # Can be set to different value during tests.
    sleep_interval: float = _DEFAULT_SLEEP_INTERVAL

    def __init__(
        self,
        appliance_id: str = "",
        address: str = None,
        port: int | str = 6444,
        token: str = None,
        key: str = "",
        appliance_type: str = "",
        data: bytes = None,
        serial_number: str = None,
        security: Security = None,
        version: int = 3,
    ) -> None:
        self._security = security or Security()
        self._retries = 0
        self._socket = None
        self.socket_timeout: float = _STATE_SOCKET_TIMEOUT
        self.token = token
        self.key = key
        self._got_tcp_key = False
        self.last_error = ""
        self.max_retries = _MAX_RETRIES
        self._no_responses = 0
        self._lock = RLock()
        self.firmware_version = None
        self.protocol_version = None
        self.udp_version = 0
        self.randomkey = None
        self.reserved = 0
        self.flags = 0
        self.extra = 0
        self.subtype = 0
        self._buffer = b""
        self.address = address
        self.serial_number = serial_number
        self.mac = None
        self.ssid = None
        self.version = version

        if data:
            self._init_from_data(data)

        else:
            self.address = address
            self.port = int(port)

            self.type = appliance_type

            self.state = Appliance.instance(
                appliance_id=appliance_id, appliance_type=self.type
            )
            self._online = False

    def update(self, other: LanDevice) -> None:
        """Updates this LanDevice with data from another one"""
        self.token = other.token
        self.key = other.key
        self._socket = None
        self._got_tcp_key = False
        self.max_retries = other.max_retries
        self._retries = other._retries  # pylint: disable=protected-access
        self.address = other.address
        self.port = other.port
        self.firmware_version = other.firmware_version
        self.protocol_version = other.protocol_version
        self.udp_version = other.protocol_version
        self.serial_number = other.serial_number
        self.mac = other.mac
        self.ssid = other.ssid

    def _init_from_data(self, data: bytes):
        data = bytes(data)
        if data[:2] == HDR_ZZ:
            self.version = 2
        elif data[:2] == HDR_8370:
            self.version = 3
        else:
            self.version = 0
            return

        if data[8:10] == HDR_ZZ:
            data = data[8:-16]
        appliance_id = str(int.from_bytes(data[20:26], "little"))
        reply = self._security.aes_decrypt(data[40:-16])
        self.address = ".".join([str(i) for i in reply[3::-1]])
        _LOGGER.debug(
            "From %s decrypted reply=%s", Redacted(self.address, 5), Redacted(reply)
        )
        self.port = int.from_bytes(reply[4:8], "little")
        self.serial_number = reply[8:40].decode("ascii")
        ssid_len = reply[40]
        # ssid like midea_xx_xxxx net_xx_xxxx
        self.ssid = reply[41 : 41 + ssid_len].decode("ascii")

        self._extract_mac(reply, ssid_len)
        self._extract_type(reply, ssid_len)
        self._init_extra_data(reply, ssid_len)

        self.state = Appliance.instance(appliance_id, self.type)
        self._online = True

        _LOGGER.debug("Descriptor data %r", self.redacted())

    def _extract_mac(self, reply, ssid_len):
        if len(reply) >= (69 + ssid_len):
            self.mac = reply[63 + ssid_len : 69 + ssid_len].hex()
        else:
            assert self.serial_number
            self.mac = self.serial_number[16:32]

    def _extract_type(self, reply, ssid_len):
        if len(reply) >= (56 + ssid_len) and reply[55 + ssid_len] != 0:
            # Get type
            self.type = hex(reply[55 + ssid_len])
            if len(reply) >= (59 + ssid_len):
                self.subtype = int.from_bytes(
                    reply[57 + ssid_len : 59 + ssid_len], "little"
                )
        else:
            # Get from SSID
            assert self.ssid
            self.type = self.ssid.split("_")[1].lower()
            self.subtype = 0

    def _init_extra_data(self, reply: bytes, ssid_len: int):
        if len(reply) >= (46 + ssid_len):
            self.reserved = reply[43 + ssid_len]
            self.flags = reply[44 + ssid_len]
            self.extra = reply[45 + ssid_len]
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
                if len(reply) >= (94 + ssid_len):
                    self.randomkey = reply[78 + ssid_len : 94 + ssid_len]

    def _lan_packet(self, command: MideaCommand, local_packet: bool = True) -> bytes:
        id_bytes = int(self.appliance_id).to_bytes(8, "little")
        now: datetime = datetime.now()
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
                int(now.microsecond / 10000),
                now.second,
                now.minute,
                now.hour,
                now.day,
                now.month,
                now.year % 100,
                int(now.year / 100),
                # 8 bytes - Device ID
                id_bytes[0],
                id_bytes[1],
                id_bytes[2],
                id_bytes[3],
                id_bytes[4],
                id_bytes[5],
                id_bytes[6],
                id_bytes[7],
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

        # Append the encrypted command data to the packet
        if local_packet:
            encrypted = self._security.aes_encrypt(command.finalize())
            packet.extend(encrypted)
        else:
            packet.extend(command.finalize())
        # Set packet length
        packet[4:6] = (len(packet) + 16).to_bytes(2, "little")
        # Append a checksum to the packet
        packet.extend(self._security.md5fingerprint(packet))
        return bytes(packet)

    def refresh(self, cloud: MideaCloud = None) -> None:
        """Refreshes appliance data from network or cloud"""
        with self._lock:

            cmd = self.state.refresh_command()
            responses = self._status(cmd, cloud)
            if responses:
                self._no_responses = 0
                if len(responses) > 1:
                    _LOGGER.debug(
                        "Got several responses on refresh from: %s, got=%d",
                        self,
                        len(responses),
                    )
                self._online = True
                _LOGGER.debug("refresh %s responses=%s", self, responses)
                self.state.process_response(responses[-1])

    def _check_for_offline(self, cloud):
        if self._no_responses > self.max_retries:
            if self._online:
                _LOGGER.debug(
                    "No response for %s in %d retries. Considered offline",
                    self,
                    self._no_responses,
                )
            self._online = False
            if not cloud:
                self._disconnect()

    def _connect(self) -> None:
        with self._lock:
            if not self._socket:
                self._disconnect()
                _LOGGER.debug("Attempting new connection to %s", self)
                self._buffer = b""
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # set timeout
                self._socket.settimeout(self.socket_timeout)
                try:
                    self._socket.connect((self.address, self.port))
                except Exception as error:  # pylint: disable=broad-except
                    _LOGGER.debug(
                        "Connection error: %s for %s", self, error, exc_info=True
                    )
                    self.last_error = error
                    self._disconnect()

    def _disconnect(self) -> None:
        with self._lock:
            if self._socket:
                self._socket.close()
            self._socket = None
            self._got_tcp_key = False

    def _sleep(self, duration: float) -> None:
        sleep(duration * self.sleep_interval)

    def _request(self, message) -> bytes:
        with self._lock:
            # Create a TCP/IP socket
            self._connect()
            if not self._socket:
                _LOGGER.debug("Socket not open for %s", self)
                self.last_error = f"Socket not open for {self.address}"
                self._retries += 1
                return b""

            # Send data
            try:
                _LOGGER.debug("Sending to %s, message=%s", self, Redacted(message))
                self._socket.sendall(message)
            except Exception as error:  # pylint: disable=broad-except
                _LOGGER.debug("Error sending to %s: %s", self, error)
                self.last_error = str(error)
                self._disconnect()
                self._retries += 1
                return b""

            # Receive data
            try:
                response = self._socket.recv(1024)
            except socket.timeout as error:
                _LOGGER.debug("Timeout receiving from %s: %s", self, error)
                self.last_error = str(error)
                self._retries += 1
                return b""
            except OSError as error:
                _LOGGER.debug("Error receiving from %s: %s", self, error)
                self.last_error = str(error)
                self._disconnect()
                self._retries += 1
                return b""
            else:
                _LOGGER.debug("From %s, message=%s", self, Redacted(response))
                if len(response) == 0:
                    self.last_error = f"No results from {self.address}"
                    self._disconnect()
                    self._retries += 1
                    return b""
                self._retries = 0
                return response

    def _authenticate(self):
        if not self.token or not self.key:
            raise AuthenticationError("Missing token/key pair")
        try:
            byte_token = binascii.unhexlify(self.token)
        except binascii.Error as ex:
            raise AuthenticationError(f"Invalid token {ex}") from ex
        if is_very_verbose():
            _LOGGER.debug(
                "token='%s' key='%s' for %s",
                Redacted(self.token, -2),
                Redacted(self.key, -2),
                self,
            )
        response = b""
        for i in range(self.max_retries):
            request = self._security.encode_8370(byte_token, MSGTYPE_HANDSHAKE_REQUEST)
            response = self._request(request)
            if not response:
                if i > 0:
                    # Retry handshake
                    _LOGGER.debug("Handshake retry %d of %d", i + 1, self.max_retries)
                    self._sleep(i + 1)
            else:
                break
        else:
            raise AuthenticationError(
                f"Failed to perform handshake for {self.serial_number}"
            )

        if is_very_verbose():
            _LOGGER.debug("handshake_response=%s for %s", response, self)
        response = response[8:72]

        self._get_tcp_key(response)

    def _get_tcp_key(self, response: bytes):
        try:
            tcp_key = self._security.tcp_key(response, binascii.unhexlify(self.key))
            if is_very_verbose():
                _LOGGER.debug("tcp_key=%s for %s", Redacted(tcp_key.hex(), -2), self)

            self._got_tcp_key = True
            _LOGGER.debug("Got TCP key for: %s", self)
            # After authentication, don’t send data immediately,
            # so sleep 500ms.
            self._sleep(0.5 * self.sleep_interval)

        except Exception as ex:
            raise AuthenticationError(
                f"Failed to get TCP key for {Redacted(self.serial_number, 8)},"
                f" cause {ex}"
            ) from ex

    def _status(self, cmd: MideaCommand, cloud: MideaCloud | None) -> list[bytes]:
        data = self._lan_packet(cmd, cloud is None)
        _LOGGER.debug("Packet for: %s data=%s", self, data)
        if cloud:
            _LOGGER.debug("Sending request via cloud API to: %s", self)
            responses = cloud.appliance_transparent_send(self.appliance_id, data)
        else:
            responses = self.appliance_send(data)

        if len(responses) == 0:
            _LOGGER.debug("Got no responses on status from: %s", self)
            self._no_responses += 1
            self._check_for_offline(cloud)
        else:
            self._no_responses = 0
            self._online = True
            _LOGGER.debug("Got %d response(s) from: %s", len(responses), self)

        return responses

    def _appliance_send_8370(self, data: bytes) -> list[bytes]:
        """Sends data using v3 (8370) protocol"""
        if is_very_verbose():
            _LOGGER.debug("appliance_send_8370 %s data=%s", self, data)

        if not self._socket or not self._got_tcp_key:
            _LOGGER.debug("Socket %s closed, creating new socket", self)
            self._disconnect()

            for i in range(self.max_retries):
                try:
                    self._authenticate()
                    break
                except MideaError as ex:
                    if i == self.max_retries - 1:
                        _LOGGER.debug("Failed to authenticate %s", self)
                        raise ex
                    _LOGGER.debug(
                        "Retrying authenticate, %d out of %d: %s",
                        i + 2,
                        self.max_retries,
                        self,
                    )
                    self._disconnect()

                    self._sleep((i + 1) * 2)

        # copy from data in order to resend data
        original_data = bytes(data)
        data = self._security.encode_8370(data, MSGTYPE_ENCRYPTED_REQUEST)
        if is_very_verbose():
            _LOGGER.debug("encode_8370 %s data=%s", self, data)

        # wait few seconds before re-sending data, default is 0
        self._sleep(self._retries)
        response_buf = self._request(data)

        if packets := self._retry_send(original_data, response_buf):
            return packets

        responses, self._buffer = self._security.decode_8370(
            self._buffer + response_buf
        )
        if is_very_verbose():
            _LOGGER.debug(
                "decode_8370 responses=%s overflow=%s for %s",
                responses,
                self._buffer,
                self,
            )
        for response in responses:
            if len(response) > 40 + 16:
                response = self._security.aes_decrypt(response[40:-16])
            # header length is 10 bytes
            if len(response) > 10:
                packets.append(response[10:])
        return packets

    def _appliance_send_v2(self, data: bytes) -> list[bytes]:
        # wait few seconds before re-sending data, default is 0
        self._sleep(self._retries)
        if is_very_verbose():
            _LOGGER.debug("appliance_send_v2 %s data=%s", self, data)
        response_buf = self._request(data)
        if packets := self._retry_send(data, response_buf):
            return packets
        response_len = len(response_buf)
        if response_buf[:2] == HDR_ZZ and response_len > 5:
            self._zz_packets(response_buf, packets)
        elif response_buf[0] == 0xAA and response_len > 2:
            self._b5_packets(response_buf, packets)
        else:
            raise ProtocolError(f"Unknown response format {self} {response_buf}")
        return packets

    def _zz_packets(self, response_buf: bytes, packets: list[bytes]) -> None:
        # ZZ response
        response_len = len(response_buf)
        i = 0
        # maybe multiple response
        while i < response_len:
            size = response_buf[i + 4]
            data = self._security.aes_decrypt(response_buf[i : i + size][40:-16])
            # header length is 10 bytes
            if len(data) > 10:
                packets.append(data[10:])
            i += size

    def _b5_packets(self, response_buf: bytes, packets: list[bytes]) -> None:
        # B5 response
        response_len = len(response_buf)
        i = 0
        while i < response_len:
            size = response_buf[i + 1]
            data = response_buf[i : i + size + 1]
            # header length is 10 bytes
            if len(data) > 10:
                packets.append(data[10:])
            i += size + 1

    def _retry_send(self, data: bytes, response_buf: bytes) -> list[bytes]:
        if not response_buf:
            if self._retries < self.max_retries:
                if is_very_verbose():
                    _LOGGER.debug(
                        "retrying appliance_send_lan %d of %d",
                        self._retries,
                        self.max_retries,
                    )
                self.last_error = "empty reply"
                self._retries += 1
                packets = self.appliance_send(data)
                self._retries = 0
                return packets
            error = self.last_error
            self.last_error = ""
            raise MideaNetworkError(
                f"Unable to send data after {self.max_retries} retries,"
                f" last error {error} for {Redacted(self.serial_number, 8)}"
                f" ({Redacted(self.appliance_id, 4)})"
            )
        return []

    def appliance_send(self, data: bytes) -> list[bytes]:
        """Sends data packet to the appliance"""
        if _is_token_version(self.version):
            return self._appliance_send_8370(data)
        if _is_no_token_version(self.version):
            return self._appliance_send_v2(data)
        raise ProtocolError(f"Unsupported protocol {self.version}")

    def apply(self, cloud: MideaCloud = None) -> None:
        """Applies changes to device. I.e. sends command to update data."""
        with self._lock:
            cmd = self.state.apply_command()

            data = self._lan_packet(cmd, cloud is None)

            _LOGGER.debug("Packet for %s data: %s", self, data)
            if use_cloud := cloud is not None:
                _LOGGER.debug("Sending request via cloud to %s", self)
                responses = cloud.appliance_transparent_send(self.appliance_id, data)
            else:
                responses = self.appliance_send(data)
            _LOGGER.debug("Got response(s) from: %s", self)

            if responses:
                if len(responses) > 1:
                    _LOGGER.debug(
                        "Got several responses on apply from: %s, %d",
                        self,
                        len(responses),
                    )
                self._online = True
                self.state.process_response(responses[-1])
            else:
                _LOGGER.debug("Got no responses on apply from: %s", self)
                self._online = False
                if not use_cloud:
                    self._disconnect()

    def _get_valid_token(self, cloud: MideaCloud) -> bool:
        """Retrieves token and authenticates connection to appliance.
        Works only with v3 appliances.

        Args:
            cloud (CloudService): interface to Midea cloud API

        Returns:
            bool: True if successful
        """
        for udp_id in [
            _get_udp_id(int(self.appliance_id).to_bytes(6, "little")),
            _get_udp_id(int(self.appliance_id).to_bytes(6, "big")),
        ]:
            self.token, self.key = cloud.get_token(udp_id)
            try:
                self._authenticate()
                _LOGGER.debug("Token valid for %s udp_id=%s", self, udp_id)
                return True
            except MideaError as ex:
                _LOGGER.debug(
                    "Token check failed for udp_id=%s, %s", udp_id, ex, exc_info=True
                )
                # token/key were not valid, forget them
                self.token, self.key = "", ""

        return False

    def is_identified(self, cloud: MideaCloud = None) -> bool:
        """Returns True if this appliance can be identified"""
        try:
            self.identify(cloud)
            return True
        except MideaError as ex:
            _LOGGER.debug("Error identifying appliance %s", ex)
            return False

    def valid_token(self, cloud: MideaCloud | None):
        if not self.token or not self.key:
            if not cloud:
                raise MideaError(f"Provide either token/key pair or cloud {self!r}")
            if not self._get_valid_token(cloud):
                raise AuthenticationError(
                    f"Unable to get valid token for {self.serial_number}"
                )
        else:
            self._authenticate()

    def _check_is_supported(self, use_cloud: bool):
        if not self.is_supported_version and not use_cloud:
            raise UnsupportedError(
                f"Appliance {self.serial_number} protocol is not supported."
            )

        if not Appliance.supported(self.type):
            raise UnsupportedError(f"Unsupported appliance: {self!r}")

    def identify(self, cloud: MideaCloud = None, use_cloud: bool = False) -> None:
        """Identifies appliance data on network and/or from cloud"""

        self._check_is_supported(use_cloud)

        if _is_token_version(self.version) and not use_cloud:
            self.valid_token(cloud)

        cmd = DeviceCapabilitiesCommand()
        responses = self._status(cmd, cloud if use_cloud else None)
        if len(responses) == 0:
            _LOGGER.debug("No response on device capabilities request")
        else:
            if is_very_verbose():
                _LOGGER.debug("device capabilities %s response=%s", self, responses[-1])
            self.state.process_response_device_capabilities(responses[-1], 0)
        cmd = DeviceCapabilitiesCommandMore()
        responses = self._status(cmd, cloud if use_cloud else None)
        if len(responses) == 0:
            _LOGGER.debug("No response on device capabilities request (more)")
        else:
            if is_very_verbose():
                _LOGGER.debug(
                    "device capabilities (more) %s response=%s", self, responses[-1]
                )
            self.state.process_response_device_capabilities(responses[-1], 1)

        self.refresh(cloud if use_cloud else None)
        _LOGGER.debug("Identified appliance: %s", self.redacted())

    def set_state(self, **kwargs) -> None:
        """Sets state attributes of the appliance. Attribute cloud has special meaning
        and is used to pass MideaCloud object.
        """
        cloud = None
        for attr, value in kwargs.items():
            if attr == "cloud":
                cloud = value
            elif hasattr(self.state, attr):
                if value is not None:
                    setattr(self.state, attr, value)
            else:
                _LOGGER.warning("Unknown state attribute %s for %s", attr, self)

        self.apply(cloud)

    def __str__(self) -> str:
        return (
            f"sn={Redacted(self.serial_number, 8)}"
            f" id={Redacted(self.appliance_id, 4)}"
            f" address={Redacted(self.address, 5)}"
            f" version={self.version}"
        )

    def redacted(self) -> str:
        return (
            "{id=%s, address=%s, port=%d, version=%d, name=%s, online=%s,"
            " type=%s, subtype=%x, flags=%x, extra=%x, reserved=%x,"
            " mac=%s, ssid=%s, udp_version=%x, protocol=%s, version=%s,"
            " sn=%s, state=%s}"
        ) % (
            Redacted(self.appliance_id, 4),
            Redacted(self.address, 5),
            self.port,
            self.version,
            Redacted(self.name, length=0),
            self.online,
            self.type,
            self.subtype,
            self.flags,
            self.extra,
            self.reserved,
            Redacted(self.mac, 5),
            self.ssid,
            self.udp_version,
            self.protocol_version,
            self.firmware_version,
            Redacted(self.serial_number, 8),
            self.state,
        )

    def __repr__(self) -> str:
        return (
            "{id=%s, address=%s, port=%d, version=%d, name=%s, online=%s,"
            " type=%s, subtype=%x, flags=%x, extra=%x, reserved=%x,"
            " mac=%s, ssid=%s, udp_version=%x, protocol=%s, version=%s,"
            " sn=%s, state=%s}"
        ) % (
            self.appliance_id,
            self.address,
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
            self.serial_number,
            self.state,
        )

    @property
    def short_sn(self):
        if (
            self.serial_number
            and len(self.serial_number) == 32
            and self.serial_number[:6] == "000000"
        ):
            return self.serial_number[6:-4]

    @property
    def appliance_id(self) -> str:
        """Returns appliance id (from Midea app)"""
        return self.state.appliance_id

    @property
    def name(self) -> str:
        """Returns appliance name"""
        return self.state.name

    @property
    def model(self) -> str:
        """Returns appliance model"""
        return self.state.model

    @name.setter
    def name(self, name: str) -> None:
        """Set the name of the appliance"""
        self.state.name = name

    @property
    def is_supported_version(self) -> bool:
        """Returns True if appliance is supported"""
        return self.version >= 2

    @property
    def online(self) -> bool:
        """Returns True if appliance is online and responds to requests"""
        return self._online


def appliance_state(
    address: str | None = None,
    token: str = None,
    key: str = None,
    cloud: MideaCloud = None,
    use_cloud: bool = False,
    appliance_id: str | None = None,
    appliance_type: str = APPLIANCE_TYPE_DEHUMIDIFIER,
    security: Security = None,
    retries: int = DEFAULT_RETRIES,
    timeout: float = _STATE_SOCKET_TIMEOUT,
    cloud_timeout: float = None,
) -> LanDevice:
    """Gets the current state of an appliance

    Args:
        address (str, optional): IPv4 address of the appliance. Defaults to None.
        token (str, optional): Token used for appliance. Defaults to None.
        key (str, optional): Key used for appliance. Defaults to None.
        cloud (MideaCloud, optional): An instance of cloud client. Defaults to None.
        use_cloud (bool, optional): True if state should be retrieved from cloud.
        Defaults to False.
        appliance_id (str, optional): Id of the appliance as stored in Midea API.
        Defaults to None.
        appliance_type (str, optional): Type of the appliance.
        Defaults to APPLIANCE_TYPE_DEHUMIDIFIER.
        security (Security, optional): Security object. If None, a new one is allocated.
        Defaults to None.
        retries (int): Number of times library should retry retrieving data.
        timeout (float): Time to wait for device reply.
        cloud_timeout (float): Time to wait for cloud API reply. If omitted,
        same as timeout.

    Raises:
        MideaNetworkError: [description]
        MideaError: [description]

    Returns:
        LanDevice: [description]
    """
    # Create a TCP/IP socket
    if address:
        token = token or ""
        key = key or ""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        port = DISCOVERY_PORT

        try:
            # Connect to the appliance
            sock.connect((address, port))

            # Send the discovery query
            _LOGGER.debug(
                "Sending to %s:%d %s", Redacted(address, 5), port, DISCOVERY_MSG
            )
            sock.sendall(DISCOVERY_MSG)

            # Received data
            response = sock.recv(512)
            _LOGGER.debug(
                "Received from %s:%d %s", Redacted(address, 5), port, response
            )
            appliance = LanDevice(
                data=response, token=token, key=key, security=security
            )
            appliance.max_retries = retries
            appliance.socket_timeout = timeout
            _LOGGER.debug("Appliance %s", appliance)
        except socket.timeout as ex:
            raise MideaNetworkError(
                f"Timeout while connecting to appliance {address}:{port}"
            ) from ex
        except socket.error as ex:
            raise MideaNetworkError(
                f"Could not connect to appliance {address}:{port}"
            ) from ex
        finally:
            sock.close()
    elif appliance_id is not None:
        if use_cloud and cloud:
            appliance = LanDevice(
                appliance_id=appliance_id,
                appliance_type=appliance_type,
                security=security,
            )
        else:
            raise MideaError("Missing cloud credentials")
    else:
        raise MideaError("Must provide either appliance id or network address")

    if cloud:
        cloud.max_retries = retries
        cloud.request_timeout = cloud_timeout or timeout
    appliance.identify(cloud, use_cloud)
    if cloud:
        for details in cloud.list_appliances():
            if matches_lan_cloud(appliance, details):
                appliance.name = details["name"]
                appliance.serial_number = appliance.serial_number or details["sn"]
                break
    return appliance
