from __future__ import annotations


class Exception(Exception):
    pass


class ProtocolException(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"ProtocolException {self.message}"


class AuthenticationError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return f"AuthenticationError {self.message}"


class CloudError(Exception):
    def __init__(self, error_code, message):
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"CloudError {self.error_code} {self.message}"


class CloudRequestError(Exception):
    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def __str__(self):
        return f"CloudRequestError {self.endpoint}"


class RetryLaterError(Exception):
    def __init__(self, error_code, message):
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"RetryLaterError {self.error_code} {self.message}"


class CloudAuthenticationError(Exception):
    def __init__(self, error_code, message):
        self.error_code = error_code
        self.message = message

    def __str__(self):
        return f"CloudAuthenticationError {self.error_code} {self.message}"
