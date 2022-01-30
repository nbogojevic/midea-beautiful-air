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


def redact(to_redact: str, length: int = 0, char: str = "*") -> str:
    """Redacts/obfuscates the passed string."""
    if not to_redact or not isinstance(to_redact, str):
        return str(to_redact)

    to_redact = str(to_redact)
    if length < 0:
        length = int(len(to_redact) / (-length))
    if length == 0 or length >= len(to_redact):
        return char * len(to_redact)
    else:
        return to_redact[:-length] + char * length


class Redacted:
    redacting: bool = True

    def __init__(self, to_redact: str, length: int = 0, char: str = "*") -> None:
        self.to_redact = to_redact
        self.length = length
        self.char = char

    def __str__(self) -> str:
        if Redacted.redacting:
            return redact(self.to_redact, self.length, self.char)

        return str(self.to_redact)
