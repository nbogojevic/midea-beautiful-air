import json
import unittest

from requests.exceptions import RequestException
import requests_mock

from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import (
    CloudAuthenticationError,
    CloudError,
    CloudRequestError,
    RetryLaterError,
)
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

_j = json.dumps


class TestCloud(unittest.TestCase):
    def _setup_for_login(self, m: requests_mock.Mocker):
        m.post(
            "https://mapp.appsmb.com/v1/user/login/id/get",
            text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
        )
        m.post(
            "https://mapp.appsmb.com/v1/user/login",
            text=_j(
                {
                    "errorCode": "0",
                    "result": {
                        "sessionId": "session-1",
                        "accessToken": "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801",  # noqa: E501
                    },
                }
            ),
        )

    def _setup_appliance_list(self, m: requests_mock.Mocker):
        m.post(
            "https://mapp.appsmb.com/v1/homegroup/list/get",
            text=_j(
                {
                    "errorCode": "0",
                    "result": {"list": [{"isDefault": "1", "id": "group-id-1"}]},
                }
            ),
        )
        m.post(
            "https://mapp.appsmb.com/v1/appliance/list/get",
            text=_j({"errorCode": "0", "result": {"list": [{}, {}]}}),
        )

    def _cloud_client(self) -> MideaCloud:
        return MideaCloud(
            appkey=DEFAULT_APPKEY,
            appid=DEFAULT_APP_ID,
            account="user@example.com",
            password="pa55word",
        )

    def test_request_handling(self):
        cloud = self._cloud_client()

        with requests_mock.Mocker() as m:
            m.post(
                "https://mapp.appsmb.com/v1/dummy", text=_j({"result": "response text"})
            )
            response = cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertEqual("response text", response)
            m.post(
                "https://mapp.appsmb.com/v1/dummy",
                text=_j({"response": "response text"}),
            )
            response = cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertIsNone(response)
            m.post(
                "https://mapp.appsmb.com/v1/dummy",
                text=_j({"errorCode": "2", "msg": "error message"}),
            )
            with self.assertRaises(CloudError) as ex:
                cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertEqual("error message", ex.exception.message)
            self.assertEqual(2, ex.exception.error_code)
            m.post(
                "https://mapp.appsmb.com/v1/dummy",
                text=_j({"errorCode": "7610", "msg": "retry error message"}),
            )
            with self.assertRaises(RetryLaterError) as ex:
                cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertEqual("retry error message", ex.exception.message)

            m.post(
                "https://mapp.appsmb.com/v1/dummy",
                text=_j({"errorCode": "3102", "msg": "authentication error"}),
            )
            with self.assertRaises(CloudAuthenticationError) as ex:
                cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertEqual("authentication error", ex.exception.message)
            self.assertEqual(3102, ex.exception.error_code)

            # Too many retries
            m.post(
                "https://mapp.appsmb.com/v1/too-many-retries",
                text=_j({"errorCode": "9999", "msg": "internal error - ignore"}),
            )
            with self.assertRaises(CloudRequestError) as ex:
                cloud.api_request(
                    "too-many-retries", {"arg1": "test1"}, authenticate=False
                )
            self.assertEqual(
                "Too many retries while calling too-many-retries", ex.exception.message
            )
            m.post(
                "https://mapp.appsmb.com/v1/exception",
                exc=RequestException("simulated"),
            )
            with self.assertRaises(CloudRequestError) as ex:
                cloud.api_request("exception", {"arg1": "test1"}, authenticate=False)
            self.assertEqual(
                "Request error simulated while calling exception", ex.exception.message
            )

    def test_session_restart(self):
        cloud = self._cloud_client()

        with requests_mock.Mocker() as m:

            m.post(
                "https://mapp.appsmb.com/v1/dummy",
                [
                    {"text": '{"errorCode": "3106", "msg": "session restart"}'},
                    {"text": _j({"result": "response text"})},
                ],
            )
            m.post(
                "https://mapp.appsmb.com/v1/user/login/id/get",
                text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
            )
            m.post(
                "https://mapp.appsmb.com/v1/user/login",
                text=_j(
                    {
                        "errorCode": "0",
                        "result": {
                            "sessionId": "session-1",
                            "accessToken": "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801",  # noqa E501
                        },
                    }
                ),
            )
            m.post(
                "https://mapp.appsmb.com/v1/homegroup/list/get",
                text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
            )
            result = cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertEqual("response text", result)

    def test_full_restart(self):
        cloud = MideaCloud(
            appkey=DEFAULT_APPKEY,
            appid=DEFAULT_APP_ID,
            account="user@example.com",
            password="pa55word",
        )
        with requests_mock.Mocker() as m:
            m.post(
                "https://mapp.appsmb.com/v1/dummy",
                [
                    {"text": _j({"errorCode": "3144", "msg": "full restart"})},
                    {"text": _j({"result": "successful"})},
                ],
            )
            self._setup_for_login(m)
            self._setup_appliance_list(m)
            result = cloud.api_request("dummy", {"arg1": "test1"}, authenticate=False)
            self.assertEqual("successful", result)
            self.assertEqual("test-login", cloud._login_id)
            self.assertEqual("session-1", cloud._session["sessionId"])

    def test_full_restart_retries(self):
        cloud = self._cloud_client()

        with requests_mock.Mocker() as m:
            m.post(
                "https://mapp.appsmb.com/v1/full_restart",
                text=_j({"errorCode": "3144", "msg": "full restart"}),
            )
            self._setup_for_login(m)
            self._setup_appliance_list(m)

            with self.assertRaises(CloudRequestError) as ex:
                cloud.api_request("full_restart", {"arg1": "test1"}, authenticate=False)
            self.assertEqual(
                "Too many retries while calling full_restart", ex.exception.message
            )

    def test_list_appliance(self):
        cloud = self._cloud_client()

        with requests_mock.Mocker() as m:
            self._setup_for_login(m)

            self._setup_appliance_list(m)

            list = cloud.list_appliances()
            self.assertEqual(2, len(list))

            cloud._appliance_list = [{}]
            list = cloud.list_appliances()
            self.assertEqual(1, len(list))
            list = cloud.list_appliances(force=True)
            self.assertEqual(2, len(list))
            # No default appliance
            m.post(
                "https://mapp.appsmb.com/v1/homegroup/list/get",
                text=_j(
                    {
                        "errorCode": "0",
                        "result": {
                            "list": [
                                {"isDefault": "0", "id": "group-id-1"},
                                {"isDefault": "0", "id": "group-id-2"},
                            ]
                        },
                    }
                ),
            )
            with self.assertRaises(CloudRequestError) as ex:
                cloud.list_appliances(force=True)
            self.assertEqual(
                "Unable to get default home group from Midea API", ex.exception.message
            )
            m.post(
                "https://mapp.appsmb.com/v1/homegroup/list/get",
                text=_j({"errorCode": "0", "result": {}}),
            )
            with self.assertRaises(CloudRequestError) as ex:
                cloud.list_appliances(force=True)
            self.assertEqual(
                "Unable to get home groups from Midea API", ex.exception.message
            )

    def test_get_token(self):
        cloud = self._cloud_client()

        with requests_mock.Mocker() as m:
            self._setup_for_login(m)
            m.post(
                "https://mapp.appsmb.com/v1/iot/secure/getToken",
                text=_j(
                    {
                        "errorCode": "0",
                        "result": {
                            "tokenlist": [
                                {"udpId": "2", "token": "token-2", "key": "key-2"},
                                {"udpId": "1", "token": "token-1", "key": "key-1"},
                            ]
                        },
                    }
                ),
            )
            token, key = cloud.get_token("1")
            self.assertEqual("token-1", token)
            self.assertEqual("key-1", key)

            token, key = cloud.get_token("2")
            self.assertEqual("token-2", token)
            self.assertEqual("key-2", key)

            token, key = cloud.get_token("absent")
            self.assertEqual("", token)
            self.assertEqual("", key)

    def test_appliance_transparent_send(self):
        cloud = self._cloud_client()

        with requests_mock.Mocker() as m:
            self._setup_for_login(m)
            m.post(
                "https://mapp.appsmb.com/v1/appliance/transparent/send",
                text=_j(
                    {
                        "errorCode": "0",
                        "result": {
                            "reply": (
                                "7c8911b6de8e29fa9a1538def06c9018a9995980893554fb80fd87"
                                "c5478ac78b360f7b35433b8d451464bdcd3746c4f5c05a8099eceb"
                                "79aeb9cc2cc712f90f1c9b3bb091bcf0e90bddf62d36f29550796c"
                                "55acf8e637f7d3d68d11be993df933d94b2b43763219c85eb21b4d"
                                "9bb9891f1ab4ccf24185ccbcc78c393a9212c24bef3466f9b3f18a"
                                "6aabcd58e80ce9df61ccf13885ebd714595df69709f09722ff41eb"
                                "37ea5b06f727b7fab01c94588459ccf13885ebd714595df69709f0"
                                "9722ff32b544a259d2fa6e7ddaac1fdff91bb0"
                            )
                        },
                    }
                ),
            )
            cloud.authenticate()
            cloud._security.access_token = "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801"  # noqa: E501
            result = cloud.appliance_transparent_send(str(12345), b"\x12\x34\x81")
            self.assertEqual(len(result), 1)
            self.assertEqual(
                result[0].hex(),
                "412100ff030000020000000000000000000000000b24a400000000000000000000000000000000",  # noqa: E501
            )
