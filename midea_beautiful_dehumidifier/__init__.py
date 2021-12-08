from __future__ import annotations

import logging

from midea_beautiful_dehumidifier.cloud import Cloud
from midea_beautiful_dehumidifier.device import DehumidifierDevice, is_supported_device
from midea_beautiful_dehumidifier.scanner import find_devices_on_lan

__version__ = '0.1.40'

_LOGGER = logging.getLogger(__name__)

def find_devices(app_key, account, password, broadcast_retries=2, retries=4, broadcast_timeout=3, broadcast_networks=None):
    cloud_service = Cloud(app_key=app_key, account=account, password=password)
    cloud_service.authenticate()
    appliances = cloud_service.list_appliances()
    appliances_count = sum(is_supported_device(a["type"]) for a in appliances)
    _LOGGER.info("Account has %d supported device(s) out of %d appliance(s)",
                 appliances_count, len(appliances))

    devices: list[DehumidifierDevice] = []

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