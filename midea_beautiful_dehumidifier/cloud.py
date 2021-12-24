"""Interface to Midea cloud API."""
from __future__ import annotations

from datetime import datetime
import json
import logging
from threading import RLock
from typing import Any, Final, Tuple
from midea_beautiful_dehumidifier.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    CloudError,
    CloudRequestError,
    RetryLaterError,
)
from midea_beautiful_dehumidifier.midea import (
    CLOUD_API_SERVER_URL,
    DEFAULT_APP_ID,
)

import requests
from requests.exceptions import RequestException

from midea_beautiful_dehumidifier.crypto import Security

_LOGGER = logging.getLogger(__name__)


CLOUD_API_CLIENT_TYPE: Final = 1  # Android
CLOUD_API_FORMAT: Final = 2  # JSON
CLOUD_API_LANGUAGE: Final = "en_US"
CLOUD_API_SRC: Final = 17

PROTECTED_REQUESTS: Final = ["user/login/id/get", "user/login"]
PROTECTED_RESPONSES: Final = ["iot/secure/getToken", "user/login/id/get", "user/login"]

_MAX_RETRIES: Final = 3


class MideaCloud:
    def __init__(
        self,
        appkey: str,
        account: str,
        password: str,
        appid: int = DEFAULT_APP_ID,
        server_url: str = CLOUD_API_SERVER_URL,
    ):
        # Get this from any of the Midea based apps
        self._appkey = appkey
        self._appid = appid
        # Your email address for your Midea account
        self._account = account
        self._password = password
        # Server URL
        self._server_url = server_url

        # An obscure log in ID that is separate to the email address
        self._login_id: str = ""

        # A session dictionary that holds the login information of
        # the current user
        self._session = {}

        # A list of appliances associated with the account
        self._appliance_list = []

        # Allow for multiple threads to initiate requests
        self._api_lock = RLock()

        # Count the number of retries for API requests
        self._max_retries = _MAX_RETRIES
        self._retries = 0

        self._security = Security(appkey=self._appkey)
        self._appliance_list: list[dict] = []

    def api_request(self, endpoint: str, args: dict[str, Any] = {}, authenticate=True):
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
        with self._api_lock:
            response = {}

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
                if endpoint not in PROTECTED_REQUESTS:
                    _LOGGER.log(5, "HTTP request %s: %s", endpoint, data)
                # POST the endpoint with the payload
                r = requests.post(url=url, data=data, timeout=9)
                r.raise_for_status()
                if endpoint not in PROTECTED_RESPONSES:
                    _LOGGER.log(5, "HTTP response text: %s", r.text)

                response = json.loads(r.text)
            except RequestException as exc:
                raise CloudRequestError(
                    f"Request error {exc} while calling {endpoint}"
                ) from exc

        if endpoint not in PROTECTED_RESPONSES:
            _LOGGER.log(5, "HTTP response: %s", response)

        # Check for errors, raise if there are any
        if response["errorCode"] != "0":
            self.handle_api_error(int(response["errorCode"]), response["msg"])
            # If no exception, then retry
            self._retries += 1
            if self._retries < self._max_retries:
                _LOGGER.debug(
                    "Retrying API call %s: %d of",
                    endpoint,
                    self._retries,
                    self._max_retries,
                )
                return self.api_request(endpoint, args)
            else:
                raise CloudRequestError(f"Too many retries while calling {endpoint}")

        self._retries = 0
        return response["result"]

    def _get_login_id(self):
        """
        Get the login ID from the email address
        """
        response = self.api_request(
            "user/login/id/get",
            {"loginAccount": self._account},
            authenticate=False,
        )
        self._login_id: str = response["loginId"]

    def authenticate(self):
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
        self._session = self.api_request(
            "user/login",
            {
                "loginAccount": self._account,
                "password": self._security.encrypt_password(
                    self._login_id, self._password
                ),
            },
            authenticate=False,
        )

        if not self._session or not self._session.get("sessionId"):
            raise AuthenticationError("Unable to retrieve session id from Midea API")

    def list_appliances(self, force: bool = False):
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
        home_group = next(grp for grp in home_groups if grp["isDefault"] == "1")
        if not home_group:
            _LOGGER.debug("Unable to get default home group from Midea API")
            raise CloudRequestError("Unable to get default home group from Midea API")

        home_group_id = home_group["id"]

        # Get list of appliances in default home group
        response = self.api_request(
            "appliance/list/get", {"homegroupId": home_group_id}
        )

        self._appliance_list = response["list"]
        _LOGGER.debug("Midea appliance list results=%s", self._appliance_list)
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

    def handle_api_error(self, error, message: str) -> None:
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
            self._session = None
            self._get_login_id()
            self.authenticate()
            self.list_appliances(True)

        def session_restart() -> None:
            _LOGGER.debug("Restarting session: '%s' - '%s'", error, message)
            self._session = None
            self.authenticate()

        def authentication_error() -> None:
            _LOGGER.warning("Authentication error: '%s' - '%s'", error, message)
            raise CloudAuthenticationError(error, message)

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
        return str(self.__dict__)
