""" Library for local network access to Midea dehumidifier appliances """
from __future__ import annotations

import logging

from midea_beautiful.cloud import MideaCloud
from midea_beautiful.lan import LanDevice, appliance_state
from midea_beautiful.midea import (
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    DEFAULT_RETRIES,
    DEFAULT_TIMEOUT,
)
from midea_beautiful.scanner import do_find_appliances
import midea_beautiful.version as version

__all__ = (
    "appliance_state",
    "connect_to_cloud",
    "find_appliances",
    "LanDevice",
    "MideaCloud",
)

__version__ = version.__version__


_LOGGER = logging.getLogger(__name__)


def connect_to_cloud(
    account: str, password: str, appkey=DEFAULT_APPKEY, appid=DEFAULT_APP_ID
) -> MideaCloud:
    """Connects to Midea cloud API

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


def find_appliances(  # pylint: disable=too-many-arguments
    cloud: MideaCloud | None = None,
    appkey: str | None = None,
    account: str = None,
    password: str = None,
    appid: str = None,
    addresses: list[str] = None,
    appliances: list[LanDevice] = None,
    retries: int = DEFAULT_RETRIES,
    timeout: float = DEFAULT_TIMEOUT,
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
    if not cloud and account and password:
        cloud = connect_to_cloud(account, password, appkey, appid)

    addresses = addresses or ["255.255.255.255"]
    _LOGGER.debug("Scanning for midea dehumidifier appliances via %s", addresses)
    return do_find_appliances(
        cloud, addresses, appliances, max_retries=retries, timeout=timeout
    )
