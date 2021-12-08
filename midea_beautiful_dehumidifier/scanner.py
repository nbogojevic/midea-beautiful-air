from __future__ import annotations

import logging
import socket
from ipaddress import IPv4Network
from typing import Final

import ifaddr
from midea_beautiful_dehumidifier.crypto import Security
from midea_beautiful_dehumidifier.util import hex4logging, get_udpid
from midea_beautiful_dehumidifier.device import DehumidifierDevice
from midea_beautiful_dehumidifier.cloud import Cloud
from midea_beautiful_dehumidifier.lan import Lan

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)

BROADCAST_MSG: Final = bytearray([
    0x5a, 0x5a, 0x01, 0x11, 0x48, 0x00, 0x92, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x7f, 0x75, 0xbd, 0x6b, 0x3e, 0x4f, 0x8b, 0x76,
    0x2e, 0x84, 0x9c, 0x6e, 0x57, 0x8d, 0x65, 0x90,
    0x03, 0x6e, 0x9d, 0x43, 0x42, 0xa5, 0x0f, 0x1f,
    0x56, 0x9e, 0xb8, 0xec, 0x91, 0x8e, 0x92, 0xe5
])

DEVICE_INFO_MSG: Final = bytearray([
    0x5a, 0x5a, 0x15, 0x00, 0x00, 0x38, 0x00, 0x04,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x27, 0x33, 0x05,
    0x13, 0x06, 0x14, 0x14, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x03, 0xe8, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0xca, 0x8d, 0x9b, 0xf9, 0xa0, 0x30, 0x1a, 0xe3,
    0xb7, 0xe4, 0x2d, 0x53, 0x49, 0x47, 0x62, 0xbe
])


class ScannedDevice:

    def __init__(self, data: bytes | bytearray):
        self._security = Security()
        self.support = False
        self.token = None
        self.key = None
        data = bytearray(data)
        if data[:2] == b'ZZ':    # 5a5a
            self.version = 2
        elif data[:2] == b'\x83p':  # 8370
            self.version = 3
        else:
            self.version = 0
        if data[8:10] == b'ZZ':  # 5a5a
            data = data[8:-16]
        self.id = int.from_bytes(data[20:26], 'little')
        encrypt_data = data[40:-16]
        reply = self._security.aes_decrypt(encrypt_data)
        self.ip = '.'.join([str(i) for i in reply[3::-1]])
        _LOGGER.debug("Decrypted reply from %s reply=%s",
                      self.ip, hex4logging(reply, _LOGGER))
        self.port = int.from_bytes(reply[4:8], 'little')
        # ssid like midea_xx_xxxx net_xx_xxxx
        self.ssid = reply[41:41+reply[40]].decode("utf-8")
        self.mac = reply[24:36].decode("ascii")
        self.type = self.ssid.split('_')[1].lower()

    def __str__(self):
        return str(self.__dict__)

    def check_if_supported(self, cloud_service: Cloud) -> bool:
        lan_service = Lan(id=self.id, ip=self.ip, port=self.port)
        if self.version == 3:
            if not self._authenticate_v3(lan_service, cloud_service):
                return False

        if self.type == 'a1':
            self._device = DehumidifierDevice(service=lan_service)
            self._device.refresh()
            _LOGGER.debug("Device data: %s", self._device)
            self.support = self._device.support
        else:
            _LOGGER.debug("Found unsupported device: %s", self)
        return True

    def _authenticate_v3(self, lan_service: Lan, cloud_service: Cloud):
        for udpid in [
            get_udpid(self.id.to_bytes(6, 'little')),
            get_udpid(self.id.to_bytes(6, 'big'))
        ]:
            token, key = cloud_service.get_token(udpid)
            auth = lan_service.authenticate({'key': key, 'token': token})
            if auth:
                self.token, self.key = token, key
                return True
        return False


