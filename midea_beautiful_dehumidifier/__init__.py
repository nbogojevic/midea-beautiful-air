from __future__ import annotations

from midea_beautiful_dehumidifier.__version__ import __version__
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.lan import get_appliance_state
from midea_beautiful_dehumidifier.scanner import find_appliances

__version__ = __version__


def discover_appliances(
    appkey=None,
    account=None,
    password=None,
    cloud: MideaCloud | None = None,
    broadcast_retries=2,
    broadcast_timeout=3,
    broadcast_networks=None,
):
    return find_appliances(
        appkey=appkey,
        account=account,
        password=password,
        cloud=cloud,
        broadcast_retries=broadcast_retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )


def appliance_state(ip, token=None, key=None, cloud: MideaCloud = None):
    return get_appliance_state(ip, token=token, key=key, cloud=cloud)


def connect_to_cloud(appkey, account, password) -> MideaCloud:
    cloud = MideaCloud(appkey, account, password)
    cloud.authenticate()
    return cloud
