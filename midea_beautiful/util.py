"""Utility services for Midea library."""
from __future__ import annotations


class _Hex:
    """Helper class used to display bytes array as hexadecimal string"""

    def __init__(self, data: bytes | bytearray | None) -> None:
        self.data = data

    def __str__(self) -> str:
        return self.data.hex() if self.data else "None"


def strtobool(val) -> bool:
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = str(val).lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    elif val in ("n", "no", "f", "false", "off", "0"):
        return False
    else:
        raise ValueError(f"invalid truth value ${val!r}")