class MideaDiscovery:

    def __init__(self, cloud: Cloud, broadcast_retries: int, broadcast_timeout: float, broadcast_networks: list[str] | None):
        """Init discovery."""
        self._cloud = cloud
        self._broadcast_retries = broadcast_retries
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.settimeout(broadcast_timeout)
        self.result = set()
        self.found_devices = set()
        self.networks = broadcast_networks

    def collect_devices(self) -> list[ScannedDevice]:
        for i in range(self._broadcast_retries):
            _LOGGER.debug("Broadcasting message %d of %d",
                          i+1, self._broadcast_retries)
            self._broadcast_message()
            scanned_devices: set[ScannedDevice] = set()
            try:
                while True:
                    data, addr = self.socket.recvfrom(512)
                    ip = addr[0]
                    if ip not in self.found_devices:
                        _LOGGER.debug("Reply from %s payload=%s",
                                    ip, hex4logging(data, _LOGGER))
                        self.found_devices.add(ip)
                        device = ScannedDevice(data)
                        if device.version == 0:
                            _LOGGER.error(
                                "Unable to load data from device %s or unsupported version", ip)
                            continue
                        scanned_devices.add(device)

            except socket.timeout:
                _LOGGER.debug("Finished broadcast collection")
            for sd in scanned_devices:
                if sd.check_if_supported(self._cloud):
                    self.result.add(sd)

        return list(self.result)

    def _broadcast_message(self):
        for broadcast_address in self._get_networks():
            try:
                self.socket.sendto(BROADCAST_MSG, (broadcast_address, 6445))
                self.socket.sendto(BROADCAST_MSG, (broadcast_address, 20086))
            except:
                _LOGGER.debug("Unable to send broadcast to: %s",
                              broadcast_address)

    def _get_networks(self) -> list[str]:
        if self.networks is None:
            nets: list[IPv4Network] = []
            adapters: list[ifaddr.Adapter] = ifaddr.get_adapters()
            for adapter in adapters:
                ip: ifaddr.IP
                for ip in adapter.ips:
                    if ip.is_IPv4 and ip.network_prefix < 32:
                        localNet = IPv4Network(
                            f"{ip.ip}/{ip.network_prefix}", strict=False)
                        if (localNet.is_private
                            and not localNet.is_loopback
                                and not localNet.is_link_local):
                            nets.append(localNet)
            self.networks = list()
            if not nets:
                _LOGGER.error("No valid networks detected to send broadcast")
            else:
                for net in nets:
                    _LOGGER.debug("Network %s, broadcast address %s",
                                  net.network_address, net.broadcast_address)
                    self.networks.append(str(net.broadcast_address))
        return self.networks


def find_devices_on_lan(
        cloud_service: Cloud,
        broadcast_retries: int,
        appliances: list,
        broadcast_timeout: float,
        broadcast_networks: list[str] | None,
        devices: list[DehumidifierDevice]):

    discovery = MideaDiscovery(cloud=cloud_service,
                               broadcast_retries=broadcast_retries,
                               broadcast_timeout=broadcast_timeout,
                               broadcast_networks=broadcast_networks)
    _LOGGER.debug("Starting LAN discovery")

    scanned_devices = list(discovery.collect_devices())
    scanned_devices.sort(key=lambda x: x.id)
    for scanned in scanned_devices:
        if any(True for d in devices if str(d.id) == str(scanned.id)):
            _LOGGER.debug("Known device %s", scanned.id)
            # TODO update device config if needed
            continue

        appliance = next(
            filter(lambda a: a['id'] == str(scanned.id), appliances), None)
        if appliance:
            scanned._device.set_device_detail(appliance)
            scanned._device.refresh()
            devices.append(scanned._device)
            _LOGGER.info("*** Found dehumidifier id=%s, ip=%s",
                         scanned._device.id,
                         scanned._device.target())
        else:
            _LOGGER.warning("!!! Found a device that is not registered to account: id=%s, ip=%s, type=%s",
                            scanned.id, scanned.ip, scanned.type)
