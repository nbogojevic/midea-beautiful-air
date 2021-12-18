from __future__ import annotations

from midea_beautiful_dehumidifier.__version__ import __version__
from midea_beautiful_dehumidifier.cloud import MideaCloud
from midea_beautiful_dehumidifier.midea import DEFAULT_APP_ID, DEFAULT_APPKEY
from midea_beautiful_dehumidifier.lan import get_appliance_state
from midea_beautiful_dehumidifier.scanner import find_appliances

__version__ = __version__


def discover_appliances(
    appkey=DEFAULT_APPKEY,
    account=None,
    password=None,
    appid=DEFAULT_APP_ID,
    cloud: MideaCloud | None = None,
    broadcast_retries=2,
    broadcast_timeout=3,
    broadcast_networks=None,
):
    """
    Discovers appliances on local network

    Args:
        appkey (str, optional): Midea cloud application key. If not
            provided, cloud interface must be provided and will
            be used to discover appliance information and token.
            Defaults to None.
        account (str, optional): Midea cloud user e-mail. If not
            provided, cloud interface must be provided and will
            be used to discover appliance information and token.
            Defaults to None.
        password (str, optional): Midea cloud password. If not
            provided, cloud interface must be provided and will
            be used to discover appliance information and token.
            Defaults to None.
        cloud (MideaCloud, optional): Interface to Midea cloud.
            Used when credentials were not provided. Defaults to None.
        broadcast_retries (int, optional): Number of retries for UDP
            broadcast. Defaults to 2.
        broadcast_timeout (int, optional): Timeout in seconds for waiting
            for reply on UDP broadcast. Defaults to 3.
        broadcast_networks (list[str], optional): List of network broadcast
            addresses. When not provided, all network interfaces are used.
            Defaults to None.

    Returns:
        list[LanDevice]: List of appliances. Appliances that
            are found on Midea cloud, but are not discovered will
            have IP address set to None.
    """
    return find_appliances(
        appkey=appkey,
        account=account,
        password=password,
        appid=appid,
        cloud=cloud,
        broadcast_retries=broadcast_retries,
        broadcast_timeout=broadcast_timeout,
        broadcast_networks=broadcast_networks,
    )


def appliance_state(ip, token=None, key=None, cloud: MideaCloud = None):
    """
    Retrieves appliance state

    Args:
        ip (str): IP address of the appliance
        token (str, optional): Token used to connect to
            appliance on local network. If not provided, cloud
            interface must be provided and will be used
            to discover token. Defaults to None.
        key (str, optional): Key for token. If not provided, cloud
            interface must be provided and will be used
            to discover token. Defaults to None.
        cloud (MideaCloud, optional): Interface to Midea cloud.
            Used to discover token if it was not provided in arguments.
            Defaults to None.

    Returns:
        LanDevice: Appliance descriptor and state
    """
    return get_appliance_state(ip, token=token, key=key, cloud=cloud)


def connect_to_cloud(
    account, password, appkey=DEFAULT_APPKEY, appid=DEFAULT_APP_ID
) -> MideaCloud:
    """
    Connects to Midea cloud

    Args:
        appkey (str): Midea cloud API application key
        account (str): Midea cloud user e-mail
        password (str): Midea cloud password
        appid (str): Midea cloud API application id

    Returns:
        MideaCloud: Interface to Midea cloud API
    """
    cloud = MideaCloud(appkey, account, password, appid)
    cloud.authenticate()
    return cloud
