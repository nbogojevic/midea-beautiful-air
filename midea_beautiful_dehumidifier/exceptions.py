from __future__ import annotations


class MideaError(Exception):
    pass


class ProtocolError(MideaError):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"ProtocolException {self.message}"


class AuthenticationError(MideaError):
    def __init__(self, message: str):
        self.message = message

    def __str__(self):
        return f"AuthenticationError {self.message}"


class CloudError(MideaError):
    def __init__(self, error_code, message: str):
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"CloudError {self.error_code} {self.message}"


class CloudRequestError(MideaError):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def __str__(self):
        return f"CloudRequestError {self.endpoint}"


class RetryLaterError(MideaError):
    def __init__(self, error_code, message: str):
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"RetryLaterError {self.error_code} {self.message}"


class CloudAuthenticationError(MideaError):
    def __init__(self, error_code, message: str):
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"CloudAuthenticationError {self.error_code} {self.message}"
