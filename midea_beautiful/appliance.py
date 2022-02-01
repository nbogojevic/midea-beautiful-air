""" Model for Midea dehumidifier appliances """
from __future__ import annotations

import logging
import sys
from typing import Any

from midea_beautiful.command import (
    AirConditionerResponse,
    AirConditionerSetCommand,
    AirConditionerStatusCommand,
    DehumidifierResponse,
    DehumidifierSetCommand,
    DehumidifierStatusCommand,
    MideaCommand,
)
from midea_beautiful.exceptions import MideaError
from midea_beautiful.midea import AC_MAX_TEMPERATURE, AC_MIN_TEMPERATURE
from midea_beautiful.util import is_very_verbose, Redacted, strtobool

# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods

_LOGGER = logging.getLogger(__name__)


def _as_bool(value: Any) -> bool:
    return strtobool(value) if isinstance(value, str) else bool(value)


def _dump_data(data: bytes):
    if is_very_verbose():
        for i, byte in enumerate(data):
            _LOGGER.debug("%2d %3d %02X", i, byte, byte)


class Appliance:
    """Base model for any Midea appliance"""

    B5_CAPABILITIES = {}

    def __init__(self, appliance_id, appliance_type: str = "") -> None:
        self._id = str(appliance_id)
        self._type = appliance_type
        self._online = False
        self._error: int = 0
        self.latest_data: bytes = b""
        """Last received status packet"""
        self.capabilities = {}
        """Capabilities map of the appliance"""
        self.capabilities_data: bytes = b""
        """Last received capabilities (B5) packet"""

    @staticmethod
    def instance(appliance_id, appliance_type: str = "") -> Appliance:
        """
        Factory method to create an instance of appliance corresponding to
        requested type.
        """
        if DehumidifierAppliance.supported(appliance_type):
            _LOGGER.debug(
                "Creating DehumidifierAppliance %s", Redacted(appliance_id, 4)
            )
            return DehumidifierAppliance(
                appliance_id=appliance_id, appliance_type=appliance_type
            )
        if AirConditionerAppliance.supported(appliance_type):
            _LOGGER.debug(
                "Creating AirConditionerAppliance %s", Redacted(appliance_id, 4)
            )
            return AirConditionerAppliance(
                appliance_id=appliance_id, appliance_type=appliance_type
            )
        _LOGGER.warning("Creating unsupported appliance %s", Redacted(appliance_id, 4))
        return Appliance(appliance_id, appliance_type)

    @staticmethod
    def supported(appliance_type: str | int) -> bool:
        """Returns True if appliance is supported by library"""
        return DehumidifierAppliance.supported(
            appliance_type
        ) or AirConditionerAppliance.supported(appliance_type)

    @staticmethod
    def same_types(type1: str | int, type2: str | int) -> bool:
        """Returns True if two types represent same appliance type"""
        if type1 == type2:
            return True
        if isinstance(type1, int) and Appliance.same_types(hex(type1), type2):
            return True
        if isinstance(type2, int) and Appliance.same_types(type1, hex(type2)):
            return True
        type1 = str(type1).lower()
        type2 = str(type2).lower()
        return type1 == type2 or ("0x" + type1) == type2 or ("0x" + type2) == type1

    @property
    def appliance_id(self) -> str:
        """Appliance id from Midea cloud API"""
        return self._id

    @property
    def name(self) -> str:
        """Appliance name from Midea cloud API"""
        return str(getattr(self, "_name", self._id))

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def type(self) -> str:
        """Appliance type id (e.g. a1 is dehumidifier, ac is air conditioner"""
        return self._type

    @property
    def model(self) -> str:
        """Appliance type id (e.g. Dehumidifier, Air conditioner"""
        return self._type

    @property
    def online(self) -> bool:
        """Is appliance online"""
        return self._online

    @property
    def error_code(self) -> int:
        """Current appliance error code or zero if no errors"""
        return self._error

    def process_response(self, data: bytes) -> None:  # pylint: disable=unused-argument
        """Parses response payload and updates appliance data"""
        _LOGGER.debug("Ignored process_response %s", self)

    def process_response_device_capabilities(self, data: bytes, sequence: int = 0):
        """Parses device capabilities response payload and updates appliance
        supports attribute
        """
        if data:
            self.capabilities_data = data
            if data[0] != 0xB5:
                _LOGGER.debug("Not a B5 response")
                return
            properties_count = data[1]
            i = 2
            if sequence == 0:
                self.capabilities = {}
            for _ in range(properties_count):
                if (step := self.intercept_B5_property(data, i)) >= 0:
                    i += step
                elif attr := self.B5_CAPABILITIES.get(data[i : i + 2]):
                    self.capabilities[attr] = data[i + 3]
                else:
                    _LOGGER.warning("Midea B5 unknown property=%s", data[i : i + 2])
                i += 4

    def intercept_B5_property(self, data: bytes, index: int) -> int:
        """Returns positive integer if properties was processed by implementation,
        otherwise returns number of excess bytes processed on top of minimal
        4 for each property."""
        return -1

    def refresh_command(self) -> MideaCommand:  # pylint: disable=no-self-use
        """Builds refresh/status query command"""
        return MideaCommand()

    def apply_command(self) -> MideaCommand:  # pylint: disable=no-self-use
        """Builds update command"""
        return MideaCommand()

    def __str__(self) -> str:
        return "[UnknownAppliance]{id=%s type=%s}" % (
            Redacted(self.appliance_id, 4),
            self.type,
        )


