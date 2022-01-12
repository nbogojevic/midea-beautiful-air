"""Test appliance class"""

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
    assert str(appliance) == "[UnknownAppliance]{id=44 type=99}"
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
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
    assert s.mode == 0
    s.mode = 4
    assert s.mode == 4
    with pytest.raises(MideaError) as ex:
        s.mode = 16
    assert ex.value.message == "Tried to set mode to invalid value: 16"
    # Let's test __str__ method
    assert str(ex.value) == "Tried to set mode to invalid value: 16"


def test_dehumidifier_target_humidity():
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
    assert s.target_humidity == 50
    s.target_humidity = 4
    assert s.target_humidity == 4
    s.target_humidity = 5.2
    assert s.target_humidity == 5
    s.target_humidity = -4
    assert s.target_humidity == 0
    s.target_humidity = 100
    assert s.target_humidity == 100
    s.target_humidity = 101
    assert s.target_humidity == 100


def test_dehumidifier_fan():
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
    assert s.fan_speed == 40
    s.fan_speed = 4
    assert s.fan_speed == 4
    s.fan_speed = -4
    assert s.fan_speed == 0
    s.fan_speed = 100
    assert s.fan_speed == 100
    s.fan_speed = 128
    assert s.fan_speed == 127


def test_dehumidifier_beep():
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
    assert not s.beep_prompt
    s.beep_prompt = "on"
    assert s.beep_prompt
    s.beep_prompt = "off"
    assert not s.beep_prompt


def test_dehumidifier_device_capabilities(caplog: pytest.LogCaptureFixture):
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
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
    s.process_response_device_capabilities(capabilities_ion)
    assert s.supports == {"fan_speed": 7, "auto": 1, "dry_clothes": 1, "ion": 1}
    s.process_response_device_capabilities(capabilities_no_ion)
    assert s.supports == {"fan_speed": 7, "auto": 1, "dry_clothes": 1}
    s.process_response_device_capabilities(capabilities_filter)
    assert s.supports == {"fan_speed": 7, "filter": 1, "light": 1}
    s.process_response_device_capabilities(capabilities_filter_pump)
    assert s.supports == {"fan_speed": 7, "filter": 1, "pump": 1}
    s.process_response_device_capabilities(capabilities_level_pump)
    assert s.supports == {"fan_speed": 3, "water_level": 1, "pump": 1}
    s.process_response_device_capabilities(capabilities_mode_pump)
    assert s.supports == {"fan_speed": 3, "mode": 4, "pump": 1}
    caplog.clear()
    s.process_response_device_capabilities(capabilities_no_auto)
    assert s.supports == {"fan_speed": 7, "light": 1, "dry_clothes": 1}
    assert len(caplog.records) == 0
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown)
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "unknown property=FF02"
    assert s.supports == {"fan_speed": 7, "light": 1}
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown_extra)
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "unknown property=FF01"
    assert s.supports == {"fan_speed": 7, "light": 1}


def test_dehumidifier_empty_response():
    s = Appliance.instance("43", "a1")
    assert isinstance(s, DehumidifierAppliance)
    s._online = True
    assert s.online
    s.process_response(b"")
    assert not s.online
    s.process_response(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
    )
    assert s.online


def test_aircon():
    s = Appliance.instance("45", "ac")
    assert isinstance(s, AirConditionerAppliance)


def test_aircon_modes():
    s = Appliance.instance("45", "ac")
    assert isinstance(s, AirConditionerAppliance)
    assert s.mode == 0
    s.mode = 4
    assert s.mode == 4
    with pytest.raises(MideaError) as ex:
        s.mode = 24
    assert ex.value.message == "Tried to set mode to invalid value: 24"


def test_aircon_temperature():
    s = Appliance.instance("45", "ac")
    assert isinstance(s, AirConditionerAppliance)
    assert s.target_temperature == 0
    s.target_temperature = 24
    assert s.target_temperature == 24
    with pytest.raises(MideaError) as ex:
        s.target_temperature = 44
    assert (
        ex.value.message == "Tried to set target temperature 44.0 out of allowed range"
    )


