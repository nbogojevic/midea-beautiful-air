"""Scans local network for Midea appliances."""
from __future__ import annotations

from ipaddress import IPv4Network
import logging
import socket
from typing import Final

from ifaddr import IP, Adapter, get_adapters

from midea_beautiful_dehumidifier.appliance import Appliance
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.lan import DISCOVERY_MSG, LanDevice
from midea_beautiful_dehumidifier.midea import DISCOVERY_PORT
from midea_beautiful_dehumidifier.version import __version__
from midea_beautiful_dehumidifier.util import _Hex

_LOGGER = logging.getLogger(__name__)

_BROADCAST_TIMEOUT: Final = 3
_BROADCAST_RETRIES: Final = 2


def _get_broadcast_addresses(addresses: list[str] = []) -> list[str]:
    """Retrieves local networks by iterating local network adapters

    Returns:
        list[str]: list of local network broadcast addresses
    """
    # If addresses were provided, then we will send discovery to them
    # even if they are not in private ip range
    provided_address = True
    if not addresses:
        addresses = []
        provided_address = False
        adapters: list[Adapter] = get_adapters()
        for adapter in adapters:
            ip: IP
            for ip in adapter.ips:
                if ip.is_IPv4:
                    addresses.append(f"{ip.ip}/{ip.network_prefix}")
    nets: list[IPv4Network] = []

    for addr in addresses:
        localNet = IPv4Network(addr, strict=False)
        if (
            (localNet.is_private or provided_address)
            and not localNet.is_loopback
            and not localNet.is_link_local
        ):
            nets.append(localNet)
    networks = list()
    if not nets:
        _LOGGER.error("No valid networks to send broadcast to")
    else:
        for net in nets:
            _LOGGER.debug(
                "Network %s, broadcast address %s",
                net.network_address,
                net.broadcast_address,
            )
            networks.append(str(net.broadcast_address))
    return networks


class MideaDiscovery:
    def __init__(self, cloud: MideaCloud | None):
        self._cloud = cloud
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(_BROADCAST_TIMEOUT)
        self._known_ips = set()
        self._networks: list[str] = []

    def collect_appliances(self, networks: list[str] = []) -> list[LanDevice]:
        """Find all appliances on the local network."""

        self._broadcast_message(networks)

        scanned_appliances: set[LanDevice] = set()
        try:
            while True:
                data, addr = self._socket.recvfrom(512)
                ip = addr[0]
                if ip not in self._known_ips:
                    _LOGGER.log(5, "Reply from ip=%s payload=%s", ip, _Hex(data))
                    self._known_ips.add(ip)
                    appliance = LanDevice(data=data)
                    if appliance.is_supported:
                        scanned_appliances.add(appliance)
                    else:
                        _LOGGER.error("Unable to load data for appliance %s", appliance)

        except socket.timeout:
            # If we got timeout, it was enough time to wait for broadcast response
            _LOGGER.debug("Finished broadcast collection")

        # Return only successfully identified appliances
        return [sd for sd in scanned_appliances if sd.is_identified(self._cloud)]

    def _broadcast_message(self, networks: list[str]) -> None:

        for addr in networks:
            _LOGGER.debug("Broadcasting to %s", addr)
            try:
                self._socket.sendto(DISCOVERY_MSG, (addr, DISCOVERY_PORT))
            except Exception:
                _LOGGER.debug("Unable to send broadcast to: %s", addr)


def _add_missing_appliances(
    cloud_appliances: list[dict], appliances: list[LanDevice], count: int
) -> None:
    """
    Utility method to add placeholders for appliances which were not
    discovered on local network
    """
    _LOGGER.warning(
        (
            "Some appliance(s) where not discovered on local network(s):"
            " %d discovered out of %d"
        ),
        len(appliances),
        count,
    )
    for details in cloud_appliances:
        appliance_type = details["type"]
        if Appliance.supported(appliance_type):
            id = details["id"]
            for appliance in appliances:
                if id == str(appliance.id):
                    break
            else:
                appliance = LanDevice(id=id, appliance_type=appliance_type)
                appliances.append(appliance)
                _LOGGER.warning(
                    (
                        "Unable to discover registered appliance"
                        " name=%s, id=%s, type=%s"
                    ),
                    details["name"],
                    id,
                    appliance_type,
                )
            appliance.name = details["name"]


def _find_appliances_on_lan(
    cloud: MideaCloud | None, networks: list[str]
) -> list[LanDevice]:

    discovery = MideaDiscovery(cloud=cloud)
    appliances: list[LanDevice] = []
    _LOGGER.debug("Starting LAN discovery")
    cloud_appliances = cloud.list_appliances() if cloud else []
    count = sum(Appliance.supported(a["type"]) for a in cloud_appliances)
    for i in range(_BROADCAST_RETRIES):
        _LOGGER.debug("Broadcast attempt %d of max %d", i + 1, _BROADCAST_RETRIES)

        scanned_appliances = list(discovery.collect_appliances(networks))
        scanned_appliances.sort(key=lambda appliance: appliance.id)
        for scanned in scanned_appliances:
            for appliance in appliances:
                if str(appliance.id) == str(scanned.id):
                    _LOGGER.debug("Known appliance %s", scanned.id)
                    if appliance.ip != scanned.ip:
                        # Already known
                        appliance.update(scanned)
                    break

            for details in cloud_appliances:
                if details["id"] == str(scanned.id):
                    scanned.name = details["name"]
                    appliances.append(scanned)
                    _LOGGER.info("Found appliance %s", scanned)
                    break
            else:
                _LOGGER.warning(
                    "Found an appliance that is not registered to the account: %s",
                    scanned,
                )
        if len(appliances) >= count:
            _LOGGER.info("Found %d of %d appliance(s)", len(appliances), count)
            break
    if len(appliances) < count:
        _add_missing_appliances(cloud_appliances, appliances, count)
    return appliances


def find_appliances(
    cloud: MideaCloud | None = None,
    appkey=None,
    account=None,
    password=None,
    appid=None,
    networks: list[str] = [],
) -> list[LanDevice]:
    _LOGGER.debug("Library version=%s", __version__)
    if not cloud and account and password:
        cloud = MideaCloud(appkey, account, password, appid)
        cloud.authenticate()

    addresses = _get_broadcast_addresses(networks)
    _LOGGER.debug("Scanning for midea dehumidifier appliances via %s", addresses)
    return _find_appliances_on_lan(cloud, addresses)
