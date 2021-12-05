from __future__ import annotations

from typing import Final

import asyncio
from ipaddress import IPv4Network
import ifaddr
import logging
import socket

from midea_beautiful_dehumidifier.cloud import cloud
from midea_beautiful_dehumidifier.lan import lan
from midea_beautiful_dehumidifier.device import midea_device, unknown_device, device_from_type, device_name_from_type
from midea_beautiful_dehumidifier.util import hex4logging, get_udpid, Security
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


class scandevice:

    def __init__(self, cloud_service: cloud):
        self.cloud_service = cloud_service
        self._security = Security()
        self.type = 'unknown'
        self.support = False
        self.version = 0
        self.ip = '127.0.0.1'
        self.id: int = 0
        self.port: int = 6444
        self.token = None
        self.key = None
        self.ssid = None

    def __str__(self):
        return str(self.__dict__)

    async def async_support_test(self):
        lan_service = lan(id=self.id, ip=self.ip, port=self.port)
        self._device = unknown_device(service=lan_service)
        if self.version == 3:
            self._device = await self.async_support_testv3(self._device)

        if self.type == 'ac' or self.type == 'a1':
            self._device = device_from_type(self.type, service=lan_service)
            self._device.refresh()
            _LOGGER.debug("Device data: %s", self._device)
            self.support = self._device.support
        _LOGGER.debug("Found a device: %s", self)
        return self

    async def async_support_testv3(self, _device: midea_device):
        for udpid in [
            get_udpid(self.id.to_bytes(6, 'little')),
            get_udpid(self.id.to_bytes(6, 'big'))
        ]:
            token, key = self.cloud_service.get_token(udpid)
            auth = _device.get_service().authenticate(
                {'key': key, 'token': token})
            if auth:
                self.token, self.key = token, key
                return _device
        return _device

    @staticmethod
    async def async_load(ip, data: bytes | bytearray, cloud_service: cloud):
        if len(data) >= 104 and (data[:2] == b'ZZ' or data[8:10] == b'ZZ'):
            return scandeviceV2V3(data, cloud_service=cloud_service)
        if data[:6] == b'<?xml ':
            return scandeviceV1(ip, data, cloud_service=cloud_service)


class scandeviceV2V3(scandevice):
    def __init__(self, data: bytes | bytearray, cloud_service: cloud):
        super().__init__(cloud_service=cloud_service)
        self.insert(data)

    def insert(self, data: bytes | bytearray):
        data = bytearray(data)
        if data[:2] == b'ZZ':    # 5a5a
            self.version = 2
        if data[:2] == b'\x83p':  # 8370
            self.version = 3
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


class scandeviceV1(scandevice):
    def __init__(self, ip,
                 data: bytes | bytearray,
                 cloud_service: cloud):
        super().__init__(cloud_service=cloud_service)
        self.version = 1
        self.ip = ip
        self.insert(data)

    def insert(self, data: bytes | bytearray):
        root = ET.fromstring(data.decode(encoding="utf-8", errors="replace"))
        child = root.find('body/device')
        if child is None:
            return
        m = child.attrib
        self.port, self.type = int(m['port']), str(
            hex(int(m['apc_type'])))[2:].lower()

        self.id = self._get_device_id()

    def _get_device_id(self):
        response = self._get_device_info()
        if len(response) == 0:
            return 0
        if response[64:-16][:6] == b'<?xml ':
            xml = response[64:-16]
            root = ET.fromstring(xml.decode(
                encoding='utf-8', errors='replace'))
            child = root.find('smartDevice')
            if child is not None:
                m = child.attrib
                return int.from_bytes(bytearray.fromhex(m['devId']), 'little')
        return 0

    def _get_device_info(self):
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)

        try:
            # Connect the Device
            device_address = (self.ip, self.port)
            sock.connect(device_address)

            # Send data
            _LOGGER.debug("Sending device info message to %s:%s msg=%s",
                          self.ip, self.port, hex4logging(DEVICE_INFO_MSG, _LOGGER))
            sock.sendall(DEVICE_INFO_MSG)

            # Received data
            response = sock.recv(512)
        except socket.error:
            _LOGGER.info("Couldn't connect to device %s:%s",
                         self.ip, self.port)
            return bytearray(0)
        except socket.timeout:
            _LOGGER.info("Connect the Device %s:%s TimeOut for 8s. Don't care if small number of time outs occured. Many time outs may indicate unsupported device.",
                         self.ip, self.port)
            return bytearray(0)
        finally:
            sock.close()
        _LOGGER.debug("Received from  %s:%s %s",
                      self.ip, self.port, hex4logging(response, _LOGGER))
        return response


