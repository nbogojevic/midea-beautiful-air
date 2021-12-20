"""Scans local network for Midea appliances."""
from __future__ import annotations

from ipaddress import IPv4Network
import logging
import socket

from ifaddr import IP, Adapter, get_adapters

from midea_beautiful_dehumidifier.appliance import Appliance
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.lan import DISCOVERY_MSG, _Hex, LanDevice
from midea_beautiful_dehumidifier.midea import DISCOVERY_PORT

_LOGGER = logging.getLogger(__name__)


class MideaDiscovery:
    def __init__(
        self,
        cloud: MideaCloud,
        timeout: float,
        networks: list[str] | None,
    ):
        self._cloud = cloud
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(timeout)
        self._known_ips = set()
        self._networks = networks

    def collect_appliances(self) -> list[LanDevice]:
        """Find all appliances on the local network."""

        self._broadcast_message()

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
        return [sd for sd in scanned_appliances if sd.identify_appliance(self._cloud)]

    def _broadcast_message(self) -> None:
        for addr in self._get_networks():
            try:
                self._socket.sendto(DISCOVERY_MSG, (addr, DISCOVERY_PORT))
            except Exception:
                _LOGGER.debug("Unable to send broadcast to: %s", addr)

    def _get_networks(self) -> list[str]:
        """Retrieves local networks by iterating local network adapters

        Returns:
            list[str]: list of local network broadcast addresses
        """
        if self._networks is None:
            nets: list[IPv4Network] = []
            adapters: list[Adapter] = get_adapters()
            for adapter in adapters:
                ip: IP
                for ip in adapter.ips:
                    if ip.is_IPv4 and ip.network_prefix < 32:
                        localNet = IPv4Network(
                            f"{ip.ip}/{ip.network_prefix}", strict=False
                        )
                        if (
                            localNet.is_private
                            and not localNet.is_loopback
                            and not localNet.is_link_local
                        ):
                            nets.append(localNet)
            self._networks = list()
            if not nets:
                _LOGGER.error("No valid networks to send broadcast to")
            else:
                for net in nets:
                    _LOGGER.debug(
                        "Network %s, broadcast address %s",
                        net.network_address,
                        net.broadcast_address,
                    )
                    self._networks.append(str(net.broadcast_address))
        return self._networks


def _add_missing_appliances(
    cloud: MideaCloud, appliances: list[LanDevice], appliances_count: int
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
        appliances_count,
    )
    for details in cloud.list_appliances():
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


def find_appliances_on_lan(
    cloud: MideaCloud,
    appliances: list[LanDevice],
    retries: int,
    timeout: float,
    networks: list[str] | None,
) -> None:

    discovery = MideaDiscovery(
        cloud=cloud,
        timeout=timeout,
        networks=networks,
    )
    _LOGGER.debug("Starting LAN discovery")
    count = sum(Appliance.supported(a["type"]) for a in cloud.list_appliances())
    for i in range(retries):
        _LOGGER.debug("Broadcast attempt %d of max %d", i + 1, retries)

        scanned_appliances = list(discovery.collect_appliances())
        scanned_appliances.sort(key=lambda appliance: appliance.id)
        for scanned in scanned_appliances:
            for appliance in appliances:
                if str(appliance.id) == str(scanned.id):
                    _LOGGER.debug("Known appliance %s", scanned.id)
                    if appliance.ip != scanned.ip:
                        # Already known
                        appliance.update(scanned)
                    break

            for details in cloud.list_appliances():
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
        _add_missing_appliances(cloud, appliances, count)


def find_appliances(
    appkey=None,
    account=None,
    password=None,
    appid=None,
    cloud: MideaCloud | None = None,
    retries: int = 2,
    timeout: int = 3,
    networks: list[str] | None = None,
) -> list[LanDevice]:
    if cloud is None:
        cloud = MideaCloud(appkey, account, password, appid)
        cloud.authenticate()

    appliances: list[LanDevice] = []

    _LOGGER.debug("Scanning for midea dehumidifier appliances")
    find_appliances_on_lan(
        appliances=appliances,
        cloud=cloud,
        retries=retries,
        timeout=timeout,
        networks=networks,
    )

    return appliances
