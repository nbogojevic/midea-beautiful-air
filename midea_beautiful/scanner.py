"""Scans network for Midea appliances."""
from __future__ import annotations

import logging
import socket
from typing import Final

from midea_beautiful.appliance import Appliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import DISCOVERY_MSG, LanDevice, matches_lan_cloud
from midea_beautiful.midea import DISCOVERY_PORT
from midea_beautiful.util import SPAM, TRACE
from midea_beautiful.version import __version__

# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments

_LOGGER = logging.getLogger(__name__)

_BROADCAST_TIMEOUT: Final = 3
_BROADCAST_RETRIES: Final = 3


class _MideaDiscovery:
    """Utility class to discover appliances on local network"""

    def __init__(self, cloud: MideaCloud | None) -> None:
        self._cloud = cloud
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(_BROADCAST_TIMEOUT)
        self._known_ips = set()

    def _collect_appliances(self, addresses: list[str] = None) -> list[LanDevice]:
        """Find all appliances on the local network."""
        addresses = addresses or []

        self._broadcast_message(addresses)

        scanned_appliances: set[LanDevice] = set()
        try:
            while True:
                data, addr = self._socket.recvfrom(512)
                ip_address = addr[0]
                if ip_address not in self._known_ips:
                    _LOGGER.log(
                        TRACE, "Reply from address=%s payload=%s", ip_address, data
                    )
                    self._known_ips.add(ip_address)
                    appliance = LanDevice(data=data)
                    if Appliance.supported(appliance.type):
                        scanned_appliances.add(appliance)
                    else:
                        _LOGGER.debug("Not supported appliance %s", appliance)

        except socket.timeout:
            # If we got timeout, it was enough time to wait for broadcast response
            _LOGGER.debug("Finished broadcast collection")

        # Return only successfully identified appliances
        if not self._cloud:
            return list(scanned_appliances)
        return [sd for sd in scanned_appliances if sd.is_identified(self._cloud)]

    def _broadcast_message(self, addresses: list[str]) -> None:

        for addr in addresses:
            _LOGGER.debug("Broadcasting to %s", addr)
            try:
                _LOGGER.log(
                    SPAM, "UDP broadcast %s:%d %s", addr, DISCOVERY_PORT, DISCOVERY_MSG
                )
                self._socket.sendto(DISCOVERY_MSG, (addr, DISCOVERY_PORT))
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.debug("Unable to send broadcast to: %s cause %s", addr, ex)

    def broadcast(
        self,
        count,
        addresses: list[str],
        appliances: list[LanDevice],
        cloud_appliances: list[dict],
        known_cloud_appliances: set[str],
        discover_all: bool,
    ):
        """Broadcasts and discovers appliances on the networks"""
        _LOGGER.debug(
            "Broadcast attempt %d of max %d",
            count + 1,
            _BROADCAST_RETRIES,
        )

        scanned_appliances = list(self._collect_appliances(addresses))

        scanned_appliances.sort(key=lambda appliance: appliance.appliance_id)
        for scanned in scanned_appliances:
            for appliance in appliances:
                if appliance.appliance_id == scanned.appliance_id:
                    if appliance.address != scanned.address:
                        _LOGGER.debug(
                            "Known appliance %s, data changed %s", appliance, scanned
                        )
                        appliance.update(scanned)
                    break
            else:
                if not discover_all:
                    self._match_with_cloud(
                        appliances, cloud_appliances, known_cloud_appliances, scanned
                    )
                else:
                    appliances.append(scanned)

    def _match_with_cloud(
        self, appliances, cloud_appliances, known_cloud_appliances, scanned
    ):
        for details in cloud_appliances:
            if matches_lan_cloud(scanned, details):
                scanned.name = details["name"]
                appliances.append(scanned)
                _LOGGER.info("Found appliance %s %s", scanned, known_cloud_appliances)
                if details["id"] in known_cloud_appliances:
                    known_cloud_appliances.remove(details["id"])
                break
        else:
            _LOGGER.warning(
                "Found an appliance that is not registered to the account: %s",
                scanned,
            )


def _add_missing_appliances(
    cloud_appliances: list[dict], appliances: list[LanDevice], count: int
) -> None:
    """
    Utility method to add placeholders for appliances which were not
    discovered on local network
    """
    _LOGGER.warning(
        (
            "Some appliance(s) where not discovered on local network:"
            " %d discovered out of %d"
        ),
        len(appliances),
        count,
    )
    for known in cloud_appliances:
        if Appliance.supported(known["type"]):
            for local in appliances:
                if matches_lan_cloud(local, known):
                    break
            else:
                local = LanDevice(
                    appliance_id=known["id"],
                    appliance_type=known["type"],
                    serial_number=known["sn"],
                )
                appliances.append(local)
                _LOGGER.warning(
                    "Unable to discover registered appliance %s",
                    known,
                )
            local.name = known["name"]


def _find_appliances_on_lan(
    cloud: MideaCloud | None, addresses: list[str], appliances: list[LanDevice] = None
) -> list[LanDevice]:

    discovery = _MideaDiscovery(cloud=cloud)
    appliances = appliances or []
    _LOGGER.debug("Starting LAN discovery")
    discover_all = not cloud
    cloud_appliances = cloud.list_appliances() if cloud else []
    count = sum(Appliance.supported(a["type"]) for a in cloud_appliances)
    known_cloud_appliances = set(a["id"] for a in cloud_appliances)
    for i in range(_BROADCAST_RETRIES):
        discovery.broadcast(
            count=i,
            addresses=addresses,
            appliances=appliances,
            cloud_appliances=cloud_appliances,
            known_cloud_appliances=known_cloud_appliances,
            discover_all=discover_all,
        )
        if cloud and len(known_cloud_appliances) == 0:
            break
    if cloud:
        _LOGGER.info("Found %d of %d appliance(s)", len(appliances), count)
    else:
        _LOGGER.info("Found %d appliance(s)", len(appliances))

    if len(appliances) < count:
        _add_missing_appliances(cloud_appliances, appliances, count)
    return appliances


def find_appliances(
    cloud: MideaCloud | None = None,
    appkey: str | None = None,
    account: str = None,
    password: str = None,
    appid: str = None,
    addresses: list[str] = None,
    appliances: list[LanDevice] = None,
) -> list[LanDevice]:
    """Finds appliances on local network

    Args:
        cloud (MideaCloud, optional): Cloud client. Defaults to None.
        appkey (str, optional): Midea mobile application key. Defaults to None.
        account (str, optional): User account. Defaults to None.
        password (str, optional): Account password. Defaults to None.
        appid (str, optional): Midea mobile application key. Defaults to None.
        addresses (list[str], optional): List of addresses to search.
        If omitted, search all addresses (255.255.255.255). Defaults to None.
        appliances (list[LanDevice], optional): List of known appliances.
        Defaults to None.

    Returns:
        list[LanDevice]: [description]
    """
    addresses = addresses or ["255.255.255.255"]
    _LOGGER.debug("Library version=%s", __version__)
    if not cloud and account and password:
        cloud = MideaCloud(
            appkey=appkey, account=account, password=password, appid=appid
        )
        cloud.authenticate()

    _LOGGER.debug("Scanning for midea dehumidifier appliances via %s", addresses)
    return _find_appliances_on_lan(cloud, addresses, appliances)
