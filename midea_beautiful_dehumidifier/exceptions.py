from __future__ import annotations


class MideaError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return self.message


class MideaNetworkError(MideaError):
    pass


class ProtocolError(MideaError):
    pass


class UnsupportedError(MideaError):
    pass


class AuthenticationError(MideaError):
    pass


class CloudError(MideaError):
    def __init__(self, error_code: int, message: str) -> None:
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        return f"Midea cloud API error {self.error_code} {self.message}"


class CloudRequestError(MideaError):
    pass


class RetryLaterError(MideaError):
    def __init__(self, error_code, message: str) -> None:
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        return f"Retry later {self.error_code} {self.message}"


class CloudAuthenticationError(MideaError):
    def __init__(self, error_code, message: str) -> None:
        self.error_code = error_code
        self.message = message

    def __str__(self) -> str:
        return f"Authentication {self.error_code} {self.message}"
