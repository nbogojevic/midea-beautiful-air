"""Connects to Midea cloud."""
from __future__ import annotations

import datetime
import json
import logging
from threading import Lock
from typing import Any, Final
from midea_beautiful_dehumidifier.exceptions import (
    AuthenticationError,
    CloudError,
    CloudRequestError,
    RetryLaterError,
)

import requests
from requests.exceptions import RequestException

from midea_beautiful_dehumidifier.crypto import Security

# The Midea cloud client is by far the more obscure part of this library,
# and without some serious reverse engineering this would not
# have been possible.
# Thanks Yitsushi for the ruby implementation.
# This is an adaptation to Python 3

_LOGGER = logging.getLogger(__name__)


SERVER_URL: Final = "https://mapp.appsmb.com/v1/"


class CloudService:

    CLIENT_TYPE = 1  # Android
    FORMAT = 2  # JSON
    LANGUAGE = "en_US"
    APP_ID = 1017
    SRC = 17

    def __init__(
        self,
        app_key: str,
        account: str,
        password: str,
        server_url: str = SERVER_URL,
    ):
        # Get this from any of the Midea based apps, you can find one on
        # Yitsushi's github page
        self.app_key = app_key
        # Your email address for your Midea account
        self.login_account = account
        self.password = password
        self.server_url = server_url

        # An obscure log in ID that is seperate to the email address
        self._login_id: str = ""

        # A session dictionary that holds the login information of
        # the current user
        self._session = {}

        # A list of home groups used by the API to seperate "zones"
        self._home_groups = []

        # A list of appliances associated with the account
        self._appliance_list = []

        self._api_lock = Lock()
        self._retries = 0

        self._security = Security(app_key=self.app_key)

    def api_request(
        self, endpoint: str, args: dict[str, Any], authenticate=True
    ):
        """
        Sends an API request to the Midea cloud service and returns the
        results or raises ValueError if there is an error
        """
        self._api_lock.acquire()
        if authenticate:
            self.authenticate()

        response = {}
        try:
            if endpoint == "user/login" and self._session and self._login_id:
                return self._session

            # Set up the initial data payload with the global variable set
            data = {
                "appId": self.APP_ID,
                "format": self.FORMAT,
                "clientType": self.CLIENT_TYPE,
                "language": self.LANGUAGE,
                "src": self.SRC,
                "stamp": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            }
            # Add the method parameters for the endpoint
            data.update(args)

            # Add the sessionId if there is a valid session
            if self._session:
                data["sessionId"] = self._session["sessionId"]

            url = self.server_url + endpoint

            data["sign"] = self._security.sign(url, data)
            # _LOGGER.debug("HTTP request = %s", data)
            # POST the endpoint with the payload
            r = requests.post(url=url, data=data, timeout=9)
            r.raise_for_status()
            # _LOGGER.debug("HTTP response text = %s", r.text)

            response = json.loads(r.text)
        except RequestException as exc:
            raise CloudRequestError(endpoint) from exc
        finally:
            self._api_lock.release()

        # _LOGGER.debug("HTTP response = %s", response)

        # Check for errors, raise if there are any
        if response["errorCode"] != "0":
            self.handle_api_error(int(response["errorCode"]), response["msg"])
            # If no exception, then retry
            self._retries += 1
            if self._retries < 3:
                _LOGGER.debug(
                    "Retrying API call: '%s' %d", endpoint, self._retries
                )
                return self.api_request(endpoint, args)
            else:
                raise RecursionError()

        self._retries = 0
        return response["result"]

    def get_login_id(self):
        """
        Get the login ID from the email address
        """
        response = self.api_request(
            "user/login/id/get",
            {"loginAccount": self.login_account},
            authenticate=False,
        )
        self._login_id: str = response["loginId"]

    def authenticate(self):
        """
        Performs a user login with the credentials supplied to the
        constructor
        """
        if len(self._login_id) == 0:
            self.get_login_id()

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
                "loginAccount": self.login_account,
                "password": self._security.encrypt_password(
                    self._login_id, self.password
                ),
            },
            authenticate=False
        )

        self._security.access_token = self._session["accessToken"]

        if not (
            self._session is not None
            and self._session.get("sessionId") is not None
        ):
            raise AuthenticationError()

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
        home_group_id = next(
            x for x in self._home_groups if x["isDefault"] == "1"
        )["id"]

        # TODO error if no home groups
        # Get list of appliances in selected home group
        response = self.api_request(
            "appliance/list/get", {"homegroupId": home_group_id}
        )

        self._appliance_list = response["list"]
        _LOGGER.debug("Midea appliance list results=%s", self._appliance_list)
        return self._appliance_list

    def list_homegroups(self):
        """
        Lists all home groups
        """

    def get_token(self, udpid):
        """
        Get tokenlist with udpid
        """

        response = self.api_request("iot/secure/getToken", {"udpid": udpid})
        for token in response["tokenlist"]:
            if token["udpId"] == udpid:
                return token["token"], token["key"]
        return None, None

    def handle_api_error(self, error_code, message: str):
        def restart_full():
            _LOGGER.debug(
                "Restarting full connection session: '%s' - '%s",
                error_code,
                message,
            )
            self._session = None
            self.get_login_id()
            self.authenticate()
            self.list_appliances()

        def session_restart():
            _LOGGER.debug(
                "Restarting session: '%s' - '%s", error_code, message
            )
            self._session = None
            self.authenticate()

        def retry_later():
            _LOGGER.debug("Retry later: '%s' - '%s", error_code, message)
            raise RetryLaterError(error_code, message)

        def throw():
            raise CloudError(error_code, message)

        def ignore():
            _LOGGER.debug("Error ignored: '%s' - '%s", error_code, message)

        error_handlers = {
            3101: restart_full,
            3176: ignore,  # The asyn reply does not exist.
            3106: session_restart,  # invalidSession.
            3144: restart_full,
            3004: session_restart,  # value is illegal.
            7610: retry_later,
            9999: ignore,  # system error.
        }

        handler = error_handlers.get(error_code, throw)
        handler()

    def __str__(self) -> str:
        return str(self.__dict__)
