"""Connects to Midea cloud."""
from __future__ import annotations

import datetime
import json
import logging
from threading import Lock
from typing import Any

import requests

from midea_beautiful_dehumidifier.util import (Security, hex4logging,
                                               midea_command, midea_service,
                                               packet_time)

# The Midea cloud client is by far the more obscure part of this library,
# and without some serious reverse engineering this would not have been possible.
# Thanks Yitsushi for the ruby implementation. This is an adaptation to Python 3

_LOGGER = logging.getLogger(__name__)


class cloud_packet_builder:

    def __init__(self: cloud_packet_builder, device_id: int | str):
        self.command = None

        # Init the packet with the header data. Weird magic numbers,
        # I'm not sure what they all do, but they have to be there (packet length at 0x4)
        # self.packet: bytearray = bytearray([
        #     0x5a, 0x5a, 0x01, 0x00, 0x5b, 0x00, 0x20, 0x00,
        #     0x01, 0x00, 0x00, 0x00, 0x27, 0x24, 0x11, 0x09,
        #     0x0d, 0x0a, 0x12, 0x14, 0xda, 0x49, 0x00, 0x00,
        #     0x00, 0x10, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        #     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        # ])
        self.packet: bytearray = bytearray([
            # 2 bytes - StaticHeader
            0x5a, 0x5a,
            # 2 bytes - mMessageType
            0x01, 0x00,
            # 2 bytes - PacketLenght
            0x00, 0x00,
            # 2 bytes
            0x20, 0x00,
            # 4 bytes - MessageId
            0x00, 0x00, 0x00, 0x00,
            # 8 bytes - Date&Time
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # 8 bytes - mDeviceID
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            # 12 bytes
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])
        self.packet[12:20] = packet_time()
        self.packet[20:28] = int(device_id).to_bytes(8, 'little')

    def set_command(self: cloud_packet_builder, command: midea_command):
        self.command = command.finalize()

    def finalize(self: cloud_packet_builder):
        if self.command is None:
            raise Exception("Command was not specified")
        # Append the command data to the packet
        self.packet.extend(self.command)

        # Pad with 0's
        self.packet.extend([0] * (49 - len(self.command)))
        # Set the packet length in the packet!
        self.packet[0x04] = len(self.packet)
        _LOGGER.debug("Cloud packet: %s",
                      hex4logging(self.packet, _LOGGER))
        return self.packet


SERVER_URL = 'https://mapp.appsmb.com/v1/'


