"""Utility services for Midea library."""
from __future__ import annotations


class _Hex:
    """Helper class used to display bytes array as hexadecimal string"""

    def __init__(self, data: bytes | bytearray | None) -> None:
        self.data = data

    def __str__(self) -> str:
        return self.data.hex() if self.data else "None"
