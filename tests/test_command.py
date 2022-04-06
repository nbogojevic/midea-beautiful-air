"""Tests for Midea commands"""
from binascii import unhexlify
from typing import Final

import pytest
from midea_beautiful.appliance import (
    AirConditionerAppliance,
    Appliance,
    DehumidifierAppliance,
)

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
    dc = DeviceCapabilitiesCommand(0xA1)
    assert dc.finalize().hex() == "aa0ea100000000000303b501004d48"


def test_device_capabilities_command_more_a1() -> None:
    dc = DeviceCapabilitiesCommandMore(0xA1)
    assert dc.finalize().hex() == "aa0fa100000000000303b501011380"


def test_device_capabilities_command_more() -> None:
    dc = DeviceCapabilitiesCommandMore(0xAC)
    assert dc.finalize().hex() == "aa0fac00000000000303b501011375"


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
    assert command.tank_warning_level == 0
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


def test_dehumidifier_tank_warning_level() -> None:
    command = DehumidifierSetCommand()
    assert command.tank_warning_level == 0
    command.tank_warning_level = 50
    cmd = command.finalize()
    assert command.tank_warning_level == 50

    assert (
        cmd.hex()
        == "aa20a1000000000003024800013200000000000000000032000000000000014448"
    )


_CMD_MSMART = b"\xaa \xac\x00\x00\x00\x00\x00\x00\x03A\x81\x00\xff\x03\xff\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x11\xeco"  # noqa: E501


def test_ac_status(aircon: AirConditionerAppliance) -> None:
    cmd = aircon.refresh_command().finalize()
    assert (
        cmd.hex()
        == "aa20ac00000000000003418100ff03ff00020000000000000000000000000171fa"
    )


def test_ac_status_2(aircon: AirConditionerAppliance) -> None:
    cmd = aircon.refresh_command()
    MideaSequenceCommand.reset_sequence(0x10)
    data = cmd.finalize()
    assert len(data.hex()) == len(_CMD_MSMART.hex())
    assert data.hex() == _CMD_MSMART.hex()


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
    assert not response.off_timer_set
    assert response.off_timer_hour == 31
    assert not response.on_timer_set
    assert response.on_timer_hour == 31
    assert "'fault': False" in str(response)
    assert "'current_humidity': 63" in str(response)


def test_dehumidifier_response_cube20():
    cube20_data = unhexlify("c80101507f7f0023000000000000004b1e580000000000080a28")
    cube20 = DehumidifierResponse(cube20_data)
    assert cube20.current_humidity == 30
    assert not cube20.tank_full
    assert cube20.target_humidity == 35
    assert cube20.tank_warning_level == 75

    assert not cube20.off_timer_set
    assert cube20.off_timer_hour == 31
    assert not cube20.on_timer_set
    assert cube20.on_timer_hour == 31
    assert "'fault': False" in str(cube20)
    assert "'current_humidity': 30" in str(cube20)
    cube20_data = unhexlify("c80101507f7f003c00000000000000641e440000000000098370")
    cube20 = DehumidifierResponse(cube20_data)
    assert cube20.current_humidity == 30
    assert cube20.target_humidity == 60
    assert cube20.tank_warning_level == 100


def test_dehumidifier_response_cube50():
    cube50pump_data = unhexlify("c80101507f7f00280010000000000064255000000000000716f0")
    cube50 = DehumidifierResponse(cube50pump_data)
    assert cube50.current_humidity == 37
    assert cube50.tank_warning_level == 100
    assert not cube50.tank_full
    assert cube50.target_humidity == 40
    assert not cube50.off_timer_set
    assert cube50.off_timer_hour == 31
    assert not cube50.on_timer_set
    assert cube50.on_timer_hour == 31
    assert "'fault': False" in str(cube50)
    assert "'current_humidity': 37" in str(cube50)


def test_capabilities_cube():
    cube50 = Appliance.instance("99", APPLIANCE_TYPE_DEHUMIDIFIER)
    b5 = unhexlify("b50510020103170201021d020101200201012d020104c40f")
    cube50.process_response_device_capabilities(b5)
    assert cube50.capabilities == {
        "fan_speed": 3,
        "filter": 2,
        "pump": 1,
        "dry_clothes": 1,
        "water_level": 4,
    }
    cube20 = Appliance.instance("99", APPLIANCE_TYPE_DEHUMIDIFIER)
    b5 = unhexlify("b5041002010317020102200201012d02010457a2")
    cube20.process_response_device_capabilities(b5)
    assert cube20.capabilities == {
        "dry_clothes": 1,
        "fan_speed": 3,
        "filter": 2,
        "water_level": 4,
    }


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
    response = AirConditionerResponse(
        b"\xc0\x00Rf\x7f\x7f\x00<\x00\x00\x04VZ\x00p\x00\x00\x00\x00\x00\x00\x00\x00\x01\xac\xa8"  # noqa: E501
    )
    assert response.mode == 2