class cloud(midea_service):

    CLIENT_TYPE = 1                 # Android
    FORMAT = 2                      # JSON
    LANGUAGE = 'en_US'
    APP_ID = 1017
    SRC = 17

    def __init__(self, app_key: str, account: str, password: str, server_url: str = SERVER_URL):
        # Get this from any of the Midea based apps, you can find one on
        # Yitsushi's github page
        self._app_key = app_key
        # Your email address for your Midea account
        self._login_account = account
        self._password = password
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

        self._api_lock = Lock()
        self._retries = 0

        self._security = Security(app_key=self._app_key)

    def status(self, cmd: midea_command, id: str | int) -> list[bytearray]:
        """
        Retrieves device status
        """
        pkt_builder = cloud_packet_builder(id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        res: bytearray = self._appliance_transparent_send_with_retry(data, id)
        _LOGGER.debug("Got status response from '%s': %s",
                      id, hex4logging(res, _LOGGER))
        if len(res) < 0x50:
            _LOGGER.error(
                "Got error response, length was %d, should be at least 80",
                len(res))
            return []

        return [res[50:]]

    def apply(self, cmd: midea_command,
              id: str | int, protocol: int = None) -> bytearray | None:
        """
        Sets device status
        """
        pkt_builder = cloud_packet_builder(id)
        pkt_builder.set_command(cmd)
        data = pkt_builder.finalize()
        res: bytearray = self._appliance_transparent_send_with_retry(data, id)
        _LOGGER.debug("Got status response after apply from '%s': %s",
                      id, hex4logging(res, _LOGGER))
        if len(res) < 0x50:
            _LOGGER.error(
                "Got error response, length was %d, should be at least 80",
                len(res))
            return

        return res[50:]

    def _appliance_transparent_send_with_retry(self: cloud,
                                               data, id) -> bytearray:
        """
        Retries sending appliance/transparent/send if it timeouts on 
        first request 
        """
        try:
            res = self._appliance_transparent_send(data, id=id)
        except requests.exceptions.ReadTimeout as e:
            # retry once
            _LOGGER.debug("Retrying after time-out exception: %s %s", e, id)
            res = self._appliance_transparent_send(data, id=id)

        return res

    def api_request(self, endpoint: str, args: dict[str, Any]):
        """
        Sends an API request to the Midea cloud service and returns the 
        results or raises ValueError if there is an error
        """
        self._api_lock.acquire()
        response = {}
        try:
            if endpoint == 'user/login' and self._session and self._login_id:
                return self._session

            # Set up the initial data payload with the global variable set
            data = {
                'appId': self.APP_ID,
                'format': self.FORMAT,
                'clientType': self.CLIENT_TYPE,
                'language': self.LANGUAGE,
                'src': self.SRC,
                'stamp': datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            }
            # Add the method parameters for the endpoint
            data.update(args)

            # Add the sessionId if there is a valid session
            if self._session:
                data['sessionId'] = self._session['sessionId']

            url = self._server_url + endpoint

            data['sign'] = self._security.sign(url, data)
            _LOGGER.debug("HTTP request = %s", data)
            # POST the endpoint with the payload
            r = requests.post(url=url, data=data, timeout=9)
            r.raise_for_status()
            _LOGGER.debug("HTTP response text = %s", r.text)

            response = json.loads(r.text)
        finally:
            self._api_lock.release()

        _LOGGER.debug("HTTP response = %s", response)

        # Check for errors, raise if there are any
        if response['errorCode'] != '0':
            self.handle_api_error(int(response['errorCode']), response['msg'])
            # If no exception, then retry
            self._retries += 1
            if(self._retries < 3):
                _LOGGER.debug("Retrying API call: '%s' %d",
                              endpoint, self._retries)
                return self.api_request(endpoint, args)
            else:
                raise RecursionError()

        self._retries = 0
        return response['result']

    def get_login_id(self):
        """
        Get the login ID from the email address
        """
        response = self.api_request('user/login/id/get', {
            'loginAccount': self._login_account
        })
        self._login_id: str = response['loginId']

    def authenticate(self) -> bool:
        """
        Performs a user login with the credentials supplied to the 
        constructor
        """
        if len(self._login_id) == 0:
            self.get_login_id()

        if self._session is not None and self._session.get('sessionId') is not None:
            # Don't try logging in again, someone beat this thread to it
            return True

        # Log in and store the session
        self._session = self.api_request('user/login', {
            'loginAccount': self._login_account,
            'password': self._security.encrypt_password(self._login_id,
                                                        self._password)
        })

        self._security.access_token = self._session['accessToken']

        return self._session is not None and self._session.get('sessionId') is not None

    def list_appliances(self):
        """
        Lists all appliances associated with the account
        """

        # Get all home groups
        if not self._home_groups:
            response = self.api_request('homegroup/list/get', {})
            _LOGGER.debug("Midea home group query result=%s", response)
            if not response or response.get('list') is None:
                _LOGGER.error(
                    "Unable to get home groups from Midea Cloud. response=%s",
                    response)
                return []
            self._home_groups = response['list']

        # Find default home group
        home_group_id = next(
            x for x in self._home_groups if x['isDefault'] == '1')['id']

        # TODO error if no home groups
        # Get list of appliances in selected home group
        response = self.api_request('appliance/list/get', {
            'homegroupId': home_group_id
        })

        self._appliance_list = response['list']
        _LOGGER.debug("Midea appliance list results=%s", self._appliance_list)
        return self._appliance_list

    def _encode(self, data: bytearray):
        normalized = []
        for b in data:
            if b >= 128:
                b = b - 256
            normalized.append(str(b))

        string = ','.join(normalized)
        return bytearray(string.encode('ascii'))

    def _decode(self, data: bytes | bytearray):
        datas = [int(a) for a in data.decode('ascii').split(',')]
        for i in range(len(datas)):
            if datas[i] < 0:
                datas[i] = datas[i] + 256
        return bytearray(datas)

    def _appliance_transparent_send(self, data: bytearray,
                                    id: str | int) -> bytearray:
        if not self._session:
            self.authenticate()

        _LOGGER.debug("Sending to %s: %s", id,  hex4logging(data, _LOGGER))
        encoded = self._encode(data)
        order = self._security.aes_encrypt(encoded)
        response = self.api_request('appliance/transparent/send', {
            'order': order.hex(),
            'funId': '0000',
            'applianceId': id
        })

        reply = self._decode(self._security.aes_decrypt(
            bytearray.fromhex(response['reply'])))

        _LOGGER.debug("Recieved from %s: %s", id, hex4logging(reply, _LOGGER))
        return reply

    def list_homegroups(self):
        """
        Lists all home groups
        """

    def get_token(self, udpid):
        """
        Get tokenlist with udpid
        """

        response = self.api_request('iot/secure/getToken', {
            'udpid': udpid
        })
        for token in response['tokenlist']:
            if token['udpId'] == udpid:
                return token['token'], token['key']
        return None, None

    def handle_api_error(self, error_code, message: str):

        def restart_full():
            _LOGGER.debug(
                "Restarting full connection session: '%s' - '%s", error_code, message)
            self._session = None
            self.get_login_id()
            self.authenticate()
            self.list_appliances()

        def session_restart():
            _LOGGER.debug("Restarting session: '%s' - '%s",
                          error_code, message)
            self._session = None
            self.authenticate()

        def retry_later():
            _LOGGER.debug("Retry later: '%s' - '%s",
                          error_code, message)
            raise Exception(error_code, message)

        def throw():
            raise ValueError(error_code, message)

        def ignore():
            _LOGGER.debug("Error ignored: '%s' - '%s", error_code, message)

        error_handlers = {
            3101: restart_full,
            3176: ignore,          # The asyn reply does not exist.
            3106: session_restart,  # invalidSession.
            3144: restart_full,
            3004: session_restart,  # value is illegal.
            7610: retry_later,
            9999: ignore,  # system error.
        }

        handler = error_handlers.get(error_code, throw)
        handler()

    def __str__(self) -> str:
        return str(__dict__)
