"""Utility services for Midea library."""
from __future__ import annotations

from typing import Final

SPAM: Final = 1
TRACE: Final = 5


HDR_8370: Final = b"\x83\x70"
HDR_ZZ: Final = b"\x5a\x5a"


def strtobool(val) -> bool:
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = str(val).lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    if val in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"invalid truth value ${val!r}")
