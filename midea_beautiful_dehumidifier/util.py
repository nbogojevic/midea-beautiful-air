""" Helpers for Midea Dehumidifier """
from __future__ import annotations

import logging


def hex4log(
    data: bytes,
    logger: logging.Logger,
    level: int = logging.DEBUG,
) -> str:
    """
    Outputs bytes or byte array as hex if logging.DEBUG level is enabled.
    """
    return data.hex() if logger.isEnabledFor(level) else ""
