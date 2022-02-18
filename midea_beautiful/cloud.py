"""Interface to Midea cloud API."""
from __future__ import annotations
import base64

from datetime import datetime
import json
import logging
from threading import RLock
from time import sleep, time
from typing import Any, Final, Tuple
from secrets import token_hex, token_urlsafe

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
from midea_beautiful.midea import (
    DEFAULT_API_SERVER_URL,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    DEFAULT_HMACKEY,
    DEFAULT_IOTKEY,
    DEFAULT_PROXIED,
    DEFAULT_SIGNKEY,
)
from midea_beautiful.util import Redacted, is_very_verbose, sensitive

# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-arguments
# spell-checker: ignore iampwd mdata

_LOGGER = logging.getLogger(__name__)


CLOUD_API_CLIENT_TYPE: Final = 1  # Android
CLOUD_API_FORMAT: Final = 2  # JSON
CLOUD_API_LANGUAGE: Final = "en_US"

PROTECTED_REQUESTS: Final = ["/v1/user/login/id/get", "/v1/user/login"]
PROTECTED_RESPONSES: Final = [
    "/v1/iot/secure/getToken",
    "/v1/user/login/id/get",
    "/v1/user/login",
]

_MAX_RETRIES: Final = 3
_DEFAULT_CLOUD_TIMEOUT: Final = 9
_REDACTED_KEYS: Final = {"id": {"length": 4}, "sn": {"length": 8}}
_REDACTED_REQUEST: Final = {"sessionId": {}}

