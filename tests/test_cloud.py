"""Tests for Midea cloud client API"""
import json
from typing import Final
from unittest.mock import patch

import pytest
from requests.exceptions import RequestException
import requests_mock

from midea_beautiful.cloud import MideaCloud
from midea_beautiful.exceptions import (
    AuthenticationError,
    CloudAuthenticationError,
    CloudError,
    CloudRequestError,
    MideaError,
    RetryLaterError,
)
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name line-too-long
# pylint: disable=unused-argument

_j = json.dumps

DUMMY_RQ: Final = {"arg1": "value1"}
TEST_ACCESS_TOKEN: Final = (
    "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801"
)


@pytest.fixture(name="appliance_list")
def appliance_list(requests_mock: requests_mock.Mocker):
    # requests_mock.post(
    #     "https://mapp.appsmb.com/v1/homegroup/list/get",
    #     text=_j(
    #         {
    #             "errorCode": "0",
    #             "result": {"list": [{"isDefault": "1", "id": "group-id-1"}]},
    #         }
    #     ),
    # )
    requests_mock.post(
        "/v1/appliance/user/list/get",
        text=_j({"errorCode": "0", "result": {"list": [{"id": "1"}, {"id": "2"}]}}),
    )
    return requests_mock


@pytest.fixture(name="cloud_client")
def cloud_client() -> MideaCloud:
    cloud = MideaCloud(
        appkey=DEFAULT_APPKEY,
        appid=DEFAULT_APP_ID,
        account="user@example.com",
        password="pa55word",
    )
    cloud.sleep_interval = 0.001
    return cloud


@pytest.fixture(name="for_login")
def for_login(requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login/id/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j(
            {
                "errorCode": "0",
                "result": {"sessionId": "session-1", "accessToken": TEST_ACCESS_TOKEN},
            }
        ),
    )
    return requests_mock


def test_str(cloud_client: MideaCloud):
    assert "MideaCloud(https://mapp.appsmb.com)" in str(cloud_client)


def test_request_handling(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy", text=_j({"result": "response text"})
    )
    response = cloud_client.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert response == "response text"


def test_request_missing_result(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"response": "response text"}),
    )
    response = cloud_client.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert response is None


def test_request_error(cloud_client: MideaCloud, requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"errorCode": "2", "msg": "error message"}),
    )
    with pytest.raises(CloudError) as ex:
        cloud_client.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert ex.value.message == "error message"
    assert ex.value.error_code == 2
    assert str(ex.value) == "Midea cloud API error: error message (2)"


def test_request_retry(cloud_client: MideaCloud, requests_mock: requests_mock.Mocker):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"errorCode": "7610", "msg": "retry error message"}),
    )
    with pytest.raises(RetryLaterError) as ex:
        cloud_client.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert ex.value.message == "retry error message"
    assert str(ex.value) == "Retry later: retry error message (7610)"


def test_request_authentication_error(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        text=_j({"errorCode": "3102", "msg": "authentication error"}),
    )
    with pytest.raises(CloudAuthenticationError) as ex:
        cloud_client.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert ex.value.message == "authentication error"
    assert ex.value.error_code == 3102
    assert str(ex.value) == "Cloud authentication error: authentication error (3102)"


def test_bad_authentication_reply(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login/id/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j(
            {
                "errorCode": "0",
                "result": {"accessToken": TEST_ACCESS_TOKEN},
            }
        ),
    )
    with pytest.raises(AuthenticationError) as ex:
        cloud_client.authenticate()
    assert ex.value.message == "Unable to retrieve session id from Midea API"


def test_cache_login_reply(cloud_client: MideaCloud, for_login: requests_mock.Mocker):
    res = cloud_client.api_request("user/login", DUMMY_RQ)
    assert res == {
        "accessToken": TEST_ACCESS_TOKEN,
        "sessionId": "session-1",
    }
    assert len(for_login.request_history) == 2


