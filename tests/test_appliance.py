import pytest
from midea_beautiful.appliance import (
    AirConditionerAppliance,
    Appliance,
    DehumidifierAppliance,
)
from midea_beautiful.command import MideaCommand
from midea_beautiful.exceptions import MideaError


def test_appliance():
    s = Appliance.instance("44", "99")
    assert s.id == "44"
    assert s.type == "99"
    assert not isinstance(s, DehumidifierAppliance)
    assert not isinstance(s, AirConditionerAppliance)
    assert isinstance(s, Appliance)
    assert str(s) == "[UnknownAppliance]{id=44 type=99}"
    assert s.model == s.type
    assert not s.online
    assert isinstance(s.refresh_command(), MideaCommand)
    assert isinstance(s.apply_command(), MideaCommand)


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
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)

    assert "[Dehumidifier]" in str(s)

    assert s.id == "44"
    assert s.type == "a1"
    assert not s.running
    s.running = "On"
    assert s.running
    s.running = "OFF"
    assert not s.running
    s.running = "true"
    assert s.running
    s.running = "0"
    assert not s.running
    s.running = "true"
    assert s.running
    s.running = "TRUE"
    assert s.running
    with pytest.raises(ValueError):
        s.running = "TRU"


def test_dehumidifier_mode():
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
    assert s.mode == 0
    s.mode = 4
    assert s.mode == 4
    with pytest.raises(MideaError) as ex:
        s.mode = 16
    assert ex.value.message == "Tried to set mode to invalid value: 16"


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


def test_dehumidifier_device_capabilities(caplog):
    s = Appliance.instance("44", "a1")
    assert isinstance(s, DehumidifierAppliance)
    capabilities_no_ion = b"\xb5\x03\x10\x02\x01\x07\x1f\x02\x01\x01 \x02\x01\x01\xcb\\"
    capabilities_ion = b"\xb5\x04\x10\x02\x01\x07\x1e\x02\x01\x01\x1f\x02\x01\x01 \x02\x01\x01\xabU"  # noqa: E501
    capabilities_no_auto = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01 \x02\x01\x01\xcb\\"  # noqa: E501
    )
    capabilities_unknown = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x02\x01\x01\xcb\\"  # noqa: E501
    )
    capabilities_unknown_extra = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x01\x01\x01\xcb\\"  # noqa: E501
    )

    s.process_response_device_capabilities(capabilities_ion)
    assert s.supports == {"fan_speed": 7, "auto": 1, "dry_clothes": 1, "ion": 1}
    s.process_response_device_capabilities(capabilities_no_ion)
    assert s.supports == {"fan_speed": 7, "auto": 1, "dry_clothes": 1}
    caplog.clear()
    s.process_response_device_capabilities(capabilities_no_auto)
    assert s.supports == {"fan_speed": 7, "light": 1, "dry_clothes": 1}
    assert len(caplog.messages) == 0
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown)
    assert len(caplog.messages) == 1
    assert caplog.messages[0] == "unknown property=FF02"
    assert s.supports == {"fan_speed": 7, "light": 1}
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown_extra)
    assert len(caplog.messages) == 1
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

    assert s.id == "45"
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


def test_aircon_device_capabilities(caplog):
    s = Appliance.instance("34", "ac")
    assert isinstance(s, AirConditionerAppliance)
    capabilities_ion = b"\xb5\x04\x10\x02\x01\x07\x1e\x02\x01\x01\x1f\x02\x01\x01\x2a\x02\x01\x01\xabU"  # noqa: E501
    capabilities_no_auto = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\x12\x02\x01\x01\xcb\\"
    )
    capabilities_unknown = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x02\x01\x01\xcb\\"
    )
    capabilities_unknown_extra = (
        b"\xb5\x03\x10\x02\x01\x07\x24\x02\x01\x01\xff\x01\x01\x01\xcb\\"
    )

    s.process_response_device_capabilities(capabilities_ion)
    assert s.supports == {"anion": 1, "fan_speed": 7, "humidity": 1, "strong_fan": 1}
    caplog.clear()
    s.process_response_device_capabilities(capabilities_no_auto)
    assert s.supports == {"eco": 1, "screen_display": 1, "fan_speed": 7}
    assert len(caplog.messages) == 0
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown)
    assert s.supports == {"fan_speed": 7, "screen_display": 1}
    assert len(caplog.messages) == 1
    assert caplog.messages[0] == "unknown property=FF02"
    caplog.clear()
    s.process_response_device_capabilities(capabilities_unknown_extra)
    assert len(caplog.messages) == 1
    assert caplog.messages[0] == "unknown property=FF01"
    assert s.supports == {"fan_speed": 7, "screen_display": 1}


def test_aircon_empty_response():
    s = Appliance.instance("34", "ac")
    assert isinstance(s, AirConditionerAppliance)
    s._online = True
    assert s.online
    s.process_response(b"")
    assert not s.online
    s.process_response(
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"  # noqa: E501
    )
    assert s.online
