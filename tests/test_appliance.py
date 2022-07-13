"""Test appliance class"""

import binascii
from typing import Final
import logging
import pytest
from midea_beautiful.appliance import (
    AirConditionerAppliance,
    Appliance,
    DehumidifierAppliance,
)
from midea_beautiful.command import MideaCommand
from midea_beautiful.exceptions import MideaError
from midea_beautiful.util import very_verbose

# pylint: disable=protected-access
# pylint: disable=missing-function-docstring
# pylint: disable=invalid-name line-too-long
# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


def test_appliance(caplog: pytest.LogCaptureFixture):
    appliance = Appliance.instance("44", "99")
    assert appliance.appliance_id == "44"
    assert appliance.type == "99"
    assert not isinstance(appliance, DehumidifierAppliance)
    assert not isinstance(appliance, AirConditionerAppliance)
    assert isinstance(appliance, Appliance)
    assert str(appliance) == "[UnknownAppliance]{id=** type=99}"
    assert appliance.model == appliance.type
    assert not appliance.online
    assert isinstance(appliance.refresh_command(), MideaCommand)
    assert isinstance(appliance.apply_command(), MideaCommand)
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        appliance.process_response(b"")
        assert len(caplog.records) == 1
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        appliance.process_response_device_capabilities(b"")
        assert len(caplog.records) == 0
        caplog.clear()
        appliance.process_response_device_capabilities(b"\xff")
        assert len(caplog.records) == 1


def test_appliance_same_type():
    assert not Appliance.same_types("a0", "a1")
    assert not Appliance.same_types(0xA0, 0xA1)
    assert Appliance.same_types(0xA0, 0xA0)
    assert Appliance.same_types(0xA0, "a0")
    assert Appliance.same_types("a1", "0xa1")
    assert Appliance.same_types(0xA1, "0xa1")
    assert Appliance.same_types("0xa1", 0xA1)
    assert Appliance.same_types("a0", "0xa0")


def test_dehumidifier():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)

    assert "[Dehumidifier]" in str(appliance)

    assert appliance.appliance_id == "44"
    assert appliance.type == "a1"
    assert not appliance.running
    appliance.running = "On"
    assert appliance.running
    appliance.running = "OFF"
    assert not appliance.running
    appliance.running = "true"
    assert appliance.running
    appliance.running = "0"
    assert not appliance.running
    appliance.running = "true"
    assert appliance.running
    appliance.running = "TRUE"
    assert appliance.running
    with pytest.raises(ValueError):
        appliance.running = "TRU"


def test_dehumidifier_mode():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    assert appliance.mode == 0
    appliance.mode = 4
    assert appliance.mode == 4
    with pytest.raises(MideaError) as ex:
        appliance.mode = 16
    assert ex.value.message == "Tried to set mode to invalid value: 16"
    # Let'appliance test __str__ method
    assert str(ex.value) == "Tried to set mode to invalid value: 16"


def test_dehumidifier_target_humidity():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    assert appliance.target_humidity == 50
    appliance.target_humidity = 4
    assert appliance.target_humidity == 4
    appliance.target_humidity = 5.2
    assert appliance.target_humidity == 5
    appliance.target_humidity = -4
    assert appliance.target_humidity == 0
    appliance.target_humidity = 100
    assert appliance.target_humidity == 100
    appliance.target_humidity = 101
    assert appliance.target_humidity == 100


def test_dehumidifier_fan():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    assert appliance.fan_speed == 40
    appliance.fan_speed = 4
    assert appliance.fan_speed == 4
    appliance.fan_speed = -4
    assert appliance.fan_speed == 0
    appliance.fan_speed = 100
    assert appliance.fan_speed == 100
    appliance.fan_speed = 128
    assert appliance.fan_speed == 127


def test_dehumidifier_beep():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    assert not appliance.beep_prompt
    appliance.beep_prompt = "on"
    assert appliance.beep_prompt
    appliance.beep_prompt = "off"
    assert not appliance.beep_prompt


def test_dehumidifier_pump_switch():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    assert not appliance.pump_switch_flag
    appliance.pump_switch_flag = "on"
    assert appliance.pump_switch_flag
    cmd = appliance.apply_command()
    assert cmd.pump_switch_flag


def test_dehumidifier_swinger():
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    assert not appliance.vertical_swing
    appliance.vertical_swing = "on"
    assert appliance.vertical_swing
    cmd = appliance.apply_command()
    assert cmd.vertical_swing
    appliance.vertical_swing = 0
    assert not appliance.vertical_swing
    cmd = appliance.apply_command()
    assert not cmd.vertical_swing


