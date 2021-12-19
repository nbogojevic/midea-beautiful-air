"""Connects to Midea appliances on local network."""
from __future__ import annotations

from binascii import unhexlify
from datetime import datetime
from hashlib import sha256
import logging
import socket
from threading import Lock
from time import sleep, time
from typing import Final

from midea_beautiful_dehumidifier.appliance import Appliance
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.command import MideaCommand
from midea_beautiful_dehumidifier.crypto import Security
from midea_beautiful_dehumidifier.exceptions import AuthenticationError, ProtocolError
from midea_beautiful_dehumidifier.midea import (
    DISCOVERY_PORT,
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_HANDSHAKE_REQUEST,
)

_LOGGER = logging.getLogger(__name__)


def _hexlog(
    data: bytes,
    level: int = 5,
) -> str:
    """
    Outputs bytes or byte array as hex if logging level 5 is enabled.
    """
    return data.hex() if _LOGGER.isEnabledFor(level) else ""


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
        id: int | str = 0,
        ip: str = None,
        port: int | str = 6444,
        token: str = "",
        key: str = "",
        max_retries: int = 2,
        appliance_type: str = "",
        discovery_data=None,
    ):
        self._security = Security()

        if discovery_data is not None:
            data = bytes(discovery_data)
            if data[:2] == b"ZZ":  # 5a5a
                self.version = 2
            elif data[:2] == b"\x83\x70":  # 8370
                self.version = 3
            else:
                self.version = 0
            if data[8:10] == b"ZZ":  # 5a5a
                data = data[8:-16]
            id = int.from_bytes(data[20:26], "little")
            encrypt_data = data[40:-16]
            reply = self._security.aes_decrypt(encrypt_data)
            self.ip = ".".join([str(i) for i in reply[3::-1]])
            _LOGGER.log(
                5,
                "Decrypted reply from %s len=%d reply=%s",
                self.ip,
                len(reply),
                _hexlog(reply),
            )
            self.port = int.from_bytes(reply[4:8], "little")
            self.sn = reply[8:40].decode("ascii")
            ssid_len = reply[40]
            # ssid like midea_xx_xxxx net_xx_xxxx
            self.ssid = reply[41 : 41 + ssid_len].decode("ascii")
            self.mac = reply[63 + ssid_len : 69 + ssid_len].hex(":")
            if reply[55 + ssid_len] != 0:
                # Get type
                self.type = hex(reply[55 + ssid_len])
                self.subtype = int.from_bytes(
                    reply[57 + ssid_len : 59 + ssid_len], "little"
                )
            else:
                # Get from SSID
                self.type = self.ssid.split("_")[1].lower()
                self.subtype = 0
            self.reserved = reply[43 + ssid_len]
            self.flags = reply[44 + ssid_len]
            self.extra = reply[45 + ssid_len]
            # m_enable_extra = (b >> 7) == 1
            # m_support_extra_auth = (b & 1) == 1
            # m_support_extra_channel = (b & 2) == 2
            # m_support_extra_last_error_code = (b & 4) == 4

            self.randomkey = reply[78 + ssid_len : 94 + ssid_len]
            self.udp_version = int.from_bytes(
                reply[46 + ssid_len : 50 + ssid_len], "little"
            )
            self.protocol_version = reply[69 + ssid_len : 72 + ssid_len].hex()
            self.firmware_version = (
                f"{reply[72 + ssid_len]}."
                f"{reply[73 + ssid_len]}."
                f"{reply[74 + ssid_len]}"
            )
            _LOGGER.debug(
                (
                    "Descriptor data from %s"
                    " type=%s subtype=%x flags=%x extra=%x reserved=%x"
                    " mac=%s ssid=%s udp version=%x protocol=%s version=%s"
                    " enckey=%s sn=%s"
                ),
                self.ip,
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
                self.randomkey,
                self.sn,
            )
        else:
            id = int(id)
            self.ip = ip
            self.port = int(port)
            self.sn = None
            self.subtype = None
            self.reserved = None
            self.flags = None
            self.extra = None
            self.randomkey = None
            self.mac = None
            self.ssid = None
            self.type = appliance_type
            self.firmware_version = None
            self.protocol_version = None
            self.udp_version = None

        # Default interface version is 3
        self.version = 3
        self._retries = 0
        self._socket = None
        self.token = token
        self.key = key
        self._timestamp = time()
        self._tcp_key = None
        self.state = Appliance.instance(id=id, appliance_type=self.type)
        self._max_retries = int(max_retries)
        self._connection_retries = 3
        self._api_lock = Lock()

    def update(self, other: LanDevice):
        self.token = other.token
        self.key = other.key
        self._socket = other._socket
        self._tcp_key = other._tcp_key
        self._socket = other._socket
        self._tcp_key = other._tcp_key
        self._max_retries = other._max_retries
        self._timestamp = other._timestamp
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
        responses = self.status(cmd)
        for response in responses:
            self.state.process_response(response)

    def _connect(self, socket_timeout=2) -> None:
        if self._socket is None:
            self._disconnect()
            _LOGGER.debug("Attempting new connection to %s:%s", self.ip, self.port)
            self._buffer = b""
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # set timeout
            self._socket.settimeout(socket_timeout)
            try:
                self._socket.connect((self.ip, self.port))

            except Exception as error:
                _LOGGER.error(
                    "Connection error: %s:%s %s",
                    self.ip,
                    self.port,
                    error,
                )
                self._disconnect()

    def _disconnect(self) -> None:
        if self._socket:
            self._socket.close()
        self._socket = None
        self._tcp_key = None

    def _socket_info(self, level=logging.DEBUG) -> str:
        if not _LOGGER.isEnabledFor(level):
            return ""
        socket_time = round(time() - self._timestamp, 2)

        return (
            f"local -> {self.ip}:{self.port}"
            f" retries: {self._retries} time: {socket_time}"
        )

    def _request(self, message) -> bytes:
        if self._api_lock.acquire(timeout=10):
            try:
                # Create a TCP/IP socket
                self._connect()
                if self._socket is None:
                    _LOGGER.debug("Socket is None: %s:%s", self.ip, self.port)
                    self._retries += 1
                    return b""

                # Send data
                try:
                    _LOGGER.log(
                        5,
                        "Sending to %s, message: %s",
                        self._socket_info(),
                        _hexlog(message),
                    )
                    self._socket.sendall(message)
                except Exception as error:
                    _LOGGER.error(
                        "Error sending to %s: %s",
                        self._socket_info(logging.ERROR),
                        error,
                    )
                    self._disconnect()
                    self._retries += 1
                    return b""

                # Received data
                try:
                    response = self._socket.recv(1024)
                except socket.timeout as error:
                    _LOGGER.debug(
                        "Receiving from %s, time out error: %s",
                        self._socket_info(),
                        error,
                    )

                    self._retries += 1
                    return b""
                except OSError as error:
                    _LOGGER.debug(
                        "Error receiving from %s: %s",
                        self._socket_info(),
                        error,
                    )
                    self._disconnect()
                    self._retries += 1
                    return b""
                else:
                    _LOGGER.log(
                        5,
                        "Receiving from %s, response: %s",
                        self._socket_info(5),
                        _hexlog(response),
                    )
                    if len(response) == 0:
                        _LOGGER.debug("Socket closed from %s", self._socket_info())
                        self._disconnect()
                        self._retries += 1
                        return b""
                    else:
                        self._retries = 0
                        return response
            finally:
                self._api_lock.release()
        else:
            _LOGGER.warn("Unable to acquire lock for request in 10s for %s", self.id)
            return b""

    def _authenticate(self) -> bool:
        if not self.token or not self.key:
            raise AuthenticationError("missing token/key pair")
        byte_token = unhexlify(self.token)

        response = b""
        for i in range(self._connection_retries):
            request = self._security.encode_8370(byte_token, MSGTYPE_HANDSHAKE_REQUEST)
            response = self._request(request)

            if not response:
                if i > 0:
                    # Retry handshake
                    _LOGGER.info(
                        "Unable to perform handshake, retrying %d of %d",
                        i + 1,
                        self._connection_retries,
                    )
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
            _LOGGER.log(
                5,
                "Got TCP key for %s %s",
                self._socket_info(level=5),
                self._tcp_key,
            )
            # After authentication, don’t send data immediately,
            # so sleep 500ms.
            sleep(0.5)
            return True
        except Exception:
            _LOGGER.warning(
                "Failed to get TCP key for %s",
                self._socket_info(logging.WARN),
            )
            return False

    def status(self, cmd: MideaCommand) -> list[bytes]:
        data = self._lan_packet(int(self.id), cmd)
        _LOGGER.log(
            5,
            "Packet for: %s(%s) data: %s",
            self.id,
            self.ip,
            _hexlog(data),
        )
        responses = self._appliance_send_8370(data)
        _LOGGER.log(5, "Got response(s) from: %s(%s)", self.id, self.ip)

        if len(responses) == 0:
            _LOGGER.warning("Got no responses on status from: %s(%s)", self.id, self.ip)
            self._active = False
            self._support = False
            self._disconnect()
        return responses

    def _appliance_send_8370(self, data) -> list[bytes]:
        if self._socket is None or self._tcp_key is None:
            _LOGGER.debug("Socket %s closed, creating new socket", self._socket_info())
            self._disconnect()

            for i in range(self._connection_retries):
                if not self._authenticate():
                    if i == self._connection_retries - 1:
                        _LOGGER.error(
                            "Failed to authenticate %s",
                            self._socket_info(logging.ERROR),
                        )
                        return []
                    _LOGGER.debug(
                        "Retrying authenticate, %d out of %d: %s",
                        i + 2,
                        self._connection_retries,
                        self._socket_info(),
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
        if not response_buf and self._retries < self._max_retries:
            packets = self._appliance_send_8370(original_data)
            self._retries = 0
            return packets
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

        _LOGGER.log(
            5,
            "Packet for: %s(%s) data: %s",
            self.id,
            self.ip,
            _hexlog(data),
        )
        responses = self._appliance_send_8370(data)
        _LOGGER.debug("Got response(s) from: %s(%s)", self.id, self.ip)

        if len(responses) == 0:
            _LOGGER.warning(
                "Got no responses on apply from: %s(%s)",
                self.id,
                self.ip,
            )
            self._active = False
            self._support = False
            self._disconnect()
        return responses

    def _get_valid_token(self, cloud: MideaCloud) -> bool:
        """
        Retrieves token and authenticates connection to appliance.
        Works only with v3 appliances.

        Args:
            cloud (CloudService): interface to Midea cloud

        Returns:
            bool: True if successful
        """
        for udp_id in [
            _get_udp_id(self.id.to_bytes(6, "little")),
            _get_udp_id(self.id.to_bytes(6, "big")),
        ]:
            self.token, self.key = cloud.get_token(udp_id)
            if self._authenticate():
                _LOGGER.debug("Token valid for %s", udp_id)
                return True
            # token/key were not valid, forget them
            self.token, self.key = "", ""
        return False

    def identify_appliance(self, cloud: MideaCloud = None) -> bool:
        if self.version == 3:
            if not self.token or not self.key:
                if cloud is None:
                    raise ValueError("Provide either token/key pair or cloud")
                if not self._get_valid_token(cloud):
                    return False
            elif not self._authenticate():
                return False
        else:
            raise ProtocolError(
                f"Only version 3 is supported," f" was {self.version} for id={self.id}"
            )

        if Appliance.supported(self.type):
            self.refresh()
            _LOGGER.debug("Appliance data: %s", self.state)
        else:
            _LOGGER.debug("Found unsupported appliance: %s", self)
            return False
        return True

    def set_state(self, **kwargs):
        for attr, value in kwargs:
            if hasattr(self.state, attr):
                setattr(self.state, attr, value)
            else:
                _LOGGER.warn("Unknown state attribute %s", attr)

        return self.apply()

    @property
    def id(self):
        return self.state.id

    @property
    def name(self):
        return self.state.name

    @property
    def model(self):
        return self.state.model

    @name.setter
    def name(self, name):
        self.state.name = name


def get_appliance_state(
    ip: str,
    port: int = DISCOVERY_PORT,
    token: str = "",
    key: str = "",
    socket_timeout: int = 8,
    cloud: MideaCloud = None,
) -> LanDevice | None:
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(socket_timeout)

    try:
        # Connect to the appliance
        sock.connect((ip, port))

        # Send the discovery query
        _LOGGER.log(5, "Sending to %s:%d %s", ip, port, _hexlog(DISCOVERY_MSG))
        sock.sendall(DISCOVERY_MSG)

        # Received data
        response = sock.recv(512)
        _LOGGER.log(5, "Received from %s:%d %s", ip, port, _hexlog(response))
        appliance = LanDevice(discovery_data=response, token=token, key=key)
        _LOGGER.log(5, "Appliance from %s:%d is %s", ip, port, appliance)
        if appliance.identify_appliance(cloud):
            if cloud is not None:
                for details in cloud.list_appliances():
                    if details["id"] == appliance.id:
                        appliance.name = details["name"]
                        break
            return appliance
    except socket.error:
        _LOGGER.warn("Could not connect with appliance %s:%d", ip, port)
    except socket.timeout:
        _LOGGER.warn(
            "Timeout while connecting to appliance %s:%d for %ds.",
            ip,
            port,
            socket_timeout,
        )
    finally:
        sock.close()

    return None
