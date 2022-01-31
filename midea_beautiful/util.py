"""Utility services for Midea library."""
from __future__ import annotations

from typing import Any, Final, Mapping

HDR_8370: Final = b"\x83\x70"
HDR_ZZ: Final = b"\x5a\x5a"
_MAX_LEN: Final = 1024


_very_verbose: bool = False


def is_very_verbose() -> bool:
    global _very_verbose
    return _very_verbose


def very_verbose(verbose: bool) -> None:
    global _very_verbose
    _very_verbose = verbose


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


def redact(to_redact: str, length: int = _MAX_LEN, char: str = "*") -> str:
    """Redacts/obfuscates the passed string."""
    if not to_redact or not isinstance(to_redact, str):
        return _SensitiveStrings.clean(str(to_redact))

    to_redact = str(to_redact)
    if length < 0:
        length = int(len(to_redact) / (-length))
    if length >= len(to_redact):
        return char * len(to_redact)
    if length == 0:
        return _SensitiveStrings.clean(to_redact)
    else:
        return _SensitiveStrings.clean(to_redact[:-length] + char * length)


class _SensitiveStrings:
    """Collection of strings that should be removed from logs."""

    sensitives: dict[str, dict] = {}

    @staticmethod
    def add(sensitive: str, rules: dict) -> None:
        _SensitiveStrings.sensitives[sensitive] = redact(sensitive, **rules)

    @staticmethod
    def clean(value: str) -> None:
        cleaned = str(value)
        for sensitive, replace in _SensitiveStrings.sensitives.items():
            cleaned = cleaned.replace(sensitive, replace)
        return cleaned


def sensitive(sensitive: str, rules: dict = {}) -> None:
    """Add sensitive string to the list. Apply passed rules to redaction method."""
    _SensitiveStrings.add(sensitive, rules)


def clear_sensitive() -> None:
    """Clears all sensitive rules."""
    _SensitiveStrings.sensitives.clear()


class Redacted:
    """Wrapper for redacted basic data."""

    redacting: bool = True

    def __init__(
        self,
        to_redact: Any,
        length: int = _MAX_LEN,
        char: str = "*",
        keys: dict[str, dict] = {},
    ) -> None:
        self.to_redact = to_redact
        self.length = length
        self.char = char
        self.keys = keys

    def __str__(self) -> str:
        if Redacted.redacting:
            if isinstance(self.to_redact, str):
                return redact(self.to_redact, self.length, self.char)
            if isinstance(self.to_redact, Mapping):
                new = {**self.to_redact}
                for key, kwargs in self.keys.items():
                    if key in new:
                        new[key] = redact(new[key], **kwargs)
                return str(new)
            if isinstance(self.to_redact, list):
                new_list = []
                for item in self.to_redact:
                    new = {**item}
                    new_list.append(new)
                    for key, kwargs in self.keys.items():
                        if key in new:
                            new[key] = redact(new[key], **kwargs)
                return str(new_list)
            converted = str(self.to_redact)
            return _SensitiveStrings.clean(converted)

        return str(self.to_redact)
