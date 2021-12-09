from __future__ import annotations

from midea_beautiful_dehumidifier.scanner import find_appliances
from midea_beautiful_dehumidifier.lan import get_appliance_state


def discover_appliances(
    app_key,
    account,
    password,
    broadcast_retries=2,
    retries=4,
    broadcast_timeout=3,
    broadcast_networks=None,
):
    return find_appliances(
        app_key,
        account,
        password,
        broadcast_retries=broadcast_retries,
        retries=retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )


def appliance_state(ip, port, token=None, key=None):
    return get_appliance_state(ip, port, token=token, key=key)
