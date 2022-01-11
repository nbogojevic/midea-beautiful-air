"""Tests for Midea commands"""
from binascii import unhexlify
from typing import Final

import pytest
from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance

from midea_beautiful.command import (
    AirConditionerResponse,
    AirConditionerSetCommand,
    DehumidifierResponse,
    DehumidifierSetCommand,
    DeviceCapabilitiesCommand,
    DeviceCapabilitiesCommandMore,
    MideaSequenceCommand,
)
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APPKEY,
)

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name
# pylint: disable=invalid-name line-too-long

APP_KEY: Final = DEFAULT_APPKEY


def setup_function():
    MideaSequenceCommand.reset_sequence()


@pytest.fixture(name="dehumidifier")
def dehumidifier():
    return DehumidifierAppliance(
        appliance_id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER
    )


@pytest.fixture(name="aircon")
def aircon():
    return AirConditionerAppliance(
        appliance_id="12345", appliance_type=APPLIANCE_TYPE_AIRCON
    )


def test_device_capabilities_command() -> None:
    dc = DeviceCapabilitiesCommand()
    assert dc.finalize().hex() == "aa0ea100000000000303b501118ef6"


def test_device_capabilities_command_more() -> None:
    dc = DeviceCapabilitiesCommandMore()
    assert dc.finalize().hex() == "aa0ea100000000000303b501011381"


def test_dehumidifier_status(dehumidifier: DehumidifierAppliance) -> None:
    cmd = dehumidifier.refresh_command().finalize()
    assert (
        cmd.hex()
        == "aa20a100000000000003418100ff03ff000000000000000000000000000001294f"
    )


def test_dehumidifier_set(dehumidifier: DehumidifierAppliance) -> None:
    cmd = dehumidifier.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa20a100000000000302480000280000003200000000000000000000000001395e"
    )


def test_dehumidifier_set_fan_speed(dehumidifier: DehumidifierAppliance) -> None:
    dehumidifier.fan_speed = 60
    cmd = dehumidifier.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa20a1000000000003024800003c0000003200000000000000000000000001dea5"
    )


def test_dehumidifier_set_mode(dehumidifier: DehumidifierAppliance) -> None:
    dehumidifier.mode = 3
    cmd = dehumidifier.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa20a1000000000003024800032800000032000000000000000000000000014b49"
    )


def test_dehumidifier_set_target_humidity(dehumidifier: DehumidifierAppliance) -> None:
    dehumidifier.target_humidity = 45
    cmd = dehumidifier.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa20a100000000000302480000280000002d000000000000000000000000017626"
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
        cmd.hex()
        == "aa20a100000000000302480001320000000000100000000000000000000001e8c6"
    )


def test_ac_status(aircon: AirConditionerAppliance) -> None:
    cmd = aircon.refresh_command().finalize()
    assert (
        cmd.hex()
        == "aa20ac00000000000003418100ff03ff00020000000000000000000000000171fa"
    )


def test_ac_status_in_sequence(aircon: AirConditionerAppliance) -> None:
    MideaSequenceCommand.reset_sequence(2)
    cmd = aircon.refresh_command().finalize()
    assert (
        cmd.hex()
        == "aa20ac00000000000003418100ff03ff000200000000000000000000000003cd9c"
    )


def test_aircon_defaults() -> None:
    cmd = AirConditionerSetCommand()
    assert not cmd.beep_prompt
    assert not cmd.comfort_sleep
    assert not cmd.dryer
    assert not cmd.eco_mode
    assert not cmd.fahrenheit
    assert not cmd.horizontal_swing
    assert not cmd.purifier
    assert not cmd.running
    assert not cmd.screen
    assert not cmd.turbo
    assert not cmd.turbo_fan
    assert not cmd.vertical_swing
    assert cmd.fan_speed == 0
    assert cmd.mode == 0
    assert cmd.temperature == 16
    assert cmd.temperature_decimal == 0


def test_aircon_set_fan(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.fan_speed = 48
    cmd = aircon.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa23ac0000000000000240400030000000000000100000000000000000000100000078f6"
    )


def test_aircon_set_mode(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.fan_speed = 48
    aircon.mode = 2
    cmd = aircon.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa23ac00000000000002404040300000000000001000000000000000000001000000ce60"
    )


def test_aircon_set_turbo(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.turbo = True
    aircon.fan_speed = 40
    cmd = aircon.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa23ac000000000000024040002800000000000012000000000000000000010000000173"
    )


def test_aircon_set_temperature(aircon: AirConditionerAppliance) -> None:
    aircon.beep_prompt = True
    aircon.turbo = True
    aircon.fan_speed = 45
    aircon.target_temperature = 20.5
    cmd = aircon.apply_command().finalize()
    assert (
        cmd.hex()
        == "aa23ac000000000000024040142d0000000000001200000000000000000001000000a7b4"
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
    assert "'fault': False" in str(response)
    assert "'current_humidity': 63" in str(response)


def test_dehumidifier_response_big_values():
    response = DehumidifierResponse(
        unhexlify("c80101287f7f007c00000000000000003fa200000000024238")
    )
    assert response.target_humidity == 100
    assert response.indoor_temperature == 50
    assert "'fault': False" in str(response)


def test_dehumidifier_response_short():
    response = DehumidifierResponse(unhexlify("c80101287f7f003c00000000000000003f5238"))
    assert response.current_humidity == 63
    assert not response.tank_full
    assert response.target_humidity == 60
    assert response.light_class is None
    assert "'light_class': None" in str(response)


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
    assert response.outdoor_temperature == -9
    assert response.indoor_temperature == 7

    response = AirConditionerResponse(
        unhexlify("c80101287f7f003c00000041210000003f5000000000024238")
    )
    assert response.outdoor_temperature == -8.5
    assert response.indoor_temperature == 7.5
    response = AirConditionerResponse(
        unhexlify("c80101287f7f003c00000042240000243f5000000000024238")
    )
    assert response.outdoor_temperature == -7.2
    assert response.indoor_temperature == 8.4
    response = AirConditionerResponse(
        unhexlify("c80101287f7f003c00000022520000373f5000000000024238")
    )
    assert response.outdoor_temperature == 16.3
    assert response.indoor_temperature == -8.7
    assert "'indoor_temperature': -8.7" in str(response)
