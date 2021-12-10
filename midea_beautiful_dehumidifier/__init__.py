from __future__ import annotations

from midea_beautiful_dehumidifier.__version__ import __version__
from midea_beautiful_dehumidifier.cloud import CloudService
from midea_beautiful_dehumidifier.lan import get_appliance_state
from midea_beautiful_dehumidifier.scanner import find_appliances

__version__ = __version__


def discover_appliances(
    app_key=None,
    account=None,
    password=None,
    cloud_service: CloudService | None = None,
    broadcast_retries=2,
    broadcast_timeout=3,
    broadcast_networks=None,
):
    return find_appliances(
        app_key=app_key,
        account=account,
        password=password,
        cloud_service=cloud_service,
        broadcast_retries=broadcast_retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )


def appliance_state(
    ip, port=6445, token=None, key=None, cloud_service: CloudService = None
):
    return get_appliance_state(
        ip, port=port, token=token, key=key, cloud_service=cloud_service
    )


def connect_to_cloud(app_key, account, password) -> CloudService | None:
    cloud = CloudService(
        app_key,
        account,
        password,
    )
    cloud.authenticate()
    return cloud