class MideaDiscovery:

    def __init__(self, cloud_service: cloud, packets, broadcast_timeout, broadcast_networks: list[str] | None):
        """Init discovery."""
        self.cloud_service = cloud_service
        self._packets = packets
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.settimeout(broadcast_timeout)
        self.result = set()
        self.found_devices = set()
        self.networks = broadcast_networks

    async def async_get_all(self) -> list[scandevice]:
        for i in range(self._packets):
            _LOGGER.debug("Broadcasting message %d of %d", i+1, self._packets)
            await self._async_broadcast_message()
            tasks: set[asyncio.Task] = set()
            while True:
                task = await self._async_get_response_task()
                if task:
                    tasks.add(task)
                else:
                    break
            if len(tasks) > 0:
                await asyncio.wait(tasks)
                for task in tasks:
                    self.result.add(task.result())
        return list(self.result)

    async def _async_get_response_task(self, ip=None):
        try:
            data, addr = self.socket.recvfrom(512)
            _LOGGER.debug("Got response from addr=%s ip=%s", addr, ip)
            if ip is not None and addr[0] != ip:
                return None
            else:
                ip = addr[0]
            if ip not in self.found_devices:
                _LOGGER.debug("Local reply %s %s", ip,
                              hex4logging(data, _LOGGER))
                self.found_devices.add(ip)
                device = await scandevice.async_load(ip=ip, data=data,
                                                     cloud_service=self.cloud_service)
                if device is None:
                    _LOGGER.error("Unable to load data from device %s", ip)
                    return None
                return asyncio.create_task(device.async_support_test())
        except socket.timeout:
            _LOGGER.debug("Socket timeout")
            return None

    async def _async_broadcast_message(self):
        for broadcast_address in self._get_networks():
            try:
                self.socket.sendto(
                    BROADCAST_MSG, (broadcast_address, 6445)
                )
                self.socket.sendto(
                    BROADCAST_MSG, (broadcast_address, 20086)
                )
            except:
                _LOGGER.debug("Unable to send broadcast to: %s",
                            str(broadcast_address))

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
                    _LOGGER.debug("Network %s, boradcast address %s",
                          net.network_address, net.broadcast_address)
                    self.networks.append(str(net.broadcast_address))
        return self.networks

async def _async_find_devices_on_lan(
        cloud_service: cloud,
        packets: int,
        appliances: list,
        broadcast_timeout: float,
        broadcast_networks: list[str] | None,
        devices: list[midea_device]):

    discovery = MideaDiscovery(cloud_service=cloud_service, packets=packets, broadcast_timeout=broadcast_timeout, broadcast_networks=broadcast_networks)
    _LOGGER.debug("Starting LAN discovery")

    scanned_devices = list(await discovery.async_get_all())
    scanned_devices.sort(key=lambda x: x.id)
    for scanned in scanned_devices:
        if any(True for d in devices if str(d.id) == str(scanned.id)):
            _LOGGER.debug("Known device %s", scanned.id)
            # TODO update device config if needed
            continue

        appliance = next(filter(lambda a: a['id'] == str(
            scanned.id), appliances), None)
        if appliance:
            scanned._device.set_device_detail(appliance)
            scanned._device.refresh()
            devices.append(scanned._device)
            _LOGGER.info("*** Found a %s: id=%s, ip=%s",
                         device_name_from_type(scanned._device.type),
                         scanned._device.id,
                         scanned._device.get_service().target())
        else:
            _LOGGER.warning("!!! Found a device that is not registered to account: id=%s, ip=%s, type=%s",
                            scanned.id, scanned.ip, scanned.type)


async def async_find_devices(app_key, account, password, use_midea_cloud: bool = False, packets=5, retries=4, broadcast_timeout=5, broadcast_networks=None):
    cloud_service = cloud(app_key=app_key, account=account, password=password)
    cloud_service.authenticate()
    appliances = cloud_service.list_appliances()
    appliances_count = sum(not device_name_from_type(appliance["type"]).startswith("unknown")
                           for appliance in appliances)
    _LOGGER.info("Account %s has %d supported device(s) out of %d appliance(s)",
                 account, appliances_count, len(appliances))

    devices: list[midea_device] = []

    if use_midea_cloud:

        for appliance in appliances:
            if device_name_from_type(appliance['type']).startswith('unknown'):
                continue
            device: midea_device = device_from_type(
                appliance['type'], cloud_service)
            device.set_device_detail(appliance)
            device.refresh()
            _LOGGER.info("Found %s: id=%s", device_name_from_type(
                device.type), device.id)
    else:
        _LOGGER.info("Scanning for midea appliances")
        for i in range(retries):
            if i > 0:
                _LOGGER.info(
                    "Re-scanning network for midea appliances %d of %d", i+1, retries)
            await _async_find_devices_on_lan(
                appliances=appliances,
                devices=devices,
                cloud_service=cloud_service,
                packets=packets,
                broadcast_timeout=broadcast_timeout,
                broadcast_networks=broadcast_networks)
            if len(devices) >= appliances_count:
                break
            if i == 0:
                _LOGGER.warning("Some appliance(s) where not discovered on local LAN: %d discovered out of %d",
                                len(devices), appliances_count)

                for appliance in appliances:
                    if not any(True for d in devices if str(d.id) == str(appliance['id'])):
                        _LOGGER.info("Missing appliance id=%s, type=%s",
                                     appliance['id'],
                                     device_name_from_type(appliance['type']))

    _LOGGER.info("Found %d of %d device(s)", len(devices), appliances_count)
    return devices
