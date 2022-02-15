"""Midea constants"""
from __future__ import annotations

from typing import Final

MSGTYPE_HANDSHAKE_REQUEST: Final = 0x0
MSGTYPE_HANDSHAKE_RESPONSE: Final = 0x1
MSGTYPE_ENCRYPTED_RESPONSE: Final = 0x3
MSGTYPE_ENCRYPTED_REQUEST: Final = 0x6
MSGTYPE_TRANSPARENT: Final = 0xF

DISCOVERY_PORT: Final = 6445

CLOUD_API_SERVER_URL: Final = "https://mapp.appsmb.com/v1/"

SUPPORTED_APPS: Final = {
    "NetHome Plus": {"appkey": "3742e9e5842d4ad59c2db887e12449f9", "appid": 1017},
    "Midea Air": {"appkey": "ff0cf6f5f0c3471de36341cab3f7a9af", "appid": 1117},
    "MSmartHome": {"appkey": "ac21b9f9cbfe4ca5a88562ef25e2b768", "appid": 1010},
}

# spell-checker: disable
# pylint: disable=unsubscriptable-object
# spell-checker: enable
DEFAULT_APP = "NetHome Plus"
DEFAULT_APPKEY: Final[str] = SUPPORTED_APPS[DEFAULT_APP]["appkey"]
DEFAULT_APP_ID: Final[int] = SUPPORTED_APPS[DEFAULT_APP]["appid"]
# spell-checker: disable
# pylint: enable=unsubscriptable-object
# spell-checker: enable


DEFAULT_RETRIES: Final = 3
DEFAULT_TIMEOUT: Final = 3

ERROR_CODE_P2: Final = 38
ERROR_CODE_BUCKET_FULL: Final = ERROR_CODE_P2
ERROR_CODE_BUCKET_REMOVED: Final = 37

APPLIANCE_TYPE_DEHUMIDIFIER: Final = "0xa1"
APPLIANCE_TYPE_AIRCON: Final = "0xac"

AC_MIN_TEMPERATURE: Final = 16
AC_MAX_TEMPERATURE: Final = 31
