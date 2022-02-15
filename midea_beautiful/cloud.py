"""Interface to Midea cloud API."""
from __future__ import annotations

from datetime import datetime
import json
import logging
from threading import RLock
from time import sleep
from typing import Any, Final, Tuple

import requests
from requests.exceptions import RequestException

from midea_beautiful.crypto import Security
from midea_beautiful.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    CloudError,
    CloudRequestError,
    MideaError,
    ProtocolError,
    RetryLaterError,
)
from midea_beautiful.midea import CLOUD_API_SERVER_URL, DEFAULT_APP_ID, DEFAULT_APPKEY
from midea_beautiful.util import Redacted, sensitive

# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments

_LOGGER = logging.getLogger(__name__)


CLOUD_API_CLIENT_TYPE: Final = 1  # Android
CLOUD_API_FORMAT: Final = 2  # JSON
CLOUD_API_LANGUAGE: Final = "en_US"
CLOUD_API_SRC: Final = 17

PROTECTED_REQUESTS: Final = ["user/login/id/get", "user/login"]
PROTECTED_RESPONSES: Final = ["iot/secure/getToken", "user/login/id/get", "user/login"]

_MAX_RETRIES: Final = 3
_DEFAULT_CLOUD_TIMEOUT: Final = 9
_REDACTED_KEYS: Final = {"id": {"length": 4}, "sn": {"length": 8}}
_REDACTED_REQUEST: Final = {"sessionId": {}}


def _encode_as_csv(data: bytes | bytearray) -> str:
    normalized = []
    for byt in data:
        if byt >= 128:
            byt = byt - 256
        normalized.append(str(byt))

    string = ",".join(normalized)
    return string


def _decode_from_csv(data: str) -> bytes:
    int_data = [int(a) for a in data.split(",")]
    for i, value in enumerate(int_data):
        if value < 0:
            int_data[i] = value + 256
    return bytes(int_data)