def test_aircon_booleans():
    s = Appliance.instance("45", "ac")
    assert isinstance(s, AirConditionerAppliance)

    assert s.appliance_id == "45"
    assert s.type == "ac"
    s.running = "TRUE"
    assert s.running

    assert not s.eco_mode
    s.eco_mode = "1"
    assert s.eco_mode
    s.eco_mode = "oFf"
    assert not s.eco_mode

    assert not s.turbo_fan
    s.turbo_fan = "1"
    assert s.turbo_fan
    s.turbo_fan = "0"
    assert not s.turbo_fan

    assert not s.comfort_sleep
    s.comfort_sleep = "oN"
    assert s.comfort_sleep
    s.comfort_sleep = "ofF"
    assert not s.comfort_sleep

    assert not s.purifier
    s.purifier = 1
    assert s.purifier
    s.purifier = "off"
    assert not s.purifier

    assert not s.dryer
    s.dryer = "on"
    assert s.dryer
    s.dryer = 0
    assert not s.dryer

    assert not s.fahrenheit
    s.fahrenheit = "t"
    assert s.fahrenheit
    s.fahrenheit = 0
    assert not s.fahrenheit

    # By default show screen
    assert s.show_screen
    s.show_screen = "f"
    assert not s.show_screen
    s.show_screen = "y"
    assert s.show_screen


def test_aircon_swing():
    s = Appliance.instance("45", "ac")
    assert isinstance(s, AirConditionerAppliance)

    assert not s.vertical_swing
    s.vertical_swing = 1
    assert s.vertical_swing
    s.vertical_swing = 0
    assert not s.vertical_swing

    assert not s.horizontal_swing
    s.horizontal_swing = True
    assert s.horizontal_swing
    s.horizontal_swing = 0
    assert not s.horizontal_swing


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


def test_aircon_device_capabilities(caplog: pytest.LogCaptureFixture):
    s = Appliance.instance("34", "ac")
    assert isinstance(s, AirConditionerAppliance)

    s.process_response_device_capabilities(capabilities_ion)
    assert s.supports == {"anion": 1, "fan_speed": 7, "humidity": 1, "strong_fan": 1}
    s.process_response_device_capabilities(capabilities_fan)
    assert s.supports == {"anion": 1, "fan_speed": 3, "humidity": 1, "filter_check": 1}
    s.process_response_device_capabilities(capabilities_fahrenheit_filter_check)
    assert s.supports == {"anion": 1, "fan_speed": 7, "fahrenheit": 1, "heat_8": 1}
    s.process_response_device_capabilities(capabilities_fan_avoid_ptc_fan_straight)
    assert s.supports == {"ptc": 1, "fan_speed": 7, "fan_straight": 1, "fan_avoid": 1}
    s.process_response_device_capabilities(capabilities_self_clean_fan_swing)
    assert s.supports == {"fan_speed": 7, "self_clean": 1, "fan_swing": 1}
    s.process_response_device_capabilities(capabilities_electricity)
    assert s.supports == {"electricity": 1, "no_fan_sense": 1, "filter_reminder": 1}
    s.process_response_device_capabilities(capabilities_several_options)
    assert s.supports == {
        "energy_save_on_absence": 1,
        "mode": 6,
        "fa_no_fan_sense": 1,
        "prevent_direct_fan": 1,
        "no_fan_sense": 1,
    }
    s.process_response_device_capabilities(capabilities_several_options_speed)
    assert s.supports == {
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
    s.process_response_device_capabilities(capabilities_none)
    assert s.supports == {}
    with caplog.at_level(logging.DEBUG):
        caplog.clear()
        s.process_response_device_capabilities(capabilities_not_b5)
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "DEBUG"
        assert caplog.messages[0] == "Not a B5 response"
    caplog.clear()
    s.process_response_device_capabilities(capabilities_no_auto)
    assert s.supports == {"eco": 1, "screen_display": 1, "fan_speed": 7}
    assert len(caplog.records) == 0
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown)
    assert s.supports == {"fan_speed": 7, "screen_display": 1}
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "unknown property=FF02"
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown_extra)
    assert len(caplog.records) == 1
    assert caplog.messages[0] == "unknown property=FF01"
    assert s.supports == {"fan_speed": 7, "screen_display": 1}


def test_aircon_empty_response(caplog: pytest.LogCaptureFixture):
    s = Appliance.instance("34", "ac")
    assert isinstance(s, AirConditionerAppliance)
    s._online = True
    assert s.online
    s.process_response(b"")
    assert not s.online
    s.process_response(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
    )


def test_dump_data(caplog: pytest.LogCaptureFixture):
    s = Appliance.instance("34", "ac")
    assert isinstance(s, AirConditionerAppliance)
    with caplog.at_level(logging.NOTSET):
        caplog.clear()
        sample_buf: Final = b"\x13\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
        s.process_response(sample_buf)
        assert len(caplog.records) > len(sample_buf)
        assert any(r.levelno < logging.DEBUG for r in caplog.records)
        assert any(" 0  19 13" in m for m in caplog.messages)
        assert any("12   0 00" in m for m in caplog.messages)
    assert s.online
