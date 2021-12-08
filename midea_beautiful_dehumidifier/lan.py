"""Connects to Midea devices on local network."""
from __future__ import annotations

import binascii
import logging
import socket
import time

from midea_beautiful_dehumidifier.crypto import Security
from midea_beautiful_dehumidifier.util import (MSGTYPE_ENCRYPTED_REQUEST,
                                               MSGTYPE_HANDSHAKE_REQUEST,
                                               hex4logging,
                                               MideaCommand, MideaService,
                                               packet_time)

_LOGGER = logging.getLogger(__name__)


class LanPacketBuilder:

    def __init__(self, id: int | str):
        self.command = None
        self.security = Security()
        # aa20ac00000000000003418100ff03ff000200000000000000000000000006f274
        # Init the packet with the header data.
        self.packet = bytearray([
            # 2 bytes - StaicHeader
            0x5a, 0x5a,
            # 2 bytes - mMessageType
            0x01, 0x11,
            # 2 bytes - PacketLenght
            0x00, 0x00,
            # 2 bytes
            0x20, 0x00,
            # 4 bytes - MessageId
            0x00, 0x00, 0x00, 0x00,
            # 8 bytes - Date&Time
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # 6 bytes - mDeviceID
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # 12 bytes
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        self.packet[12:20] = packet_time()
        self.packet[20:28] = int(id).to_bytes(8, 'little')

    def set_command(self, command: MideaCommand):
        self.command = command.finalize()

    def finalize(self):
        # Append the command data(48 bytes) to the packet
        self.packet.extend(self.security.aes_encrypt(self.command)[:48])
        # PacketLength
        self.packet[4:6] = (len(self.packet) + 16).to_bytes(2, 'little')
        # Append a basic checksum data(16 bytes) to the packet
        self.packet.extend(self.security.encode32_data(self.packet))
        return self.packet

        
def _to_hex(value: str | bytes | None):
    return binascii.hexlify(value) if isinstance(value, bytes) else value

class Lan(MideaService):
    def __init__(self, id: int | str,
                 ip: str, port: int | str = 6444,
                 token: str | bytes = None, key: str | bytes = None,
                 max_retries: int = 2):
        self.id = int(id)
        self.ip = ip
        self.port = int(port)
        self._security = Security()
        self._retries = 0
        self._socket = None
        self._token = _to_hex(token)
        self._key = _to_hex(key)
        self._timestamp = time.time()
        self._tcp_key = None
        self._local = None
        self._connection_retries = 3

        self._max_retries = int(max_retries)

    def target(self) -> str:
        return f"{self.ip}:{self.port}"

    def _connect(self):
        if self._socket is None:
            self._disconnect()
            _LOGGER.debug("Attempting new connection to %s:%s",
                          self.ip, self.port)
            self._buffer = b''
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # set timeout
            self._socket.settimeout(2)
            try:
                self._socket.connect((self.ip, self.port))
                self._timestamp = time.time()
                self._local = ":".join(
                    '%s' % i for i in self._socket.getsockname())
            except Exception as error:
                _LOGGER.error("Connection error: %s:%s %s",
                              self.ip, self.port, error)
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
        return f"{self._local} -> {self.ip}:{self.port} retries: {self._retries} time: {socket_time}"

    def _request(self, message):
        # Create a TCP/IP socket
        self._connect()
        if self._socket is None:
            _LOGGER.debug("Socket is None: %s:%s", self.ip, self.port)
            return bytearray(0), False

        # Send data
        try:
            _LOGGER.debug("Sending %s message: %s",
                          self._socket_info(),
                          hex4logging(message, _LOGGER))
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
            if error.args[0] == 'timed out':
                _LOGGER.debug("Recv %s, timed out", self._socket_info())
                self._retries += 1
                return bytearray(0), True
            else:
                _LOGGER.debug("Recv %s time out error: %s",
                              self._socket_info(), error)
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
        except socket.error as error:
            _LOGGER.debug("Recv %s error: %s", self._socket_info(), error)
            self._disconnect()
            self._retries += 1
            return bytearray(0), True
        else:
            _LOGGER.debug("Recv %s response: %s", self._socket_info(),
                          hex4logging(response, _LOGGER))
            if len(response) == 0:
                _LOGGER.debug("Recv %s server closed socket",
                              self._socket_info())
                self._disconnect()
                self._retries += 1
                return bytearray(0), True
            else:
                self._retries = 0
                return response, True

    def authenticate(self, args: dict) -> bool:
        if args is not None:
            self._token = args.get('token')
            self._key = args.get('key')
            self._token = _to_hex(self._token)
            self._key = _to_hex(self._key)
        return self._authenticate()

    def _authenticate(self) -> bool:
        if not self._token or not self._key:
            raise Exception("missing token key pair")
        byte_token = binascii.unhexlify(self._token)

        response, success = None, False
        for i in range(self._connection_retries):
            request = self._security.encode_8370(byte_token,
                                                MSGTYPE_HANDSHAKE_REQUEST)
            response, success = self._request(request)

            if not success:
                if i > 0:
                    # Retry handshake
                    _LOGGER.info("Unable to perform handshake, retrying %d of 3", i+1, self._connection_retries)
                    time.sleep(i+1)
            else:
                break

        if not success or response is None:
            _LOGGER.error("Failed to perform handshake")
            return False
        response = response[8:72]

        tcp_key, success = self._security.tcp_key(
            response, binascii.unhexlify(self._key))
        if success:
            self._tcp_key = tcp_key.hex()
            # _LOGGER.debug("Got TCP key for %s %s",
            #               self._socket_info(level=logging.DEBUG),
            #               self._tcp_key)
            # After authentication, don’t send data immediately,
            # so sleep 1s.
            time.sleep(1)
        else:
            _LOGGER.warning("Failed to get TCP key for %s",
                            self._socket_info(level=logging.INFO))
        return success

    def status(self, cmd: MideaCommand,
               id: str | int = None,
               protocol: int = None) -> list[bytearray]:
        pkt_builder = LanPacketBuilder(int(self.id))
        pkt_builder.set_command(cmd)

        data = pkt_builder.finalize()
        # _LOGGER.debug("Packet for: %s(%s) data: %s", self.id, self.ip,
        #               hex4logging(data, _LOGGER))
        responses = self._appliance_send(data, protocol=protocol)
        # _LOGGER.debug("Got response(s) from: %s(%s)",
        #               self.id, self.ip)

        if len(responses) == 0:
            _LOGGER.warning("Got Null from: %s(%s)", self.id, self.ip)
            self._active = False
            self._support = False
        return responses

    def _appliance_send_8370(self,
                             data,
                             msgtype=MSGTYPE_ENCRYPTED_REQUEST) -> list[bytearray]:
        # socket_time = time.time() - self._timestamp
        # _LOGGER.debug("Data: %s msgtype: %s len: %s socket time: %s", hex4logging(data), msgtype, len(data), socket_time))
        if self._socket is None or self._tcp_key is None:
            _LOGGER.debug("Socket %s closed, Creating new socket",
                          self._socket_info())
            self._disconnect()

            for i in range(self._connection_retries):
                if not self._authenticate():
                    if i == self._connection_retries-1:
                        _LOGGER.error("Failed to authenticate %s",
                                      self._socket_info(logging.WARNING))
                        return []                        
                    _LOGGER.info("Retrying authenticate, %d out of %d: %s",
                                i+2, self._connection_retries,
                                self._socket_info())
                    self._disconnect()
                    
                    time.sleep((i+1)*2)
                else:
                    break


        if self._tcp_key is None:
            return []

        packets = []

        # copy from data in order to resend data
        original_data = bytearray.copy(data)
        data = self._security.encode_8370(data, msgtype)

        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self._request(data)
        if responses == bytearray(0) and self._retries < self._max_retries and b:
            packets = self._appliance_send_8370(original_data, msgtype)
            self._retries = 0
            return packets
        responses, self._buffer = self._security.decode_8370(
            self._buffer + responses)
        for response in responses:
            if len(response) > 40 + 16:
                response = self._security.aes_decrypt(response[40:-16])
            # header lenght is 10
            if len(response) > 10:
                packets.append(response[10:])
        return packets

    def _appliance_send(self, data, protocol: int = None):
        if protocol == 3:
            return self._appliance_send_8370(data)
        # time sleep retries second befor send data, default is 0
        time.sleep(self._retries)
        responses, b = self._request(data)
        # _LOGGER.debug("Get responses len: %d", len(responses))
        if responses == bytearray(0) and self._retries < self._max_retries and b:
            packets = self._appliance_send(data)
            self._retries = 0
            return packets
        packets = []
        if responses == bytearray(0):
            return packets
        dlen = len(responses)
        if responses[:2] == b'ZZ' and dlen > 5:
            i = 0
            # maybe multiple response
            while i < dlen:
                size = responses[i+4]
                data = self._security.aes_decrypt(responses[i:i+size][40:-16])
                # header lenght is 10
                if len(data) > 10:
                    packets.append(data)
                i += size
        elif responses[0] == 0xaa and dlen > 2:
            i = 0
            while i < dlen:
                size = responses[i+1]
                data = responses[i:i+size+1]
                # header lenght is 10
                if len(data) > 10:
                    packets.append(data)
                i += size + 1
        else:
            _LOGGER.error("Unknown responses %s", hex4logging(
                responses, _LOGGER, level=logging.ERROR))
        return packets