def test_request_too_many_retries(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/too-many-retries",
        text=_j({"errorCode": "9999", "msg": "internal error - ignore"}),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.api_request("/v1/too-many-retries", DUMMY_RQ, authenticate=False)
    assert (
        ex.value.message
        == "Too many retries while calling /v1/too-many-retries, last error internal error - ignore (9999)"  # noqa: E501
    )


def test_request_exception(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/exception",
        exc=RequestException("simulated"),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.api_request("/v1/exception", DUMMY_RQ, authenticate=False)
    assert (
        ex.value.message
        == "Too many retries while calling /v1/exception, last error simulated"
    )


def test_session_restart(cloud_client: MideaCloud, requests_mock: requests_mock.Mocker):
    cloud = cloud_client

    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        [
            {"text": '{"errorCode": "3106", "msg": "session restart"}'},
            {"text": _j({"result": "response text"})},
        ],
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login/id/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j(
            {
                "errorCode": "0",
                "result": {"sessionId": "session-1", "accessToken": TEST_ACCESS_TOKEN},
            }
        ),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/homegroup/list/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    result = cloud.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert result == "response text"
    history = requests_mock.request_history

    assert history[0].url == "https://mapp.appsmb.com/v1/dummy"
    assert history[1].url == "https://mapp.appsmb.com/v1/user/login/id/get"
    assert history[2].url == "https://mapp.appsmb.com/v1/user/login"
    assert history[3].url == "https://mapp.appsmb.com/v1/dummy"


def test_session_restart_retries(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker
):
    cloud = cloud_client

    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        [
            {"text": '{"errorCode": "3004", "msg": "value is illegal"}'},
            {"text": _j({"result": "response text"})},
        ],
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login/id/get",
        [
            {"text": '{"errorCode": "3004", "msg": "value is illegal"}'},
            {"text": '{"errorCode": "3004", "msg": "value is illegal"}'},
            {"text": '{"errorCode": "3004", "msg": "value is illegal"}'},
            {"text": '{"errorCode": "3004", "msg": "value is illegal"}'},
            {"text": '{"errorCode": "3004", "msg": "value is illegal"}'},
        ],
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j(
            {
                "errorCode": "0",
                "result": {"sessionId": "session-1", "accessToken": TEST_ACCESS_TOKEN},
            }
        ),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/user/login",
        text=_j({"text": '{"errorCode": "3004", "msg": "value is illegal"}'}),
    )
    requests_mock.post(
        "https://mapp.appsmb.com/v1/homegroup/list/get",
        text=_j({"errorCode": "0", "result": {"loginId": "test-login"}}),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert (
        ex.value.message
        == "Too many retries while calling session-restart, last error value is illegal (3004)"  # noqa: E501
    )


def test_full_restart(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/dummy",
        [
            {"text": _j({"errorCode": "3144", "msg": "full restart"})},
            {"text": _j({"result": "successful"})},
        ],
    )
    result = cloud_client.api_request("/v1/dummy", DUMMY_RQ, authenticate=False)
    assert result == "successful"
    assert cloud_client._login_id == "test-login"
    assert cloud_client._session["sessionId"] == "session-1"
    history = requests_mock.request_history
    assert history[0].url == "https://mapp.appsmb.com/v1/dummy"
    assert history[1].url == "https://mapp.appsmb.com/v1/user/login/id/get"
    assert history[2].url == "https://mapp.appsmb.com/v1/user/login"
    assert history[3].url == "https://mapp.appsmb.com/v1/appliance/user/list/get"
    assert history[4].url == "https://mapp.appsmb.com/v1/dummy"


def test_full_restart_retries(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    requests_mock.post(
        "https://mapp.appsmb.com/v1/full_restart_retries",
        text=_j({"errorCode": "3144", "msg": "full restart"}),
    )
    with pytest.raises(CloudRequestError) as ex:
        cloud_client.api_request(
            "/v1/full_restart_retries", DUMMY_RQ, authenticate=False
        )
    assert (
        ex.value.message
        == "Too many retries while calling full-restart, last error full restart (3144)"  # noqa: E501
    )


def test_list_appliance(
    cloud_client: MideaCloud,
    requests_mock: requests_mock.Mocker,
    for_login,
    appliance_list,
):
    list_od_appliances = cloud_client.list_appliances()
    assert len(list_od_appliances) == 2

    cloud_client._appliance_list = [{}]
    list_od_appliances = cloud_client.list_appliances()
    assert len(list_od_appliances) == 1
    list_od_appliances = cloud_client.list_appliances(force=True)
    assert len(list_od_appliances) == 2


def test_get_token(
    cloud_client: MideaCloud, requests_mock: requests_mock.Mocker, for_login
):
    requests_mock.post(
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
    token, key = cloud_client.get_token("1")
    assert token == "token-1"
    assert key == "key-1"

    token, key = cloud_client.get_token("2")
    assert token == "token-2"
    assert key == "key-2"

    token, key = cloud_client.get_token("absent")
    assert token == ""
    assert key == ""


def test_appliance_transparent_send(cloud_client, for_login: requests_mock.Mocker):
    for_login.post(
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
    cloud_client.authenticate()
    cloud_client._security.access_token = TEST_ACCESS_TOKEN

    result = cloud_client.appliance_transparent_send(str(12345), b"\x12\x34\x81")
    assert len(result) == 1
    assert (
        result[0].hex()
        == "aa20a100000000000303412100ff030000020000000000000000000000000b24a400000000000000000000000000000000"  # noqa: E501
    )


def test_lua_script_ko(cloud_client: MideaCloud, for_login: requests_mock.Mocker):
    for_login.post(
        "https://mapp.appsmb.com/v1/appliance/protocol/lua/luaGet",
        text=_j({"md5": "12345", "url": "http://test.example.com/script.lua"}),
    )
    with pytest.raises(MideaError) as ex:
        cloud_client.get_lua_script(serial_number="456", manufacturer="1234")
    assert ex.value.message == "Error retrieving lua script"


def test_lua_script(cloud_client: MideaCloud, for_login: requests_mock.Mocker):
    for_login.post(
        "https://mapp.appsmb.com/v1/appliance/protocol/lua/luaGet",
        text=_j(
            {"data": {"md5": "12345", "url": "http://test.example.com/script.lua"}}
        ),
    )
    with patch.object(cloud_client._security, "aes_decrypt_string", return_value="LUA"):
        for_login.get("http://test.example.com/script.lua", text="/v1/dummy")
        res = cloud_client.get_lua_script(serial_number="456", manufacturer="1234")
        assert res == "LUA"