def test_dehumidifier_device_capabilities(caplog: pytest.LogCaptureFixture):
    appliance = Appliance.instance("44", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    capabilities_no_ion: Final = (
        b"\xb5\x03\x10\x02\x01\x07\x1f\x02\x01\x01 \x02\x01\x01\xcb\\"
    )
    capabilities_ion: Final = (
        b"\xb5\x04\x10\x02\x01\x07\x1e\x02\x01\x01\x1f\x02\x01\x01 \x02\x01\x01\xabU"
    )
    capabilities_no_auto: Final = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01 \x02\x01\x01\xcb\\"
    )
    capabilities_unknown: Final = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x02\x01\x01\xcb\\"
    )
    capabilities_unknown_extra: Final = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x01\x01\x01\xcb\\"
    )
    capabilities_filter: Final = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\x17\x02\x01\x01\xcb\\"
    )
    capabilities_filter_pump: Final = (
        b"\xb5\x03\x10\x02\x01\x07\x1d\x02\x01\x01\x17\x02\x01\x01\xcb\\"
    )
    capabilities_level_pump: Final = (
        b"\xb5\x03\x10\x02\x01\x03\x1d\x02\x01\x01\x2d\x02\x01\x01\xcb\\"
    )
    capabilities_mode_pump: Final = (
        b"\xb5\x03\x10\x02\x01\x03\x1d\x02\x01\x01\x14\x02\x01\x04\xcb\\"
    )
    appliance.process_response_device_capabilities(capabilities_ion)
    assert appliance.capabilities == {"fan_speed": 7, "auto": 1, "dry_clothes": 1, "ion": 1}  # noqa: E501
    appliance.process_response_device_capabilities(capabilities_no_ion)
    assert appliance.capabilities == {"fan_speed": 7, "auto": 1, "dry_clothes": 1}
    appliance.process_response_device_capabilities(capabilities_filter)
    assert appliance.capabilities == {"fan_speed": 7, "filter": 1, "light": 1}
    appliance.process_response_device_capabilities(capabilities_filter_pump)
    assert appliance.capabilities == {"fan_speed": 7, "filter": 1, "pump": 1}
    appliance.process_response_device_capabilities(capabilities_level_pump)
    assert appliance.capabilities == {"fan_speed": 3, "water_level": 1, "pump": 1}
    appliance.process_response_device_capabilities(capabilities_mode_pump)
    assert appliance.capabilities == {"fan_speed": 3, "mode": 4, "pump": 1}
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_no_auto)
    assert appliance.capabilities == {"fan_speed": 7, "light": 1, "dry_clothes": 1}
    assert len(caplog.records) == 0
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_unknown)
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "Midea B5 unknown property=b'\\xff\\x02'"
    assert appliance.capabilities == {"fan_speed": 7, "light": 1}
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_unknown_extra)
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "Midea B5 unknown property=b'\\xff\\x01'"
    assert appliance.capabilities == {"fan_speed": 7, "light": 1}


def test_dehumidifier_empty_response():
    appliance = Appliance.instance("43", "a1")
    assert isinstance(appliance, DehumidifierAppliance)
    appliance._online = True
    assert appliance.online
    appliance.process_response(b"")
    assert not appliance.online
    appliance.process_response(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
    )
    assert appliance.online


def test_aircon():
    appliance = Appliance.instance("45", "ac")
    assert isinstance(appliance, AirConditionerAppliance)


def test_aircon_modes():
    appliance = Appliance.instance("45", "ac")
    assert isinstance(appliance, AirConditionerAppliance)
    assert appliance.mode == 0
    appliance.mode = 4
    assert appliance.mode == 4
    with pytest.raises(MideaError) as ex:
        appliance.mode = 24
    assert ex.value.message == "Tried to set mode to invalid value: 24"


def test_aircon_temperature():
    appliance = Appliance.instance("45", "ac")
    assert isinstance(appliance, AirConditionerAppliance)
    assert appliance.target_temperature == 0
    appliance.target_temperature = 24
    assert appliance.target_temperature == 24
    with pytest.raises(MideaError) as ex:
        appliance.target_temperature = 44
    assert (
        ex.value.message == "Tried to set target temperature 44.0 out of allowed range"
    )


