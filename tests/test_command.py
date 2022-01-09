from binascii import unhexlify
from typing import Final

import pytest
from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance

from midea_beautiful.command import (
    AirConditionerResponse,
    DehumidifierResponse,
    DehumidifierSetCommand,
    DeviceCapabilitiesCommand,
    DeviceCapabilitiesCommandMore,
    midea_command_reset_sequence,
)
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APPKEY,
)

APP_KEY: Final = DEFAULT_APPKEY


def setup_function(fun):
    midea_command_reset_sequence()


@pytest.fixture(name="dehumidifier")
def dehumidifier():
    return DehumidifierAppliance(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)


@pytest.fixture(name="aircon")
def aircon():
    return AirConditionerAppliance(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)


def test_device_capabilities_command() -> None:
    dc = DeviceCapabilitiesCommand()
    assert "aa0ea100000000000303b501118ef6" == dc.finalize().hex()


def test_device_capabilities_command_more() -> None:
    dc = DeviceCapabilitiesCommandMore()
    assert "aa0ea100000000000303b501011381" == dc.finalize().hex()


def test_dehumidifier_status(dehumidifier: DehumidifierAppliance) -> None:
    cmd = dehumidifier.refresh_command().finalize()
    assert (
        "aa20a100000000000003418100ff03ff000000000000000000000000000001294f"
        == cmd.hex()
    )


def test_dehumidifier_set(dehumidifier: DehumidifierAppliance) -> None:
    cmd = dehumidifier.apply_command().finalize()
    assert (
        "aa20a100000000000302480000280000003200000000000000000000000001395e"
        == cmd.hex()
    )


def test_dehumidifier_set_fan_speed(dehumidifier: DehumidifierAppliance) -> None:
    dehumidifier.fan_speed = 60
    cmd = dehumidifier.apply_command().finalize()
    assert (
        "aa20a1000000000003024800003c0000003200000000000000000000000001dea5"
        == cmd.hex()
    )


def test_dehumidifier_set_mode(dehumidifier: DehumidifierAppliance) -> None:
    dehumidifier.mode = 3
    cmd = dehumidifier.apply_command().finalize()
    assert (
        "aa20a1000000000003024800032800000032000000000000000000000000014b49"
        == cmd.hex()
    )


def test_dehumidifier_set_target_humidity(dehumidifier: DehumidifierAppliance) -> None:
    dehumidifier.target_humidity = 45
    cmd = dehumidifier.apply_command().finalize()
    assert (
        "aa20a100000000000302480000280000002d000000000000000000000000017626"
        == cmd.hex()
    )


def test_dehumidifier_set_various() -> None:
    command = DehumidifierSetCommand()
    assert not command.running
    assert not command.ion_mode
    assert not command.pump_switch_flag
    assert not command.pump_switch
    assert not command.sleep_switch
    assert not command.beep_prompt
    assert command.target_humidity == 0
    assert command.fan_speed == 50
    assert command.mode == 1
    command.pump_switch_flag = True

    cmd = command.finalize()
    assert command.pump_switch_flag
    assert (
        "aa20a100000000000302480001320000000000100000000000000000000001e8c6"
        == cmd.hex()
    )


def test_ac_status(aircon: AirConditionerAppliance) -> None:
    cmd = aircon.refresh_command().finalize()
    assert (
        "aa20ac00000000000003418100ff03ff00020000000000000000000000000171fa"
        == cmd.hex()
    )


def test_ac_status_in_sequence(aircon: AirConditionerAppliance) -> None:
    midea_command_reset_sequence(2)
    cmd = aircon.refresh_command().finalize()
    assert (
        "aa20ac00000000000003418100ff03ff000200000000000000000000000003cd9c"
        == cmd.hex()
    )


def test_aircon_set_fan(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.fan_speed = 48
    cmd = aircon.apply_command().finalize()
    assert (
        "aa23ac0000000000000240400030000000000000100000000000000000000100000078f6"
        == cmd.hex()
    )


def test_aircon_set_mode(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.fan_speed = 48
    aircon.mode = 2
    cmd = aircon.apply_command().finalize()
    assert (
        "aa23ac00000000000002404040300000000000001000000000000000000001000000ce60"
        == cmd.hex()
    )


def test_aircon_set_turbo(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.turbo = True
    aircon.fan_speed = 40

    cmd = aircon.apply_command().finalize()
    assert (
        "aa23ac000000000000024040002800000000000012000000000000000000010000000173"
        == cmd.hex()
    )


def test_aircon_set_temperature(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.turbo = True
    aircon.fan_speed = 45
    aircon.target_temperature = 20.5

    cmd = aircon.apply_command().finalize()
    assert (
        "aa23ac000000000000024040142d0000000000001200000000000000000001000000a7b4"
        == cmd.hex()
    )


def test_dehumidifier_response():
    response = DehumidifierResponse(
        unhexlify("c80101287f7f003c00000000000000003f5000000000024238")
    )
    assert response.current_humidity == 63
    assert not response.tank_full
    assert response.target_humidity == 60
    assert not response.off_timer["status"]
    assert response.off_timer["hour"] == 31
    assert not response.on_timer["status"]
    assert response.on_timer["hour"] == 0


def test_ac_response():
    response = AirConditionerResponse(
        unhexlify("c80101287f7f003c00000000000000003f5000000000024238")
    )
    assert response.outdoor_temperature is None
    assert response.indoor_temperature is None
    assert response.target_temperature == 17
    response = AirConditionerResponse(
        unhexlify("c80101287f7f003c00000040200000003f5000000000024238")
    )
    print(response)
    assert response.outdoor_temperature == -9
    assert response.indoor_temperature == 7
