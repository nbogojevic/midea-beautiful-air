from __future__ import annotations

import logging
import socket
from ipaddress import IPv4Network

import ifaddr

from midea_beautiful_dehumidifier.cloud import CloudService
from midea_beautiful_dehumidifier.device import is_supported_device
from midea_beautiful_dehumidifier.lan import LanDevice, BROADCAST_MSG
from midea_beautiful_dehumidifier.util import hex4log

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

_LOGGER = logging.getLogger(__name__)


class MideaDiscovery:

    def __init__(self, cloud: CloudService, broadcast_retries: int, broadcast_timeout: float, broadcast_networks: list[str] | None):
        """Init discovery."""
        self._cloud = cloud
        self._broadcast_retries = broadcast_retries
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.settimeout(broadcast_timeout)
        self.result = set()
        self.found_devices = set()
        self.networks = broadcast_networks

    def collect_devices(self) -> list[LanDevice]:
        for i in range(self._broadcast_retries):
            _LOGGER.debug("Broadcasting message %d of %d",
                          i+1, self._broadcast_retries)
            self._broadcast_message()
            scanned_devices: set[LanDevice] = set()
            try:
                while True:
                    data, addr = self.socket.recvfrom(512)
                    ip = addr[0]
                    if ip not in self.found_devices:
                        _LOGGER.debug("Reply from %s payload=%s",
                                    ip, hex4log(data, _LOGGER))
                        self.found_devices.add(ip)
                        device = LanDevice(discovery_data=data)
                        if device.version == 0:
                            _LOGGER.error(
                                "Unable to load data from device %s or unsupported version", ip)
                            continue
                        scanned_devices.add(device)

            except socket.timeout:
                _LOGGER.debug("Finished broadcast collection")
            for sd in scanned_devices:
                if sd.identify_device(self._cloud):
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
        cloud_service: CloudService,
        broadcast_retries: int,
        appliances: list,
        broadcast_timeout: float,
        broadcast_networks: list[str] | None,
        devices: list[LanDevice]):

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
        if appliance and scanned.state is not None:
            scanned.state.set_device_detail(appliance)
            scanned.refresh()
            devices.append(scanned)
            _LOGGER.info("*** Found dehumidifier id=%s, ip=%s:%d",
                         scanned.id,
                         scanned.ip,
                         scanned.port)
        else:
            _LOGGER.warning("!!! Found a device that is not registered to account: id=%s, ip=%s, type=%s",
                            scanned.id, scanned.ip, scanned.type)

def find_devices(app_key, account, password, broadcast_retries=2, retries=4, broadcast_timeout=3, broadcast_networks=None):
    cloud_service = CloudService(app_key=app_key, account=account, password=password)
    cloud_service.authenticate()
    appliances = cloud_service.list_appliances()
    appliances_count = sum(is_supported_device(a["type"]) for a in appliances)
    _LOGGER.info("Account has %d supported device(s) out of %d appliance(s)",
                 appliances_count, len(appliances))

    devices: list[LanDevice] = []

    _LOGGER.debug("Scanning for midea dehumidifier appliances")
    for i in range(retries):
        if i > 0:
            _LOGGER.info(
                "Re-scanning network for midea dehumidifier appliances %d of %d", i+1, retries)
        find_devices_on_lan(
            appliances=appliances,
            devices=devices,
            cloud_service=cloud_service,
            broadcast_retries=broadcast_retries,
            broadcast_timeout=broadcast_timeout,
            broadcast_networks=broadcast_networks)
        if len(devices) >= appliances_count:
            break
        if i == 0:
            _LOGGER.warning("Some appliance(s) where not discovered on local LAN: %d discovered out of %d",
                            len(devices), appliances_count)

            for appliance in appliances:
                if not any(True for d in devices if str(d.id) == str(appliance['id'])):
                    _LOGGER.warning("Unable to find appliance id=%s, type=%s",
                                 appliance['id'],
                                 appliance['type'])

    _LOGGER.info("Found %d of %d device(s)", len(devices), appliances_count)
    return devices
