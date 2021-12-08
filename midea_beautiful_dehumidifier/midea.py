""" Midea constants and interfaces """
from __future__ import annotations

from typing import Final

MSGTYPE_HANDSHAKE_REQUEST: Final = 0x0
MSGTYPE_HANDSHAKE_RESPONSE: Final = 0x1
MSGTYPE_ENCRYPTED_RESPONSE: Final = 0x3
MSGTYPE_ENCRYPTED_REQUEST: Final = 0x6
MSGTYPE_TRANSPARENT: Final = 0xf


class MideaCommand:
    """ Base command interface """

    def finalize(self):
        pass


