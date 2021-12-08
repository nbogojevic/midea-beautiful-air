""" Helpers for Midea Dehumidifier """
from __future__ import annotations

import logging


_LOGGER = logging.getLogger(__name__)


def hex4log(data: bytes | bytearray, logger: logging.Logger = _LOGGER, level=logging.DEBUG) -> str:
    """
    Outputs bytearray as hex if logging.DEBUG level is enabled.
    """
    if not logger.isEnabledFor(level):
        return ""
    return data.hex()

