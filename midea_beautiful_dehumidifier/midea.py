""" Midea constants """
from __future__ import annotations

from typing import Final

MSGTYPE_HANDSHAKE_REQUEST: Final = 0x0
MSGTYPE_HANDSHAKE_RESPONSE: Final = 0x1
MSGTYPE_ENCRYPTED_RESPONSE: Final = 0x3
MSGTYPE_ENCRYPTED_REQUEST: Final = 0x6
MSGTYPE_TRANSPARENT: Final = 0xF

DEFAULT_APPKEY: Final = "3742e9e5842d4ad59c2db887e12449f9"
DEFAULT_SIGNKEY: Final = "xhdiwjnchekd4d512chdjx5d8e4c394D2D7S"

DISCOVERY_PORT: Final = 6445

CLOUD_API_SERVER_URL: Final = "https://mapp.appsmb.com/v1/"