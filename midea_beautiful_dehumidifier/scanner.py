from __future__ import annotations

import logging
import socket
from ipaddress import IPv4Network

import ifaddr

from midea_beautiful_dehumidifier.cloud import CloudService
from midea_beautiful_dehumidifier.appliance import is_supported_appliance
from midea_beautiful_dehumidifier.lan import BROADCAST_MSG, LanDevice
from midea_beautiful_dehumidifier.util import hex4log

_LOGGER = logging.getLogger(__name__)


class MideaDiscovery:
    def __init__(
        self,
        cloud: CloudService,
        broadcast_retries: int,
        broadcast_timeout: float,
        broadcast_networks: list[str] | None,
    ):
        self._cloud = cloud
        self._broadcast_retries = broadcast_retries
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.settimeout(broadcast_timeout)
        self.result = set()
        self.found_appliances = set()
        self.networks = broadcast_networks

    def collect_appliances(self) -> list[LanDevice]:
        """Find all appliances on the local network."""

        for i in range(self._broadcast_retries):
            _LOGGER.debug(
                "Broadcasting message %d of %d",
                i + 1,
                self._broadcast_retries,
            )
            self._broadcast_message()
            scanned_appliances: set[LanDevice] = set()
            try:
                while True:
                    data, addr = self.socket.recvfrom(512)
                    ip = addr[0]
                    if ip not in self.found_appliances:
                        _LOGGER.debug(
                            "Reply from %s payload=%s",
                            ip,
                            hex4log(data, _LOGGER),
                        )
                        self.found_appliances.add(ip)
                        appliance = LanDevice(discovery_data=data)
                        if appliance.version == 0:
                            _LOGGER.error(
                                "Unable to load data from appliance %s.", ip
                            )
                            continue
                        scanned_appliances.add(appliance)

            except socket.timeout:
                _LOGGER.debug("Finished broadcast collection")
            for sd in scanned_appliances:
                if sd.identify_appliance(self._cloud):
                    self.result.add(sd)

        return list(self.result)

    def _broadcast_message(self):
        for broadcast_address in self._get_networks():
            try:
                self.socket.sendto(BROADCAST_MSG, (broadcast_address, 6445))
                self.socket.sendto(BROADCAST_MSG, (broadcast_address, 20086))
            except Exception:
                _LOGGER.debug(
                    "Unable to send broadcast to: %s", broadcast_address
                )

    def _get_networks(self) -> list[str]:
        if self.networks is None:
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
            self.networks = list()
            if not nets:
                _LOGGER.error("No valid networks detected to send broadcast")
            else:
                for net in nets:
                    _LOGGER.debug(
                        "Network %s, broadcast address %s",
                        net.network_address,
                        net.broadcast_address,
                    )
                    self.networks.append(str(net.broadcast_address))
        return self.networks


def find_appliances_on_lan(
    cloud_service: CloudService,
    broadcast_retries: int,
    appliances_from_cloud: list,
    broadcast_timeout: float,
    broadcast_networks: list[str] | None,
    appliances: list[LanDevice],
):

    discovery = MideaDiscovery(
        cloud=cloud_service,
        broadcast_retries=broadcast_retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )
    _LOGGER.debug("Starting LAN discovery")

    scanned_appliances = list(discovery.collect_appliances())
    scanned_appliances.sort(key=lambda x: x.id)
    for scanned in scanned_appliances:
        if any(True for d in appliances if str(d.id) == str(scanned.id)):
            _LOGGER.debug("Known appliance %s", scanned.id)
            # TODO update appliance config if needed
            continue

        appliance = next(
            filter(
                lambda a: a["id"] == str(scanned.id), appliances_from_cloud
            ),
            None,
        )
        if appliance and scanned.state is not None:
            scanned.state.set_appliance_detail(appliance)
            scanned.refresh()
            appliances.append(scanned)
            _LOGGER.info(
                "Found dehumidifier id=%s, ip=%s:%d",
                scanned.id,
                scanned.ip,
                scanned.port,
            )
        else:
            _LOGGER.warning(
                (
                    "Found an appliance that is not registered to account:"
                    " id=%s, ip=%s, type=%s"
                ),
                scanned.id,
                scanned.ip,
                scanned.type,
            )


def find_appliances(
    app_key=None,
    account=None,
    password=None,
    cloud_service=None,
    broadcast_retries: int = 2,
    broadcast_timeout: int = 3,
    broadcast_networks=None,
) -> list[LanDevice]:
    if cloud_service is None:
        cloud_service = CloudService(
            app_key=app_key, account=account, password=password
        )
        cloud_service.authenticate()
    appliances_from_cloud = cloud_service.list_appliances()
    appliances_count = sum(
        is_supported_appliance(a["type"]) for a in appliances_from_cloud
    )
    _LOGGER.info(
        "Account has %d supported appliance(s) out of %d appliance(s)",
        appliances_count,
        len(appliances_from_cloud),
    )

    appliances: list[LanDevice] = []

    _LOGGER.debug("Scanning for midea dehumidifier appliances")
    find_appliances_on_lan(
        appliances=appliances,
        appliances_from_cloud=appliances_from_cloud,
        cloud_service=cloud_service,
        broadcast_retries=broadcast_retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )
    if len(appliances) >= appliances_count:
        _LOGGER.info(
            "Found %d of %d appliance(s)",
            len(appliances),
            appliances_count,
        )
    else:
        _LOGGER.warning(
            (
                "Some appliance(s) where not discovered on local LAN:"
                " %d discovered out of %d"
            ),
            len(appliances),
            appliances_count,
        )

        for c in appliances_from_cloud:
            if not any(True for d in appliances if str(d.id) == str(c["id"])):
                _LOGGER.warning(
                    "Unable to find appliance id=%s, type=%s",
                    c["id"],
                    c["type"],
                )
                if is_supported_appliance(c["type"]):
                    _LOGGER.info(
                        "Adding placeholder for appliance id=%s", c["id"]
                    )
                    appliances.append(
                        LanDevice(id=c["id"], device_type=c["type"])
                    )

    return appliances