def test_aircon_booleans():
    appliance = Appliance.instance("45", "ac")
    assert isinstance(appliance, AirConditionerAppliance)

    assert appliance.appliance_id == "45"
    assert appliance.type == "ac"
    appliance.running = "TRUE"
    assert appliance.running

    assert not appliance.eco_mode
    appliance.eco_mode = "1"
    assert appliance.eco_mode
    appliance.eco_mode = "oFf"
    assert not appliance.eco_mode

    assert not appliance.turbo_fan
    appliance.turbo_fan = "1"
    assert appliance.turbo_fan
    appliance.turbo_fan = "0"
    assert not appliance.turbo_fan

    assert not appliance.comfort_sleep
    appliance.comfort_sleep = "oN"
    assert appliance.comfort_sleep
    appliance.comfort_sleep = "ofF"
    assert not appliance.comfort_sleep

    assert not appliance.purifier
    appliance.purifier = 1
    assert appliance.purifier
    appliance.purifier = "off"
    assert not appliance.purifier

    assert not appliance.dryer
    appliance.dryer = "on"
    assert appliance.dryer
    appliance.dryer = 0
    assert not appliance.dryer

    assert not appliance.fahrenheit
    appliance.fahrenheit = "t"
    assert appliance.fahrenheit
    appliance.fahrenheit = 0
    assert not appliance.fahrenheit

    # By default show screen
    assert appliance.show_screen
    appliance.show_screen = "f"
    assert not appliance.show_screen
    appliance.show_screen = "y"
    assert appliance.show_screen


def test_aircon_swing():
    appliance = Appliance.instance("45", "ac")
    assert isinstance(appliance, AirConditionerAppliance)

    assert not appliance.vertical_swing
    appliance.vertical_swing = 1
    assert appliance.vertical_swing
    appliance.vertical_swing = 0
    assert not appliance.vertical_swing

    assert not appliance.horizontal_swing
    appliance.horizontal_swing = True
    assert appliance.horizontal_swing
    appliance.horizontal_swing = 0
    assert not appliance.horizontal_swing


capabilities_ion: Final = (
    b"\xb5\x04\x10\x02\x01\x07\x1e\x02\x01\x01\x1f\x02\x01\x01\x2a\x02\x01\x01\xabU"
)
capabilities_no_auto: Final = (
    b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\x12\x02\x01\x01\xcb\\"
)
capabilities_unknown: Final = (
    b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x02\x01\x01\xcb\\"
)
capabilities_unknown_extra: Final = (
    b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x01\x01\x01\xcb\\"
)
capabilities_fan: Final = (
    b"\xb5\x04\x10\x02\x01\x03\x1e\x02\x01\x01\x1f\x02\x01\x01\x21\x02\x01\x01\xabU"
)
capabilities_fahrenheit_filter_check: Final = (
    b"\xb5\x04\x10\x02\x01\x07\x1e\x02\x01\x01\x13\x02\x01\x01\x22\x02\x01\x01\xabU"
)
capabilities_fan_avoid_ptc_fan_straight: Final = (
    b"\xb5\x04\x10\x02\x01\x07\x33\x02\x01\x01\x19\x02\x01\x01\x32\x02\x01\x01\xabU"
)
capabilities_self_clean_fan_swing: Final = (
    b"\xb5\x03\x10\x02\x01\x07\x39\x02\x01\x01\x15\x02\x01\x01\xabU"
)
capabilities_none: Final = b"\xb5\x00\xabU"
capabilities_electricity: Final = (
    b"\xb5\x03\x16\x02\x01\x01\x18\x02\x01\x01\x17\x02\x01\x01\xabU"
)
capabilities_several_options: Final = (
    b"\xb5\x05\x14\x02\x01\x06\x43\x02\x01\x01\x30\x02\x01\x01\x42\x02\x01\x01"
    b"\x18\x02\x01\x01\xabU"
)
capabilities_several_options_speed: Final = (
    b"\xb5\x05\x14\x02\x01\x06\x43\x02\x01\x01\x30\x02\x01\x01"
    b"\x25\x02\x01\x01\x02\x11\x12\x21\x22\x31\x18\x02\x01\x01\xabU"
)
capabilities_not_b5: Final = (
    b"\xb3\x03\x16\x02\x01\x01\x18\x02\x01\x01\x17\x02\x01\x01\xabU"
)

capabilities_ac_more: Final = b'\xb5\x03\x1f\x02\x01\x00,\x02\x01\x01\t\x00\x01\x01\x00\x13p\x9b'  # noqa: E501
capabilities_ac_init: Final = b'\xb5\x08\x14\x02\x01\x00\x15\x02\x01\x00\x1e\x02\x01\x00\x17\x02\x01\x02\x1a\x02\x01\x00\x10\x02\x01\x01%\x02\x07 < < <\x00$\x02\x01\x01\x01\x00\xa4\xb0'  # noqa: E501


