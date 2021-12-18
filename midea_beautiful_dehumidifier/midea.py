""" Midea constants """
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
    "NetHome": {"appkey": "3742e9e5842d4ad59c2db887e12449f9", "appid": 1017},
    "MideaAir": {"appkey": "ff0cf6f5f0c3471de36341cab3f7a9af", "appid": 1117},
}

DEFAULT_APPKEY: Final = SUPPORTED_APPS["NetHome"]["appkey"]
DEFAULT_APP_ID: Final = SUPPORTED_APPS["NetHome"]["appid"]
DEFAULT_SIGNKEY: Final = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S"