class MideaCloud:
    """Client API for Midea cloud"""

    # Default sleep unit of time. By default 1 second.
    _DEFAULT_SLEEP_INTERVAL: Final = 1
    # Unit of time for sleep.
    # Can be set to different value during tests.
    sleep_interval: float = _DEFAULT_SLEEP_INTERVAL

    def __init__(
        self,
        appkey: str | None,
        account: str,
        password: str,
        appid: int | str | None = DEFAULT_APP_ID,
        server_url: str = CLOUD_API_SERVER_URL,
    ) -> None:
        # Get this from any of the Midea based apps
        self._appkey = appkey or DEFAULT_APPKEY
        self._appid = int(appid or DEFAULT_APP_ID)
        # Your email address for your Midea account
        self._account = account
        self._password = password
        # Server URL
        self._server_url = server_url

        self._security = Security(appkey=self._appkey)

        # Unique user ID that is separate to the email address
        self._login_id: str = ""

        # A session dictionary that holds the login information of
        # the current user
        self._session: dict = {}

        # Allow for multiple threads to initiate requests
        self._api_lock = RLock()

        # Count the number of retries for API requests
        self.max_retries = _MAX_RETRIES
        self._retries = 0
        self.request_timeout: float = _DEFAULT_CLOUD_TIMEOUT

        # A list of appliances associated with the account
        self._appliance_list: list[dict[str, str]] = []

    def api_request(
        self,
        endpoint: str,
        args: dict[str, Any] = None,
        authenticate=True,
        key="result",
    ) -> Any:
        """
        Sends an API request to the Midea cloud service and returns the
        results or raises ValueError if there is an error

        Args:
            endpoint (str): endpoint on the API server
            args (dict[str, Any]): arguments for API request
            authenticate (bool, optional): should we first attempt to
                authenticate before sending request. Defaults to True.

        Raises:
            CloudRequestError: If an HTTP error occurs
            RecursionError: If there were too many retries

        Returns:
            dict: value of result key in json response
        """
        args = args or {}
        with self._api_lock:
            payload = {}

            try:
                if authenticate:
                    self.authenticate()

                if endpoint == "user/login" and self._session and self._login_id:
                    return self._session

                # Set up the initial data payload with the global variable set
                data = {
                    "appId": self._appid,
                    "format": CLOUD_API_FORMAT,
                    "clientType": CLOUD_API_CLIENT_TYPE,
                    "language": CLOUD_API_LANGUAGE,
                    "src": CLOUD_API_SRC,
                    "stamp": datetime.now().strftime("%Y%m%d%H%M%S"),
                }
                # Add the method parameters for the endpoint
                data.update(args)

                # Add the sessionId if there is a valid session
                if self._session:
                    data["sessionId"] = self._session["sessionId"]

                url = self._server_url + endpoint

                data["sign"] = self._security.sign(url, data)
                if not Redacted.redacting or endpoint not in PROTECTED_REQUESTS:
                    _LOGGER.debug(
                        "HTTP request %s: %s",
                        endpoint,
                        Redacted(data, keys=_REDACTED_REQUEST),
                    )
                # POST the endpoint with the payload
                response = requests.post(
                    url=url, data=data, timeout=self.request_timeout
                )
                response.raise_for_status()
                if not Redacted.redacting or endpoint not in PROTECTED_RESPONSES:
                    _LOGGER.debug("HTTP response text: %s", Redacted(response.text, 0))

                payload = json.loads(response.text)
            except RequestException as exc:
                return self._retry_api_request(
                    endpoint=endpoint,
                    args=args,
                    authenticate=authenticate,
                    key=key,
                    cause=exc,
                )

        if not Redacted.redacting or endpoint not in PROTECTED_RESPONSES:
            _LOGGER.debug(
                "HTTP response: %s",
                payload if not Redacted.redacting else "*** REDACTED ***",
            )

        # Check for errors, raise if there are any
        if str(payload.get("errorCode", "0")) != "0":
            self.handle_api_error(int(payload["errorCode"]), payload["msg"])
            # If no exception, then retry
            return self._retry_api_request(
                endpoint=endpoint,
                args=args,
                authenticate=authenticate,
                key=key,
                cause=f"{payload['msg']} ({payload['errorCode']})",
            )

        self._retries = 0
        return payload.get(key) if key else payload

    def _sleep(self, duration: float) -> None:
        sleep(duration * self.sleep_interval)

    def _retry_api_request(
        self,
        endpoint: str,
        args: dict[str, Any] = None,
        authenticate=True,
        key="result",
        cause=None,
    ) -> Any:
        self._retry_check(endpoint, cause)
        _LOGGER.debug(
            "Retrying API call %s: %d of %d",
            endpoint,
            self._retries + 1,
            self.max_retries,
        )
        return self.api_request(
            endpoint=endpoint, args=args, authenticate=authenticate, key=key
        )

    def _retry_check(self, endpoint: str, cause):
        self._retries += 1
        if self._retries >= self.max_retries:
            self._retries = 0
            raise CloudRequestError(
                f"Too many retries while calling {endpoint}, last error {cause}"
            ) from cause if isinstance(cause, BaseException) else None
        # wait few seconds before re-sending data, default is 0
        self._sleep(self._retries)

    def _get_login_id(self) -> None:
        """
        Get the login ID from the email address
        """
        response = self.api_request(
            "user/login/id/get",
            {"loginAccount": self._account},
            authenticate=False,
        )
        self._login_id: str = response["loginId"]

    def authenticate(self) -> None:
        """
        Performs a user login with the credentials supplied to the
        constructor
        """
        if not self._login_id:
            self._get_login_id()

        if self._session is not None and self._session.get("sessionId") is not None:
            # Don't try logging in again, someone beat this thread to it
            return

        # Log in and store the session
        self._session: dict = self.api_request(
            "user/login",
            {
                "loginAccount": self._account,
                "password": self._security.encrypt_password(
                    self._login_id, self._password
                ),
            },
            authenticate=False,
        )
        if not self._session.get("sessionId"):
            raise AuthenticationError("Unable to retrieve session id from Midea API")
        sensitive(str(self._session.get("sessionId")))
        self._security.access_token = str(self._session.get("accessToken"))
        sensitive(self._security.access_token)

    def get_lua_script(
        self,
        manufacturer="0000",
        appliance_type="0xA1",
        model="0",
        serial_number=None,
        version="0",
    ):
        """Retrieves Lua script used by mobile app"""
        response: dict = self.api_request(
            "appliance/protocol/lua/luaGet",
            {
                "iotAppId": DEFAULT_APP_ID,
                "applianceMFCode": manufacturer,
                "applianceType": appliance_type,
                "modelNumber": model,
                "applianceSn": serial_number,
                "version": version,
            },
            key=None,
        )
        if data := response.get("data", {}):
            url = str(data.get("url"))
            _LOGGER.debug("Lua script url=%s", url)
            payload = requests.get(url)
            # We could check that content has not been tampered with:
            # str(hashlib.md5(payload.content).hexdigest()) != str(data["md5"]):
            key = self._security.md5appkey
            lua = self._security.aes_decrypt_string(payload.content.decode(), key)
            return lua
        raise MideaError("Error retrieving lua script")

    def appliance_transparent_send(self, appliance_id: str, data: bytes) -> list[bytes]:
        """Sends payload to appliance via cloud as if it was sent locally.

        Args:
            appliance_id (str): Cloud appliance id
            data (bytes): Payload to send

        Raises:
            ProtocolError: If there was an issue sending payload

        Returns:
            list[bytes]: List of reply payloads
        """
        _LOGGER.debug("Sending to id=%s data=%s", Redacted(appliance_id, 4), data)
        encoded = _encode_as_csv(data)
        _LOGGER.debug("Encoded id=%s data=%s", Redacted(appliance_id, 4), encoded)

        order = self._security.aes_encrypt_string(encoded)
        response = self.api_request(
            "appliance/transparent/send",
            {"order": order, "funId": "0000", "applianceId": appliance_id},
        )

        decrypted = self._security.aes_decrypt_string(response["reply"])
        _LOGGER.debug("decrypted reply %s", decrypted)
        reply = _decode_from_csv(decrypted)
        _LOGGER.debug("Received from id=%s data=%s", Redacted(appliance_id, 4), reply)
        if len(reply) < 50:
            raise ProtocolError(
                f"Invalid payload size, was {len(reply)} expected 50 bytes"
            )
        reply = reply[50:]

        return [reply]

    def list_appliances(self, force: bool = False) -> list:
        """
        Lists all appliances associated with the account
        """
        if not force and self._appliance_list:
            return self._appliance_list

        # Get all home groups
        response = self.api_request("homegroup/list/get")
        _LOGGER.debug("Midea home group query result=%s", response)
        if not response or not response.get("list"):
            _LOGGER.debug(
                "Unable to get home groups from Midea API. response=%s",
                response,
            )
            raise CloudRequestError("Unable to get home groups from Midea API")
        home_groups = response["list"]

        # Find default home group
        home_group = next((grp for grp in home_groups if grp["isDefault"] == "1"), None)
        if not home_group:
            _LOGGER.debug("Unable to get default home group from Midea API")
            raise CloudRequestError("Unable to get default home group from Midea API")

        home_group_id = home_group["id"]

        # Get list of appliances in default home group
        response = self.api_request(
            "appliance/list/get", {"homegroupId": home_group_id}
        )

        self._appliance_list = []
        if response["list"]:
            for item in response["list"]:
                app: dict[str, str] = {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "sn": (
                        self._security.aes_decrypt_string(item.get("sn"))
                        if item.get("sn")
                        else "Unknown"
                    ),
                    "type": item.get("type"),
                    "modelNumber": item.get("modelNumber"),
                }
                sensitive(app["sn"], _REDACTED_KEYS["sn"])
                sensitive(app["id"], _REDACTED_KEYS["id"])
                self._appliance_list.append(app)
        _LOGGER.debug(
            "Midea appliance list results=%s",
            Redacted(self._appliance_list, keys=_REDACTED_KEYS),
        )

        return self._appliance_list

    def get_token(self, udp_id: str) -> Tuple[str, str]:
        """
        Get token corresponding to udp_id
        """

        response = self.api_request("iot/secure/getToken", {"udpid": udp_id})
        for token in response["tokenlist"]:
            if token["udpId"] == udp_id:
                return str(token["token"]), str(token["key"])
        return "", ""

    def handle_api_error(self, error: int, message: str) -> None:
        """
        Handle Midea API errors

        Args:
            error_code (integer): Error code received from API
            message (str): Textual explanation
        """

        def restart_full() -> None:
            _LOGGER.debug(
                "Full connection restart: '%s' - '%s'",
                error,
                message,
            )
            retries = self._retries
            self._retry_check("full-restart", cause=f"{message} ({error})")
            self._session = {}
            self._get_login_id()
            self.authenticate()
            self.list_appliances(True)
            self._retries = retries

        def session_restart() -> None:
            _LOGGER.debug("Restarting session: '%s' - '%s'", error, message)
            retries = self._retries
            self._retry_check("session-restart", cause=f"{message} ({error})")
            self._session = {}
            self.authenticate()
            self._retries = retries

        def authentication_error() -> None:
            _LOGGER.warning("Authentication error: '%s' - '%s'", error, message)
            raise CloudAuthenticationError(error, message, self._account)

        def retry_later() -> None:
            _LOGGER.debug("Retry later: '%s' - '%s'", error, message)
            raise RetryLaterError(error, message)

        def ignore() -> None:
            _LOGGER.debug("Ignored error: '%s' - '%s'", error, message)

        def cloud_error() -> None:
            raise CloudError(error, message)

        error_handlers = {
            3004: session_restart,  # value is illegal
            3101: authentication_error,  # invalid password
            3102: authentication_error,  # invalid username
            3106: session_restart,  # invalid session
            3144: restart_full,
            3176: ignore,  # The async reply does not exist
            3301: authentication_error,  # Invalid app key
            7610: retry_later,
            9999: ignore,  # system error
        }

        handler = error_handlers.get(error, cloud_error)
        handler()

    def __str__(self) -> str:
        return f"MideaCloud({self._server_url})"
