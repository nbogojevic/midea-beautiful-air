from __future__ import annotations

import logging
import socket
from ipaddress import IPv4Network

import ifaddr

from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.appliance import Appliance
from midea_beautiful_dehumidifier.lan import BROADCAST_MSG, LanDevice

_LOGGER = logging.getLogger(__name__)


class MideaDiscovery:
    def __init__(
        self,
        cloud: MideaCloud,
        broadcast_timeout: float,
        broadcast_networks: list[str] | None,
    ):
        self._cloud = cloud
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.settimeout(broadcast_timeout)
        self._found_appliances = set()
        self._networks = broadcast_networks

    def collect_appliances(self) -> list[LanDevice]:
        """Find all appliances on the local network."""

        self._broadcast_message()
        self._result = set()

        scanned_appliances: set[LanDevice] = set()
        try:
            while True:
                data, addr = self._socket.recvfrom(512)
                ip = addr[0]
                if ip not in self._found_appliances:
                    _LOGGER.log(5, "Reply from ip=%s payload=%s", ip, data)
                    self._found_appliances.add(ip)
                    appliance = LanDevice(discovery_data=data)
                    if appliance.version == 0:
                        _LOGGER.error(
                            "Unable to load data from appliance ip=%s", ip
                        )
                        continue
                    scanned_appliances.add(appliance)

        except socket.timeout:
            _LOGGER.debug("Finished broadcast collection")
        for sd in scanned_appliances:
            if sd.identify_appliance(self._cloud):
                self._result.add(sd)

        return list(self._result)

    def _broadcast_message(self):
        for broadcast_address in self._get_networks():
            try:
                self._socket.sendto(BROADCAST_MSG, (broadcast_address, 6445))
            except Exception:
                _LOGGER.debug(
                    "Unable to send broadcast to: %s", broadcast_address
                )

    def _get_networks(self) -> list[str]:
        if self._networks is None:
            nets: list[IPv4Network] = []
            adapters: list[ifaddr.Adapter] = ifaddr.get_adapters()
            for adapter in adapters:
                ip: ifaddr.IP
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


def find_appliances_on_lan(
    cloud: MideaCloud,
    broadcast_retries: int,
    appliances_from_cloud: list,
    broadcast_timeout: float,
    broadcast_networks: list[str] | None,
    appliances: list[LanDevice],
):

    discovery = MideaDiscovery(
        cloud=cloud,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )
    _LOGGER.debug("Starting LAN discovery")
    appliances_count = sum(
        Appliance.supported(a["type"]) for a in appliances_from_cloud
    )
    for i in range(broadcast_retries):
        _LOGGER.debug(
            "Broadcast attempt %d of max %d",
            i + 1,
            broadcast_retries,
        )

        scanned_appliances = list(discovery.collect_appliances())
        scanned_appliances.sort(key=lambda x: x.id)
        for scanned in scanned_appliances:
            for a in appliances:
                if str(a.id) == str(scanned.id):
                    _LOGGER.debug("Known appliance %s", scanned.id)
                    if a.ip != scanned.ip:
                        # Already known
                        a.update(scanned)
                    break

            for d in appliances_from_cloud:
                if d["id"] == str(scanned.id):
                    scanned.state.update_info(d)
                    appliances.append(scanned)
                    _LOGGER.info(
                        "Found appliance name=%s id=%s, ip=%s:%d",
                        scanned.state.name,
                        scanned.id,
                        scanned.ip,
                        scanned.port,
                    )
                    break
            else:
                _LOGGER.warning(
                    (
                        "Found an appliance that is"
                        " not registered to account:"
                        " id=%s, ip=%s, type=%s"
                    ),
                    scanned.id,
                    scanned.ip,
                    scanned.type,
                )
        if len(appliances) >= appliances_count:
            _LOGGER.info(
                "Found %d of %d appliance(s)",
                len(appliances),
                appliances_count,
            )
            break
    else:
        _LOGGER.warning(
            (
                "Some appliance(s) where not discovered on local LAN:"
                " %d discovered out of %d"
            ),
            len(appliances),
            appliances_count,
        )
        for d in appliances_from_cloud:
            if Appliance.supported(d["type"]):
                for a in appliances:
                    if d["id"] == str(a.id):
                        appliance = a
                        break
                else:
                    appliance = LanDevice(
                        id=d["id"], appliance_type=d["type"]
                    )
                    appliances.append(appliance)
                _LOGGER.warning(
                    (
                        "Unable to discover registered appliance"
                        " name=%s id=%s, type=%s"
                    ),
                    d["name"],
                    d["id"],
                    d["type"],
                )
                appliance.state.update_info(d)


def find_appliances(
    appkey=None,
    account=None,
    password=None,
    cloud=None,
    broadcast_retries: int = 2,
    broadcast_timeout: int = 3,
    broadcast_networks=None,
) -> list[LanDevice]:
    if cloud is None:
        cloud = MideaCloud(appkey=appkey, account=account, password=password)
        cloud.authenticate()
    appliances_from_cloud = cloud.list_appliances()

    appliances: list[LanDevice] = []

    _LOGGER.debug("Scanning for midea dehumidifier appliances")
    find_appliances_on_lan(
        appliances=appliances,
        appliances_from_cloud=appliances_from_cloud,
        cloud=cloud,
        broadcast_retries=broadcast_retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )

    return appliances