def test_aircon_device_capabilities(caplog: pytest.LogCaptureFixture):
    appliance = Appliance.instance("34", "ac")
    assert isinstance(appliance, AirConditionerAppliance)

    appliance.process_response_device_capabilities(capabilities_ion)
    assert appliance.capabilities == {"anion": 1, "fan_speed": 7, "humidity": 1, "strong_fan": 1}  # noqa: E501
    appliance.process_response_device_capabilities(capabilities_fan)
    assert appliance.capabilities == {"anion": 1, "fan_speed": 3, "humidity": 1, "filter_check": 1}  # noqa: E501
    appliance.process_response_device_capabilities(capabilities_fahrenheit_filter_check)
    assert appliance.capabilities == {"anion": 1, "fan_speed": 7, "fahrenheit": 1, "heat_8": 1}  # noqa: E501
    appliance.process_response_device_capabilities(capabilities_fan_avoid_ptc_fan_straight)  # noqa: E501
    assert appliance.capabilities == {"ptc": 1, "fan_speed": 7, "fan_straight": 1, "fan_avoid": 1}  # noqa: E501
    appliance.process_response_device_capabilities(capabilities_self_clean_fan_swing)
    assert appliance.capabilities == {"fan_speed": 7, "self_clean": 1, "fan_swing": 1}
    appliance.process_response_device_capabilities(capabilities_electricity)
    assert appliance.capabilities == {"electricity": 1, "no_fan_sense": 1, "filter_reminder": 1}  # noqa: E501
    appliance.process_response_device_capabilities(capabilities_several_options)
    assert appliance.capabilities == {
        "energy_save_on_absence": 1,
        "mode": 6,
        "fa_no_fan_sense": 1,
        "prevent_direct_fan": 1,
        "no_fan_sense": 1,
    }
    appliance.process_response_device_capabilities(capabilities_several_options_speed)
    assert appliance.capabilities == {
        "energy_save_on_absence": 1,
        "mode": 6,
        "no_fan_sense": 1,
        "fa_no_fan_sense": 1,
        "temperature0": 1,
        "temperature1": 2,
        "temperature2": 17,
        "temperature3": 18,
        "temperature4": 33,
        "temperature5": 34,
        "temperature6": 49,
    }
    appliance.process_response_device_capabilities(capabilities_none)
    assert appliance.capabilities == {}
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        appliance.process_response_device_capabilities(capabilities_not_b5)
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "DEBUG"
        assert "Not a B5 response" in caplog.messages[0]
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_no_auto)
    assert appliance.capabilities == {"eco": 1, "screen_display": 1, "fan_speed": 7}
    assert len(caplog.records) == 0
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_unknown)
    assert appliance.capabilities == {"fan_speed": 7, "screen_display": 1}
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "Midea B5 unknown property=b'\\xff\\x02'"
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_unknown_extra)
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "Midea B5 unknown property=b'\\xff\\x01'"
    assert appliance.capabilities == {"fan_speed": 7, "screen_display": 1}
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_ac_init)
    print(binascii.hexlify(capabilities_ac_init))
    assert len(caplog.records) == 0
    caplog.clear()
    appliance.process_response_device_capabilities(capabilities_ac_more)
    print(binascii.hexlify(capabilities_ac_more))
    assert len(caplog.records) == 0


def test_aircon_empty_response(caplog: pytest.LogCaptureFixture):
    appliance = Appliance.instance("34", "ac")
    assert isinstance(appliance, AirConditionerAppliance)
    appliance._online = True
    assert appliance.online
    appliance.process_response(b"")
    assert not appliance.online
    appliance.process_response(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
    )


def test_dump_data(caplog: pytest.LogCaptureFixture):
    appliance = Appliance.instance("34", "ac")
    assert isinstance(appliance, AirConditionerAppliance)
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        very_verbose(True)
        sample_buf: Final = b"012345678\02\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
        appliance.process_response_ext([sample_buf])
        assert len(caplog.records) > len(sample_buf)
        assert any("10  19 13" in m for m in caplog.messages)
        assert any("22   0 00" in m for m in caplog.messages)
    assert appliance.online


def test_process_response_ext(caplog: pytest.LogCaptureFixture):
    appliance = Appliance.instance("34", "ac")
    assert isinstance(appliance, AirConditionerAppliance)
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        sample_buf_02: Final = b"012345678\02\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
        appliance.process_response_ext([sample_buf_02])
        assert not any(r.levelname == "WARNING" for r in caplog.records)
        caplog.clear()
        sample_buf_05: Final = b"012345678\05\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
        appliance.process_response_ext([sample_buf_05])
        assert not any(r.levelname == "WARNING" for r in caplog.records)
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        sample_buf_bad: Final = b"012345678\00\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
        appliance.process_response_ext([sample_buf_bad])
        assert any(r.levelname == "WARNING" for r in caplog.records)
    assert appliance.online
