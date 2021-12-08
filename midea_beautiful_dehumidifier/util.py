""" Helpers for Midea Dehumidifier """
from __future__ import annotations

import datetime
import logging
from hashlib import sha256
from typing import Final


_LOGGER = logging.getLogger(__name__)

MSGTYPE_HANDSHAKE_REQUEST: Final = 0x0
MSGTYPE_HANDSHAKE_RESPONSE: Final = 0x1
MSGTYPE_ENCRYPTED_RESPONSE: Final = 0x3
MSGTYPE_ENCRYPTED_REQUEST: Final = 0x6
MSGTYPE_TRANSPARENT: Final = 0xf


def hex4logging(data: bytes | bytearray, logger: logging.Logger = _LOGGER, level=logging.DEBUG) -> str:
    """
    Outputs bytearray as hex if logging.DEBUG level is enabled.
    """
    if not logger.isEnabledFor(level):
        return ""
    return data.hex()


def packet_time() -> bytearray:
    t = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:16]
    b = bytearray()
    for i in range(0, len(t), 2):
        d = int(t[i:i+2])
        b.insert(0, d)
    return b


def get_udpid(data):
    b = sha256(data).digest()
    b1, b2 = b[:16], b[16:]
    b3 = bytearray(16)
    i = 0
    while i < len(b1):
        b3[i] = b1[i] ^ b2[i]
        i += 1
    return b3.hex()




class MideaCommand:
    """ Base command interface """

    def finalize(self):
        pass


class MideaService:
    """ Base class for cloud and lan service"""

    def status(self,
               cmd: MideaCommand,
               id: str | int = None, protocol: int = None) -> list[bytearray]:
        """ Retrieves appliance status """

        return []

    def apply(self,
              cmd: MideaCommand,
              id: str | int = None, protocol: int = None) -> bytearray:
        """ Applies settings to appliance """

        return bytearray()

    def authenticate(self, args) -> bool:
        return False

    def target(self) -> str:
        return "None"




