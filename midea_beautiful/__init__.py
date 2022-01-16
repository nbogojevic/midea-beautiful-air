""" Library for local network access to Midea dehumidifier appliances """
from __future__ import annotations
import logging
from midea_beautiful.crypto import Security

import midea_beautiful.version as version
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import LanDevice, get_appliance_state
from midea_beautiful.midea import (
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    DEFAULT_RETRIES,
)
from midea_beautiful.scanner import do_find_appliances

# pylint: disable=too-many-arguments

__version__ = version.__version__


_LOGGER = logging.getLogger(__name__)


def connect_to_cloud(
    account: str, password: str, appkey=DEFAULT_APPKEY, appid=DEFAULT_APP_ID
) -> MideaCloud:
    """
    Connects to Midea cloud API

    Args:
        appkey (str): Midea app key
        account (str): Midea app user e-mail
        password (str): Midea app password
        appid (str): Midea app id

    Returns:
        MideaCloud: Interface to Midea cloud API
    """
    cloud = MideaCloud(appkey=appkey, account=account, password=password, appid=appid)
    cloud.authenticate()
    return cloud


def find_appliances(
    cloud: MideaCloud | None = None,
    appkey: str | None = None,
    account: str = None,
    password: str = None,
    appid: str = None,
    addresses: list[str] = None,
    appliances: list[LanDevice] = None,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_RETRIES,
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
        retries (int): Number of times library should retry discovery.
        timeout (float): Time to wait for device reply.

    Returns:
        list[LanDevice]: [description]
    """
    _LOGGER.debug("Library version=%s", __version__)
    addresses = addresses or ["255.255.255.255"]
    if not cloud and account and password:
        cloud = MideaCloud(
            appkey=appkey, account=account, password=password, appid=appid
        )
        cloud.authenticate()

    _LOGGER.debug("Scanning for midea dehumidifier appliances via %s", addresses)
    return do_find_appliances(
        cloud, addresses, appliances, max_retries=retries, timeout=timeout
    )


def appliance_state(
    address: str | None = None,
    token: str = None,
    key: str = None,
    cloud: MideaCloud = None,
    use_cloud: bool = False,
    appliance_id: str | None = None,
    appliance_type: str = APPLIANCE_TYPE_DEHUMIDIFIER,
    security: Security = None,
) -> LanDevice:
    """Gets the current state of an appliance

    Args:
        address (str, optional): IPv4 address of the appliance. Defaults to None.
        token (str, optional): Token used for appliance. Defaults to None.
        key (str, optional): Key used for appliance. Defaults to None.
        cloud (MideaCloud, optional): An instance of cloud client. Defaults to None.
        use_cloud (bool, optional): True if state should be retrieved from cloud.
        Defaults to False.
        appliance_id (str, optional): Id of the appliance as stored in Midea API.
        Defaults to None.
        appliance_type (str, optional): Type of the appliance.
        Defaults to APPLIANCE_TYPE_DEHUMIDIFIER.
        security (Security, optional): Security object. If None, a new one is allocated.
        Defaults to None.

    Raises:
        MideaNetworkError: [description]
        MideaNetworkError: [description]
        MideaError: [description]
        MideaError: [description]

    Returns:
        LanDevice: [description]
    """
    return get_appliance_state(
        address=address,
        token=token,
        key=key,
        cloud=cloud,
        use_cloud=use_cloud,
        appliance_id=appliance_id,
        appliance_type=appliance_type,
        security=security,
    )
