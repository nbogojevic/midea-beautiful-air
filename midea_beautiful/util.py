"""Utility services for Midea library."""
from __future__ import annotations
import logging

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
        return to_redact

    to_redact = str(to_redact)
    if length < 0:
        length = int(len(to_redact) / (-length))
    if length == 0 or length >= len(to_redact):
        return char * len(to_redact)
    else:
        return to_redact[:-length] + char * length


class Redacted:
    redacting: bool = False

    def __init__(self, to_redact: str) -> None:
        self.to_redact = to_redact

    def __str__(self) -> str:
        if Redacted.redacting:
            return redact(self.to_redact)
        return self.to_redact


class RedactingFilter(logging.Filter):

    def __init__(self):
        super(RedactingFilter, self).__init__()
        self._patterns = set()

    def add_redact(self, sensitive):
        if sensitive:
            self._patterns.add(sensitive)

    def filter(self, record):
        record.msg = self._redact(record.msg)
        if isinstance(record.args, dict):
            for k in record.args.keys():
                record.args[k] = self._redact(record.args[k])
        else:
            record.args = tuple(self._redact(arg) for arg in record.args)
        return True

    def _redact(self, msg):
        msg = isinstance(msg, str) and msg or str(msg)
        for pattern in self._patterns:
            msg = msg.replace(pattern, "<<TOP SECRET!>>")
        return msg


class Log:
    redactors: list[RedactingFormatter] = []
    initialized: bool = False


def sensitive(value: str, replace: str = None, **kwargs):
    if replace is None:
        replace = redact(value, **kwargs)
    for redactor in Log.redactors:
        redactor.add_redact(value, replace)


def init_logging():
    if not Log.initialized:
        Log.initialized = True
        logger = logging.getLogger("midea_beautiful")
        while logger and not logger.handlers:
            logger = logger.parent
        if logger:
            for h in logger.handlers:
                fmt = RedactingFormatter(h.formatter)
                Log.redactors.append(fmt)
                h.setFormatter(fmt)


class RedactingFormatter(object):
    _patterns: dict[str, str] = {}

    def __init__(self, orig_formatter):
        self.orig_formatter = orig_formatter

    def __getattr__(self, attr):
        return getattr(self.orig_formatter, attr)

    def format(self, record):
        msg = self.orig_formatter.format(record)
        for pattern, replace in self._patterns.items():
            msg = msg.replace(pattern, replace)
        return msg

    def add_redact(self, sensitive, replace):
        if sensitive:
            self._patterns[sensitive] = replace
