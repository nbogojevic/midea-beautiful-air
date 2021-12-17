"""Connects to Midea cloud."""
from __future__ import annotations

import datetime
import json
import logging
from threading import Lock
from typing import Any, Final
from midea_beautiful_dehumidifier.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    CloudError,
    CloudRequestError,
    RetryLaterError,
)

import requests
from requests.exceptions import RequestException

from midea_beautiful_dehumidifier.crypto import Security

_LOGGER = logging.getLogger(__name__)


CLOUD_API_SERVER_URL: Final = "https://mapp.appsmb.com/v1/"

CLOUD_API_CLIENT_TYPE: Final = 1  # Android
CLOUD_API_FORMAT: Final = 2  # JSON
CLOUD_API_LANGUAGE: Final = "en_US"
CLOUD_API_APP_ID: Final = 1017
CLOUD_API_SRC: Final = 17


class MideaCloud:
    def __init__(
        self,
        appkey: str,
        account: str,
        password: str,
        server_url: str = CLOUD_API_SERVER_URL,
        max_retries: int = 3,
    ):
        # Get this from any of the Midea based apps, you can find one on
        # Yitsushi's github page
        self._appkey = appkey
        # Your email address for your Midea account
        self._account = account
        self._password = password
        # Server URL
        self._server_url = server_url

        # An obscure log in ID that is seperate to the email address
        self._login_id: str = ""

        # A session dictionary that holds the login information of
        # the current user
        self._session = {}

        # A list of home groups used by the API to seperate "zones"
        self._home_groups = []

        # A list of appliances associated with the account
        self._appliance_list = []

        # Allow for multiple threads to initiate requests
        self._api_lock = Lock()

        # Count the number of retries for API requests
        self._max_retries = max_retries
        self._retries = 0

        self._security = Security(appkey=self._appkey)

    def api_request(
        self, endpoint: str, args: dict[str, Any], authenticate=True
    ):
        """
        Sends an API request to the Midea cloud service and returns the
        results or raises ValueError if there is an error

        Args:
            endpoint (str): endpoint on the API server
            args (dict[str, Any]): arguments for API request
            authenticate (bool, optional): should we first attempt to
                authenticate before sending request. Defaults to True.

        Raises:
            CloudRequestError: If an HTTP error occured
            RecursionError: If there were too many retries

        Returns:
            dict: value of result key in json response
        """
        response = {}
        with self._api_lock:

            try:
                if authenticate:
                    self.authenticate()

                if (
                    endpoint == "user/login"
                    and self._session
                    and self._login_id
                ):
                    return self._session

                # Set up the initial data payload with the global variable set
                data = {
                    "appId": CLOUD_API_APP_ID,
                    "format": CLOUD_API_FORMAT,
                    "clientType": CLOUD_API_CLIENT_TYPE,
                    "language": CLOUD_API_LANGUAGE,
                    "src": CLOUD_API_SRC,
                    "stamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                }
                # Add the method parameters for the endpoint
                data.update(args)

                # Add the sessionId if there is a valid session
                if self._session:
                    data["sessionId"] = self._session["sessionId"]

                url = self._server_url + endpoint

                data["sign"] = self._security.sign(url, data)
                _LOGGER.log(5, "HTTP request = %s", data)
                # POST the endpoint with the payload
                r = requests.post(url=url, data=data, timeout=9)
                r.raise_for_status()
                _LOGGER.log(5, "HTTP response text = %s", r.text)

                response = json.loads(r.text)
            except RequestException as exc:
                raise CloudRequestError(endpoint) from exc

        _LOGGER.log(5, "HTTP response = %s", response)

        # Check for errors, raise if there are any
        if response["errorCode"] != "0":
            self.handle_api_error(int(response["errorCode"]), response["msg"])
            # If no exception, then retry
            self._retries += 1
            if self._retries < self._max_retries:
                _LOGGER.debug(
                    "Retrying API call: '%s' %d of",
                    endpoint,
                    self._retries,
                    self._max_retries,
                )
                return self.api_request(endpoint, args)
            else:
                raise RecursionError()

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
        if len(self._login_id) == 0:
            self._get_login_id()

        if (
            self._session is not None
            and self._session.get("sessionId") is not None
        ):
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

        if self._session is None or self._session.get("sessionId") is None:
            raise AuthenticationError("no sessionId")

    def list_appliances(self):
        """
        Lists all appliances associated with the account
        """

        # Get all home groups
        if not self._home_groups:
            response = self.api_request("homegroup/list/get", {})
            _LOGGER.debug("Midea home group query result=%s", response)
            if not response or response.get("list") is None:
                _LOGGER.error(
                    "Unable to get home groups from Midea Cloud. response=%s",
                    response,
                )
                return []
            self._home_groups = response["list"]

        # Find default home group
        home_group = next(
            x for x in self._home_groups if x["isDefault"] == "1"
        )
        if home_group is None:
            _LOGGER.error(
                "Unable to get default home group from Midea Cloud."
            )
            return []

        home_group_id = home_group["id"]

        # Get list of appliances in selected home group
        response = self.api_request(
            "appliance/list/get", {"homegroupId": home_group_id}
        )

        self._appliance_list = response["list"]
        _LOGGER.debug("Midea appliance list results=%s", self._appliance_list)
        return self._appliance_list

    def get_token(self, udpid):
        """
        Get tokenlist with udpid
        """

        response = self.api_request("iot/secure/getToken", {"udpid": udpid})
        for token in response["tokenlist"]:
            if token["udpId"] == udpid:
                return str(token["token"]), str(token["key"])
        return "", ""

    def handle_api_error(self, error_code, message: str):
        """
        Handle Midea API errors

        Args:
            error_code (integer): Error code received from API
            message (str): Textual explanation
        """

        def restart_full():
            _LOGGER.debug(
                "Restarting full connection session: '%s' - '%s",
                error_code,
                message,
            )
            self._session = None
            self._get_login_id()
            self.authenticate()
            self.list_appliances()

        def session_restart():
            _LOGGER.debug(
                "Restarting session: '%s' - '%s", error_code, message
            )
            self._session = None
            self.authenticate()

        def authentication_error():
            _LOGGER.warn(
                "Authentication error: '%s' - '%s", error_code, message
            )
            raise CloudAuthenticationError(error_code, message)

        def retry_later():
            _LOGGER.debug("Retry later: '%s' - '%s", error_code, message)
            raise RetryLaterError(error_code, message)

        def throw():
            raise CloudError(error_code, message)

        def ignore():
            _LOGGER.debug("Error ignored: '%s' - '%s", error_code, message)

        error_handlers = {
            3004: session_restart,  # value is illegal
            3101: authentication_error,  # invalid password
            3102: authentication_error,  # invalid username
            3106: session_restart,  # invalid session
            3144: restart_full,
            3176: ignore,  # The asyn reply does not exist
            3301: authentication_error,  # Invalid app key
            7610: retry_later,
            9999: ignore,  # system error
        }

        handler = error_handlers.get(error_code, throw)
        handler()

    def __str__(self) -> str:
        return str(self.__dict__)