class DehumidifierAppliance(Appliance):
    """Midea Dehumidifier Appliance model"""

    B5_CAPABILITIES = {
        b"\x10\x02": "fan_speed",
        b"\x14\x02": "mode",
        b"\x17\x02": "filter",
        b"\x1D\x02": "pump",
        b"\x1E\x02": "ion",
        b"\x1F\x02": "auto",
        b"\x20\x02": "dry_clothes",
        b"\x24\x02": "light",
        b"\x2D\x02": "water_level",
    }

    def __init__(self, appliance_id, appliance_type: str = "") -> None:
        super().__init__(appliance_id, appliance_type)

        self._running = False
        self._ion_mode = False
        self._mode = 0
        self._target_humidity = 50
        self._current_humidity = 45
        self._fan_speed = 40
        self._tank_full = False
        self._current_temperature: float = 0
        self._error = 0
        self._defrosting: bool = False
        self._filter_indicator: bool = False
        self._pump: bool = False
        self._sleep: bool = False
        self._beep_prompt: bool = False
        self._tank_level: int = 0
        self._vertical_swing: bool = False
        self._pump_switch_flag: bool = False

    @staticmethod
    def supported(appliance_type: str | int) -> bool:
        lwr = str(appliance_type).lower()
        return (
            lwr == "a1"
            or lwr == "0xa1"
            or appliance_type == 161
            or appliance_type == -95
        )

    def process_response(self, data: bytes) -> None:
        if is_very_verbose():
            _LOGGER.debug(
                "Processing response for dehumidifier id=%s data=%s",
                Redacted(self._id, 4),
                data,
            )
        self.latest_data = data
        if len(data) > 0:
            self._online = True
            _dump_data(data)
            response = DehumidifierResponse(data)
            _LOGGER.debug("DehumidifierResponse %s", response)

            self.running = bool(response.run_status)

            self.ion_mode = response.ion_mode
            self.mode = response.mode
            self.target_humidity = response.target_humidity
            self._current_humidity = response.current_humidity
            self._current_temperature = response.indoor_temperature
            self._defrosting = response.defrosting
            self._error = response.err_code
            self._filter_indicator = response.filter_indicator
            self.pump = response.pump_switch
            self.pump_switch_flag = response.pump_switch_flag
            self.vertical_swing = response.vertical_swing
            self.sleep_mode = response.sleep_switch
            self._tank_full = response.tank_full
            self._tank_level = response.tank_level
            self.fan_speed = response.fan_speed
        else:
            self._online = False

    def refresh_command(self) -> DehumidifierStatusCommand:
        return DehumidifierStatusCommand()

    def apply_command(self) -> DehumidifierSetCommand:
        cmd = DehumidifierSetCommand()
        cmd.beep_prompt = self.beep_prompt
        cmd.fan_speed = self.fan_speed
        cmd.ion_mode = self.ion_mode
        cmd.mode = self.mode
        cmd.pump_switch = self.pump
        cmd.pump_switch_flag = self.pump_switch_flag
        cmd.running = self.running
        cmd.sleep_switch = self.sleep_mode
        cmd.target_humidity = self.target_humidity
        cmd.vertical_swing = self.vertical_swing

        return cmd

    @property
    def tank_full(self) -> bool:
        """Is water tank full"""
        return self._tank_full

    @property
    def tank_level(self) -> int:
        """Water tank level percentage"""
        return self._tank_level

    @property
    def current_humidity(self) -> int:
        """Current ambient humidity"""
        return self._current_humidity

    @property
    def current_temperature(self) -> float:
        """Current ambient temperature"""
        return self._current_temperature

    @property
    def running(self) -> bool:
        """turn on/off"""
        return self._running

    @running.setter
    def running(self, value: bool | int | str) -> None:
        self._running = _as_bool(value)

    @property
    def fan_speed(self) -> int:
        """Current fan speed"""
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, fan_speed: int) -> None:
        fan_speed = int(fan_speed)
        if fan_speed < 0:
            _LOGGER.warning(
                "Tried to set fan speed to less than 0: %s",
                fan_speed,
            )
            self._fan_speed = 0
        elif fan_speed > 127:
            _LOGGER.warning(
                "Tried to set fan speed to greater than 127: %s",
                fan_speed,
            )
            self._fan_speed = 127
        else:
            self._fan_speed = fan_speed

    @property
    def ion_mode(self) -> bool:
        """ion (anion) mode on/off"""
        return self._ion_mode

    @ion_mode.setter
    def ion_mode(self, value: bool | int | str) -> None:
        self._ion_mode = _as_bool(value)

    @property
    def pump_switch_flag(self) -> bool:
        """Pump switch flag - Disables pump"""
        return self._pump_switch_flag

    @pump_switch_flag.setter
    def pump_switch_flag(self, value: bool | int | str) -> None:
        self._pump_switch_flag = _as_bool(value)

    @property
    def vertical_swing(self) -> bool:
        """vertical swing mode on/off"""
        return self._vertical_swing

    @vertical_swing.setter
    def vertical_swing(self, value: bool | int | str) -> None:
        self._vertical_swing = _as_bool(value)

    @property
    def target_humidity(self) -> int:
        """Target humidity"""
        return self._target_humidity

    @target_humidity.setter
    def target_humidity(self, target_humidity: float) -> None:
        target_humidity = float(target_humidity)
        if target_humidity < 0:
            _LOGGER.debug(
                "Tried to set target humidity to less than 0%% value=%s",
                target_humidity,
            )
            self._target_humidity = 0
        elif target_humidity > 100:
            _LOGGER.debug(
                "Tried to set target humidity to greater than 100%% value=%s",
                target_humidity,
            )
            self._target_humidity = 100
        else:
            self._target_humidity = int(target_humidity)

    @property
    def mode(self) -> int:
        """operating mode"""
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        mode = int(mode)
        if 0 <= mode <= 15:
            self._mode = mode
        else:
            raise MideaError(f"Tried to set mode to invalid value: {mode}")

    @property
    def model(self) -> str:
        return "Dehumidifier"

    @property
    def filter_indicator(self) -> bool:
        """Indicator if filters should be cleaned/replaced"""
        return self._filter_indicator

    @property
    def defrosting(self) -> bool:
        """Indicator if dehumidifier is defrosting its circuit"""
        return self._defrosting

    @property
    def pump(self) -> bool:
        """water pump on/off"""
        return self._pump

    @pump.setter
    def pump(self, value: bool | int | str) -> None:
        self._pump = _as_bool(value)

    @property
    def sleep_mode(self) -> bool:
        """sleep mode on/off"""
        return self._sleep

    @sleep_mode.setter
    def sleep_mode(self, value: bool | int | str) -> None:
        self._sleep = _as_bool(value)

    @property
    def beep_prompt(self) -> bool:
        """turn beep prompt on/off"""
        return self._beep_prompt

    @beep_prompt.setter
    def beep_prompt(self, value: bool | int | str) -> None:
        self._beep_prompt = _as_bool(value)

    def __str__(self) -> str:
        return (
            "[Dehumidifier]{id=%s, type=%s, mode=%d,"
            " running=%s,"
            " target_humidity=%d, fan_speed=%d, tank_full=%s"
            " current_humidity=%s, current_temperature=%s"
            " defrosting=%s, filter=%s, tank_level=%s,"
            " error_code=%s, prompt=%s, supports=%s}"
            % (
                Redacted(self.appliance_id, 4),
                self.type,
                self.mode,
                self.running,
                self.target_humidity,
                self.fan_speed,
                self.tank_full,
                self.current_humidity,
                self.current_temperature,
                self.defrosting,
                self.filter_indicator,
                self.tank_level,
                self.error_code,
                self.beep_prompt,
                self.capabilities,
            )
        )


