"""Exceptions raised by library"""
from __future__ import annotations


class MideaError(Exception):
    """Base exception for all library specific exceptions"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def __str__(self) -> str:
        return self.message


class MideaNetworkError(MideaError):
    """Network problem"""


class ProtocolError(MideaError):
    """Problem while parsing payloads"""


class UnsupportedError(MideaError):
    """Unsupported appliance or protocol version"""


class AuthenticationError(MideaError):
    """Problem while authenticating"""


class CloudError(MideaError):
    """Problem while working with cloud API"""

    def __init__(self, error_code: int, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        return f"Midea cloud API error: {self.message} ({self.error_code})"


class CloudRequestError(MideaError):
    """Problem while communicating with cloud API"""


class RetryLaterError(MideaError):
    """Too many calls to cloud API. Try later."""

    def __init__(self, error_code, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        return f"Retry later: {self.message} ({self.error_code})"


class CloudAuthenticationError(MideaError):
    """Problem while authenticating with cloud API"""

    def __init__(self, error_code, message: str, account: str) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.account = account

    def __str__(self) -> str:
        return (
            f"Cloud authentication error:"
            f" {self.message} ({self.error_code})"
        )