_PROXIED_APP_VERSION: Final = "2.22.0"
_PROXIED_SYS_VERSION: Final = "8.1.0"


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
        api_url: str = DEFAULT_API_SERVER_URL,
        sign_key: str = DEFAULT_SIGNKEY,
        iot_key: str = DEFAULT_IOTKEY,
        hmac_key: str = DEFAULT_HMACKEY,
        proxied: str = DEFAULT_PROXIED,
    ) -> None:
        # Get this from any of the Midea based apps
        self._appkey = appkey or DEFAULT_APPKEY
        self._appid = int(appid or DEFAULT_APP_ID)
        self._sign_key = sign_key or DEFAULT_SIGNKEY
        self._iot_key = iot_key or DEFAULT_IOTKEY
        self._hmac_key = hmac_key or DEFAULT_HMACKEY
        self._proxied = proxied or DEFAULT_PROXIED
        self._pushtoken = token_urlsafe(120)
        # Your email address for your Midea account
        self._account = account
        self._password = password
        # Server URL
        self._api_url = api_url
        self._country_code = None

        self._security = Security(
            appkey=self._appkey,
            signkey=self._sign_key,
            iotkey=self._iot_key,
            hmackey=self._hmac_key,
        )

        basic = base64.b64encode(
            f"{self._appkey}:{self._iot_key}".encode("ascii")
        ).decode("ascii")
        self._proxied_auth = f"Basic {basic}"

        # Unique user ID that is separate to the email address
        self._login_id: str = ""

        self._country_code: str = ""
        self._id_adapt: str = ""
        self._mas_url: str = ""
        self._sse_url: str = ""
        # A session dictionary that holds the login information of
        # the current user
        self._session: dict = {}
        self._uid: str = ""
        self._header_access_token = ""

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
        key=None,
        data=None,
        req_id=None,
        instant=None,
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
                if data is None:
                    data = {
                        "appId": self._appid,
                        "format": CLOUD_API_FORMAT,
                        "clientType": CLOUD_API_CLIENT_TYPE,
                        "language": CLOUD_API_LANGUAGE,
                        "src": self._appid,
                        "stamp": datetime.now().strftime("%Y%m%d%H%M%S"),
                    }
                # Add the method parameters for the endpoint
                data.update(args)
                headers = {}

                # Add the sessionId if there is a valid session
                if self._session:
                    if not self._proxied:
                        data["sessionId"] = self._session["sessionId"]
                    else:
                        headers["uid"] = self._uid
                        headers["accessToken"] = self._header_access_token

                url = self._api_url + endpoint

                if self._proxied:
                    error_code_tag = "code"
                    key = key if key is not None else "data"
                    if not data.get("reqId"):
                        data.update(
                            {
                                "appVNum": _PROXIED_APP_VERSION,
                                "appVersion": _PROXIED_APP_VERSION,
                                "clientVersion": _PROXIED_APP_VERSION,
                                "platformId": "1",
                                "reqId": req_id or token_hex(16),
                                "retryCount": "3",
                                "uid": self._uid or "",
                                "userType": "0",
                            }
                        )
                    send_payload = json.dumps(data)
                    instant = instant or str(int(time()))
                    sign = self._security.sign_proxied(
                        None, data=send_payload, random=instant
                    )
                    headers.update(
                        {
                            "x-recipe-app": str(self._appid),
                            "Authorization": self._proxied_auth,
                            "sign": sign,
                            "secretVersion": "1",
                            "random": instant,
                            "version": _PROXIED_APP_VERSION,
                            "systemVersion": _PROXIED_SYS_VERSION,
                            "platform": "0",
                            "Accept-Encoding": "identity",
                            "Content-Type": "application/json",
                        }
                    )

                    if self._uid:
                        headers["uid"] = self._uid
                    if self._header_access_token:
                        headers["accessToken"] = self._header_access_token
                else:
                    error_code_tag = "errorCode"
                    key = key if key is not None else "result"
                    data["sign"] = self._security.sign(url, data)

                    send_payload = data

                if not Redacted.redacting or endpoint not in PROTECTED_REQUESTS:
                    _LOGGER.debug(
                        "HTTP request %s: %s %s",
                        endpoint,
                        headers,
                        Redacted(data, keys=_REDACTED_REQUEST),
                    )
                response = requests.post(
                    url=url,
                    data=send_payload,
                    timeout=self.request_timeout,
                    headers=headers,
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
        if str(payload.get(error_code_tag, "0")) != "0":
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
        result = payload.get(key) if key else payload
        if is_very_verbose():
            _LOGGER.debug("using key=%s, result=%s", key, result)
        return result

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
            "/v1/user/login/id/get",
            {"loginAccount": self._account},
            authenticate=False,
        )
        self._login_id: str = response["loginId"]

    def _get_region(self) -> None:
        """
        Gets the region from the email address
        """
        response = self.api_request(
            "/v1/multicloud/platform/user/route",
            {"userName": self._account},
            authenticate=False,
        )
        self._country_code: str = response["countryCode"]
        self._id_adapt: str = response["idAdapt"]
        if mas_url := response["masUrl"]:
            self._api_url = mas_url

    def authenticate(self) -> None:
        """
        Performs a user login with the credentials supplied to the
        constructor
        """
        if self._proxied and not self._country_code:
            self._get_region()
        if not self._login_id:
            self._get_login_id()

        if self._session:
            if self._proxied:
                return
            if self._session.get("sessionId") is not None:
                # Don't try logging in again, someone beat this thread to it
                return

        # Log in and store the session
        if self._proxied:
            login_id = self._login_id
            stamp = datetime.now().strftime("%Y%m%d%H%M%S")
            self._header_access_token = ""
            self._uid = ""
            self._session: dict = self.api_request(
                "/mj/user/login",
                instant=None,
                data={
                    "data": {
                        "appKey": self._appkey,
                        "appVersion": _PROXIED_APP_VERSION,
                        "osVersion": _PROXIED_SYS_VERSION,
                        "platform": "2",
                    },
                    "iotData": {
                        "appId": str(self._appid),
                        "appVNum": _PROXIED_APP_VERSION,
                        "appVersion": _PROXIED_APP_VERSION,
                        "clientType": CLOUD_API_CLIENT_TYPE,
                        "clientVersion": _PROXIED_APP_VERSION,
                        "format": CLOUD_API_FORMAT,
                        "language": CLOUD_API_LANGUAGE,
                        "iampwd": self._security.encrypt_iam_password(
                            login_id, self._password
                        ),
                        "loginAccount": self._account,
                        "password": self._security.encrypt_password(
                            login_id, self._password
                        ),
                        "pushToken": self._pushtoken,
                        "pushType": "4",
                        "reqId": token_hex(16),
                        "retryCount": "3",
                        "src": "10",
                        "stamp": stamp,
                    },
                    "reqId": token_hex(16),
                    "stamp": stamp,
                },
                authenticate=False,
            )
            self._uid = str(self._session.get("uid"))
            sensitive(self._uid)
            if mdata := self._session.get("mdata"):
                self._header_access_token = mdata["accessToken"]
                sensitive(self._header_access_token)

            self._security.set_access_token(
                str(self._session.get("accessToken")), self._appkey
            )
            sensitive(self._security.access_token)
        else:
            self._login_non_proxied()

    def _login_non_proxied(self):
        self._session: dict = self.api_request(
            "/v1/user/login",
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
            "/v1/appliance/protocol/lua/luaGet",
            {
                "iotAppId": DEFAULT_APP_ID,
                "applianceMFCode": manufacturer,
                "applianceType": appliance_type,
                "modelNumber": model,
                "applianceSn": serial_number,
                "version": version,
            },
            key="",
        )
        if response and (data := response.get("data", {})):
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
            "/v1/appliance/transparent/send",
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

        response = self.api_request("/v1/appliance/user/list/get", {})

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

        response = self.api_request("/v1/iot/secure/getToken", {"udpid": udp_id})
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
        return f"MideaCloud({self._api_url})"