class AirConditionerAppliance(Appliance):
    """Represents Midea air conditioner"""

    B5_CAPABILITIES = {
        b"\x10\x02": "fan_speed",
        b"\x12\x02": "eco",
        b"\x13\x02": "heat_8",
        b"\x14\x02": "mode",
        b"\x15\x02": "fan_swing",
        b"\x16\x02": "electricity",
        b"\x17\x02": "filter_reminder",
        b"\x18\x02": "no_fan_sense",
        b"\x19\x02": "ptc",
        b"\x1E\x02": "anion",
        b"\x1F\x02": "humidity",
        b"\x21\x02": "filter_check",
        b"\x22\x02": "fahrenheit",
        b"\x24\x02": "screen_display",
        b"\x2A\x02": "strong_fan",
        b"\x30\x02": "energy_save_on_absence",
        b"\x32\x02": "fan_straight",
        b"\x33\x02": "fan_avoid",
        b"\x39\x02": "self_clean",
        b"\x42\x02": "prevent_direct_fan",
        b"\x43\x02": "fa_no_fan_sense",
    }

    def __init__(self, appliance_id, appliance_type: str = "") -> None:
        super().__init__(appliance_id, appliance_type)

        self._running = False
        self._mode = 0
        self._fan_speed = 40
        self._target_temperature: float = 0
        self._comfort_sleep: bool = False
        self._eco_mode: bool = False
        self._turbo: bool = False
        self._turbo_fan: bool = False
        self._beep_prompt: bool = False
        self._purifier: bool = False
        self._dryer: bool = False
        self._fahrenheit: bool = False
        self._indoor_temperature: float | None = 0
        self._outdoor_temperature: float | None = 0
        self._vertical_swing: bool = False
        self._horizontal_swing: bool = False
        self._show_screen: bool = True
        self._error: int = 0

    @staticmethod
    def supported(appliance_type: str | int) -> bool:
        lwr = str(appliance_type).lower()
        return (
            lwr == "ac"
            or lwr == "0xac"
            or appliance_type == 172
            or appliance_type == -84
        )

    def process_response(self, data: bytes) -> None:
        if is_very_verbose():
            _LOGGER.debug(
                "Processing response for air conditioner id=%s data=%s",
                Redacted(self._id, 4),
                data,
            )
        self.latest_data = data
        if len(data) > 0:
            self._online = True
            _dump_data(data)
            response = AirConditionerResponse(data)
            _LOGGER.debug("AirConditionerResponse %s", response)

            self._error = response.err_code
            self.comfort_sleep = response.comfort_sleep
            self.fahrenheit = response.fahrenheit
            self.fan_speed = response.fan_speed
            self.horizontal_swing = response.horizontal_swing
            self._indoor_temperature = response.indoor_temperature
            self.mode = response.mode
            self._outdoor_temperature = response.outdoor_temperature
            self.purifier = response.purifier
            self.running = bool(response.run_status)
            self.target_temperature = response.target_temperature
            self.turbo = response.turbo
            self.turbo_fan = response.turbo_fan
            self.vertical_swing = response.vertical_swing
        else:
            self._online = False

    def intercept_B5_property(self, data: bytes, index: int) -> int:
        if data[index : index + 2] == b"\x25\x02":
            for j in range(7):
                self.capabilities[f"temperature{j}"] = data[index + 3 + j]
            return 6
        return -1

    def refresh_command(self) -> AirConditionerStatusCommand:
        return AirConditionerStatusCommand()

    def apply_command(self) -> AirConditionerSetCommand:
        cmd = AirConditionerSetCommand()
        cmd.beep_prompt = self.beep_prompt
        cmd.comfort_sleep = self.comfort_sleep
        cmd.dryer = self.dryer
        cmd.eco_mode = self.eco_mode
        cmd.fahrenheit = self.fahrenheit
        cmd.fan_speed = self.fan_speed
        cmd.horizontal_swing = self.horizontal_swing
        cmd.mode = self.mode
        cmd.purifier = self.purifier
        cmd.running = self.running
        cmd.screen = self.show_screen
        cmd.temperature = self.target_temperature
        cmd.turbo = self.turbo
        cmd.turbo_fan = self.turbo_fan
        cmd.vertical_swing = self.vertical_swing
        return cmd

    @property
    def running(self) -> bool:
        """Is air conditioner running"""
        return self._running

    @running.setter
    def running(self, value: bool | int | str) -> None:
        self._running = _as_bool(value)

    @property
    def target_temperature(self) -> float:
        """A/C target temperature"""
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, temperature: float | str) -> None:
        temperature = float(temperature)
        if AC_MIN_TEMPERATURE <= temperature <= AC_MAX_TEMPERATURE:
            self._target_temperature = temperature
        else:
            raise MideaError(
                f"Tried to set target temperature {temperature} out of allowed range"
            )

    @property
    def outdoor_temperature(self) -> float:
        """
        Current outdoor temperature. If measure not available,
        returns sys.float_info.min
        """
        return self._outdoor_temperature or sys.float_info.min

    @property
    def indoor_temperature(self) -> float:
        """
        Current indoor temperature. If measure not available,
        returns sys.float_info.min
        """
        return self._indoor_temperature or sys.float_info.min

    @property
    def fan_speed(self) -> int:
        """Current fan speed"""
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, fan_speed: int) -> None:
        self._fan_speed = fan_speed

    @property
    def mode(self) -> int:
        """Current operating mode"""
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        mode = int(mode)
        if 0 <= mode <= 15:
            self._mode = mode
        else:
            raise MideaError(f"Tried to set mode to invalid value: {mode}")

    @property
    def eco_mode(self) -> bool:
        """eco mode on/off"""
        return self._eco_mode

    @eco_mode.setter
    def eco_mode(self, value: bool | int | str) -> None:
        self._eco_mode = _as_bool(value)

    @property
    def comfort_sleep(self) -> bool:
        """sleep comfort mode on/off"""
        return self._comfort_sleep

    @comfort_sleep.setter
    def comfort_sleep(self, value: bool | int | str) -> None:
        self._comfort_sleep = _as_bool(value)

    @property
    def turbo_fan(self) -> bool:
        """turbo fan mode on/off"""
        return self._turbo_fan

    @turbo_fan.setter
    def turbo_fan(self, value: bool | int | str) -> None:
        self._turbo_fan = _as_bool(value)

    @property
    def turbo(self) -> bool:
        """turbo (boost) mode on/off"""
        return self._turbo

    @turbo.setter
    def turbo(self, value: bool | int | str) -> None:
        self._turbo = _as_bool(value)

    @property
    def dryer(self) -> bool:
        """dryer mode on/off"""
        return self._dryer

    @dryer.setter
    def dryer(self, value: bool | int | str) -> None:
        self._dryer = _as_bool(value)

    @property
    def purifier(self) -> bool:
        """dryer mode on/off"""
        return self._purifier

    @purifier.setter
    def purifier(self, value: bool | int | str) -> None:
        self._purifier = _as_bool(value)

    @property
    def beep_prompt(self) -> bool:
        """turn beep prompt on/off"""
        return self._beep_prompt

    @beep_prompt.setter
    def beep_prompt(self, value: bool | int | str) -> None:
        self._beep_prompt = _as_bool(value)

    @property
    def vertical_swing(self) -> bool:
        """fan up/down swing on/off"""

        return self._vertical_swing

    @vertical_swing.setter
    def vertical_swing(self, value: bool | int | str):
        self._vertical_swing = _as_bool(value)

    @property
    def horizontal_swing(self) -> bool:
        """fan left/right swing on/off"""
        return self._horizontal_swing

    @horizontal_swing.setter
    def horizontal_swing(self, value: bool | int | str):
        self._horizontal_swing = _as_bool(value)

    @property
    def show_screen(self) -> bool:
        """display on/off"""
        return self._show_screen

    @show_screen.setter
    def show_screen(self, value: bool | int | str) -> None:
        self._show_screen = _as_bool(value)

    @property
    def fahrenheit(self) -> bool:
        """use Fahrenheit degrees"""
        return self._fahrenheit

    @fahrenheit.setter
    def fahrenheit(self, value: bool | int | str) -> None:
        self._fahrenheit = _as_bool(value)

    @property
    def model(self) -> str:
        return "Air conditioner"

    def __str__(self) -> str:
        return (
            "[Air conditioner]{id=%s,"
            " type=%s"
            " mode=%d,"
            " running=%s,"
            " turbo=%s,"
            " fan_speed=%d,"
            " turbo_fan=%s,"
            " purifier=%s,"
            " dryer=%s,"
            " target_temperature=%s,"
            " indoor_temperature=%s,"
            " outdoor_temperature=%s,"
            " vertical_swing=%s"
            " horizontal_swing=%s"
            " comfort_sleep=%s,"
            " error_code=%d,"
            " prompt=%s,"
            " supports=%s}"
            % (
                Redacted(self.appliance_id, 4),
                self.type,
                self.mode,
                self.running,
                self.turbo,
                self.fan_speed,
                self.turbo_fan,
                self.purifier,
                self.dryer,
                self.target_temperature,
                self.indoor_temperature,
                self.outdoor_temperature,
                self.vertical_swing,
                self.horizontal_swing,
                self.comfort_sleep,
                self.error_code,
                self.beep_prompt,
                self.capabilities,
            )
        )
