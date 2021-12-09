"""Connects to Midea appliances on local network."""
from __future__ import annotations

import binascii
import datetime
import logging
import socket
import time
from hashlib import sha256
from typing import Final

from midea_beautiful_dehumidifier.cloud import CloudService
from midea_beautiful_dehumidifier.crypto import Security
from midea_beautiful_dehumidifier.appliance import DehumidifierAppliance
from midea_beautiful_dehumidifier.midea import (
    MSGTYPE_ENCRYPTED_REQUEST,
    MSGTYPE_HANDSHAKE_REQUEST,
    MideaCommand,
)
from midea_beautiful_dehumidifier.util import hex4log

_LOGGER = logging.getLogger(__name__)


BROADCAST_MSG: Final = bytearray(
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


class LanPacketBuilder:
    def __init__(self, id: int | str):
        self.command = None
        self.security = Security()
        # aa20ac00000000000003418100ff03ff000200000000000000000000000006f274
        # Init the packet with the header data.
        self.packet = bytearray(
            [
                # 2 bytes - StaicHeader
                0x5A,
                0x5A,
                # 2 bytes - mMessageType
                0x01,
                0x11,
                # 2 bytes - PacketLenght
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
                # 6 bytes - mDeviceID
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
        self.packet[12:20] = _packet_time()
        self.packet[20:28] = int(id).to_bytes(8, "little")

    def set_command(self, command: MideaCommand):
        self.command = command.finalize()

    def finalize(self):
        # Append the command data(48 bytes) to the packet

        encrypted = self.security.aes_encrypt(self.command)

        self.packet.extend(encrypted)
        # PacketLength
        self.packet[4:6] = (len(self.packet) + 16).to_bytes(2, "little")
        # Append a basic checksum data(16 bytes) to the packet
        self.packet.extend(self.security.encode32_data(self.packet))
        return self.packet


def _packet_time() -> bytearray:
    t = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:16]
    b = bytearray()
    for i in range(0, len(t), 2):
        d = int(t[i : i + 2])
        b.insert(0, d)
    return b


def _to_hex(value: str | bytes | None):
    return binascii.hexlify(value) if isinstance(value, bytes) else value


def _get_udpid(data):
    b = sha256(data).digest()
    b1, b2 = b[:16], b[16:]
    b3 = bytearray(16)
    i = 0
    while i < len(b1):
        b3[i] = b1[i] ^ b2[i]
        i += 1
    return b3.hex()


class LanDevice:
    def __init__(
        self,
        id: int | str = 0,
        ip: str = None,
        port: int | str = 6444,
        token: str | bytes = None,
        key: str | bytes = None,
        max_retries: int = 2,
        discovery_data=None,
    ):
        self._security = Security()

        if discovery_data is not None:
            data = bytearray(discovery_data)
            if data[:2] == b"ZZ":  # 5a5a
                self.version = 2
            elif data[:2] == b"\x83p":  # 8370
                self.version = 3
            else:
                self.version = 0
            if data[8:10] == b"ZZ":  # 5a5a
                data = data[8:-16]
            self.id = int.from_bytes(data[20:26], "little")
            encrypt_data = data[40:-16]
            reply = self._security.aes_decrypt(encrypt_data)
            self.ip = ".".join([str(i) for i in reply[3::-1]])
            _LOGGER.debug(
                "Decrypted reply from %s reply=%s",
                self.ip,
                hex4log(reply, _LOGGER),
            )
            self.port = int.from_bytes(reply[4:8], "little")
            # ssid like midea_xx_xxxx net_xx_xxxx
            self.ssid = reply[41 : 41 + reply[40]].decode("utf-8")
            self.mac = reply[24:36].decode("ascii")
            self.type = self.ssid.split("_")[1].lower()
        else:
            self.id = int(id)
            self.ip = ip
            self.port = int(port)

        self._retries = 0
        self._socket = None
        self.token = _to_hex(token)
        self.key = _to_hex(key)
        self._timestamp = time.time()
        self._tcp_key = None
        self._local = None
        self.state = DehumidifierAppliance(id)
        self._max_retries = int(max_retries)
        self._connection_retries = 3

    def refresh(self):
        if self.state is None:
            raise ValueError("Midea appliance descriptor is None")
        cmd = self.state.refresh_command()
        responses = self.status(cmd, id=self.state.id)
        for response in responses:
            self.state.process_response(response)

    def _connect(self):
        if self._socket is None:
            self._disconnect()
            _LOGGER.debug(
                "Attempting new connection to %s:%s", self.ip, self.port
            )
            self._buffer = b""
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # set timeout
            self._socket.settimeout(2)
            try:
                self._socket.connect((self.ip, self.port))
                self._timestamp = time.time()
                self._local = ":".join(
                    "%s" % i for i in self._socket.getsockname()
                )
            except Exception as error:
                _LOGGER.error(
                    "Connection error: %s:%s %s", self.ip, self.port, error
                )
                self._disconnect()

    def _disconnect(self):
        if self._socket:
            self._socket.close()
            self._socket = None
            self._tcp_key = None

    def _socket_info(self, level=logging.DEBUG):
        if not _LOGGER.isEnabledFor(level):
            return ""
        socket_time = round(time.time() - self._timestamp, 2)
        return (
            f"{self._local} -> {self.ip}:{self.port}"
            f" retries: {self._retries} time: {socket_time}"
        )

    def _request(self, message):
        # Create a TCP/IP socket
        self._connect()
        if self._socket is None:
            _LOGGER.debug("Socket is None: %s:%s", self.ip, self.port)
            return bytearray(0), False

        # Send data
        try:
            _LOGGER.debug(
                "Sending %s message: %s",
                self._socket_info(),
                hex4log(message, _LOGGER),
            )
            self._socket.sendall(message)
        except Exception as error:
            _LOGGER.error("Send %s Error: %s", self._socket_info(), error)
            self._disconnect()
            self._retries += 1
            return bytearray(0), True

        # Received data
        try:
            response = self._socket.recv(1024)
        except socket.timeout as error:
            if error.args[0] == "timed out":
                _LOGGER.debug("Recv %s, timed out", self._socket_info())
                self._retries += 1
                return bytearray(0), True
            else:
                _LOGGER.debug(
                    "Recv %s time out error: %s", self._socket_info(), error
                )
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
        except socket.error as error:
            _LOGGER.debug("Recv %s error: %s", self._socket_info(), error)
            self._disconnect()
            self._retries += 1
            return bytearray(0), True
        else:
            _LOGGER.debug(
                "Recv %s response: %s",
                self._socket_info(),
                hex4log(response, _LOGGER),
            )
            if len(response) == 0:
                _LOGGER.debug(
                    "Recv %s server closed socket", self._socket_info()
                )
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
            else:
                self._retries = 0
                return response, True

    def _authenticate(self) -> bool:
        if not self.token or not self.key:
            raise Exception("missing token key pair")
        byte_token = binascii.unhexlify(self.token)

        response, success = None, False
        for i in range(self._connection_retries):
            request = self._security.encode_8370(
                byte_token, MSGTYPE_HANDSHAKE_REQUEST
            )
            response, success = self._request(request)

            if not success:
                if i > 0:
                    # Retry handshake
                    _LOGGER.info(
                        "Unable to perform handshake, retrying %d of 3",
                        i + 1,
                        self._connection_retries,
                    )
                    time.sleep(i + 1)
            else:
                break

        if not success or response is None:
            _LOGGER.error("Failed to perform handshake")
            return False
        response = response[8:72]

        tcp_key, success = self._security.tcp_key(
            response, binascii.unhexlify(self.key)
        )
        if success:
            self._tcp_key = tcp_key.hex()
            # _LOGGER.debug("Got TCP key for %s %s",
            #               self._socket_info(level=logging.DEBUG),
            #               self._tcp_key)
            # After authentication, don’t send data immediately,
            # so sleep 1s.
            time.sleep(1)
        else:
            _LOGGER.warning(
                "Failed to get TCP key for %s",
                self._socket_info(level=logging.INFO),
            )
        return success

    def status(
        self, cmd: MideaCommand, id: str | int = None
    ) -> list[bytearray]:
        pkt_builder = LanPacketBuilder(int(self.id))
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        # _LOGGER.debug("Packet for: %s(%s) data: %s", self.id, self.ip,
        #               hex4log(data, _LOGGER))
        responses = self._appliance_send_8370(data)
        # _LOGGER.debug("Got response(s) from: %s(%s)",
        #               self.id, self.ip)

        if len(responses) == 0:
            _LOGGER.warning("Got Null from: %s(%s)", self.id, self.ip)
            self._active = False
            self._support = False
        return responses

    def _appliance_send_8370(self, data) -> list[bytearray]:
        if self._socket is None or self._tcp_key is None:
            _LOGGER.debug(
                "Socket %s closed, Creating new socket", self._socket_info()
            )
            self._disconnect()

            for i in range(self._connection_retries):
                if not self._authenticate():
                    if i == self._connection_retries - 1:
                        _LOGGER.error(
                            "Failed to authenticate %s",
                            self._socket_info(logging.WARNING),
                        )
                        return []
                    _LOGGER.info(
                        "Retrying authenticate, %d out of %d: %s",
                        i + 2,
                        self._connection_retries,
                        self._socket_info(),
                    )
                    self._disconnect()

                    time.sleep((i + 1) * 2)
                else:
                    break

        if self._tcp_key is None:
            return []

        packets = []

        # copy from data in order to resend data
        original_data = bytearray.copy(data)
        data = self._security.encode_8370(data, MSGTYPE_ENCRYPTED_REQUEST)

        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self._request(data)
        if (
            responses == bytearray(0)
            and self._retries < self._max_retries
            and b
        ):
            packets = self._appliance_send_8370(original_data)
            self._retries = 0
            return packets
        responses, self._buffer = self._security.decode_8370(
            self._buffer + responses
        )
        for response in responses:
            if len(response) > 40 + 16:
                response = self._security.aes_decrypt(response[40:-16])
            # header lenght is 10
            if len(response) > 10:
                packets.append(response[10:])
        return packets

    def apply(self):
        if self.state is None:
            raise ValueError("Midea appliance descriptor is None")
        cmd = self.state.apply_command()

        responses = self._apply(cmd)
        for response in responses:
            self.state.process_response(response)

    def _apply(self, cmd: MideaCommand) -> list[bytearray]:
        pkt_builder = LanPacketBuilder(int(self.id))
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        _LOGGER.debug(
            "Packet for: %s(%s) data: %s",
            self.id,
            self.ip,
            hex4log(data, _LOGGER),
        )
        responses = self._appliance_send_8370(data)
        _LOGGER.debug("Got response(s) from: %s(%s)", self.id, self.ip)

        if len(responses) == 0:
            _LOGGER.warning("Got Null from: %s(%s)", self.id, self.ip)
            self._active = False
            self._support = False
        return responses

    def _get_token_and_authenticate_v3(self, cloud_service: CloudService):
        for udpid in [
            _get_udpid(self.id.to_bytes(6, "little")),
            _get_udpid(self.id.to_bytes(6, "big")),
        ]:
            token, key = cloud_service.get_token(udpid)
            self.token = _to_hex(token)
            self.key = _to_hex(key)
            auth = self._authenticate()
            if auth:
                return True
            self.token = None
            self.key = None
        return False

    def identify_appliance(self, cloud_service: CloudService = None) -> bool:
        if self.version == 3:
            if self.token is None or self.key is None:
                if cloud_service is None:
                    raise ValueError(
                        "Provide either token, key or cloud_service"
                    )
                if not self._get_token_and_authenticate_v3(cloud_service):
                    return False
            if not self._authenticate():
                return False

        if self.type.lower() == "a1" or self.type.lower() == "0xa1":
            self.state = DehumidifierAppliance(self.id)
            self.refresh()
            _LOGGER.debug("Device data: %s", self.state)
        else:
            _LOGGER.debug("Found unsupported appliance: %s", self)
            return False
        return True

    def set_state(
        self,
        target_humidity=None,
        fan_speed=None,
        mode=None,
        ion=None,
        is_on=None,
    ):
        if target_humidity is not None:
            self.state.target_humidity = int(target_humidity)
        if fan_speed is not None:
            self.state.fan_speed = int(fan_speed)
        if mode is not None:
            self.state.mode = int(mode)
        if ion is not None:
            self.state.ion_mode = int(ion) != 0
        if is_on is not None:
            self.state.is_on = int(is_on) != 0
        return self.apply()


def get_appliance_state(
    ip, port, token=None, key=None, socket_timeout=8
) -> LanDevice | None:
    # Create a TCP/IP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(socket_timeout)

    try:
        # Connect to appliance
        appliance_address = (ip, port)
        sock.connect(appliance_address)

        # Send data
        _LOGGER.debug("Sending to %s:%d %s", ip, port, BROADCAST_MSG.hex())
        sock.sendall(BROADCAST_MSG)

        # Received data
        response = sock.recv(512)
        _LOGGER.debug("Received from %s:%d %s", ip, port, response.hex())
        appliance = LanDevice(discovery_data=response, token=token, key=key)
        _LOGGER.debug("Appliance from %s:%d is %s", ip, port, appliance)
        if appliance.identify_appliance():
            return appliance
    except socket.error:
        _LOGGER.info("Couldn't connect with appliance %s:%d", ip, port)
    except socket.timeout:
        _LOGGER.info(
            "Timeout while connecting the appliance %s:%d for %ds.",
            ip,
            port,
            socket_timeout,
        )
    finally:
        sock.close()

    return None
