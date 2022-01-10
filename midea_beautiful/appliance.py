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
from midea_beautiful.util import SPAM, TRACE, strtobool

_LOGGER = logging.getLogger(__name__)


def _as_bool(value: Any) -> bool:
    return strtobool(value) if isinstance(value, str) else bool(value)


def _dump_data(data: bytes):
    if _LOGGER.isEnabledFor(SPAM):
        for i in range(len(data)):
            _LOGGER.log(SPAM, "%2d %3d %02X", i, data[i], data[i])


class Appliance:
    """Base model for any Midea appliance"""

    def __init__(self, id, appliance_type: str = "") -> None:
        self._id = str(id)
        self._type = appliance_type
        self._online = False

    @staticmethod
    def instance(id, appliance_type: str = "") -> Appliance:
        """
        Factory method to create an instance of appliance corresponding to
        requested type.
        """
        if DehumidifierAppliance.supported(appliance_type):
            _LOGGER.log(
                TRACE, "Creating DehumidifierAppliance %s %s", id, appliance_type
            )
            return DehumidifierAppliance(id=id, appliance_type=appliance_type)
        if AirConditionerAppliance.supported(appliance_type):
            _LOGGER.log(
                TRACE, "Creating AirConditionerAppliance %s %s", id, appliance_type
            )
            return AirConditionerAppliance(id=id, appliance_type=appliance_type)
        _LOGGER.warning("Creating unsupported appliance %s %s", id, appliance_type)
        return Appliance(id, appliance_type)

    @staticmethod
    def supported(appliance_type: str | int) -> bool:
        return DehumidifierAppliance.supported(
            appliance_type
        ) or AirConditionerAppliance.supported(appliance_type)

    @staticmethod
    def same_types(type1: str | int, type2: str | int) -> bool:
        if type1 == type2:
            return True
        if isinstance(type1, int):
            if Appliance.same_types(hex(type1), type2):
                return True
        if isinstance(type2, int):
            if Appliance.same_types(type1, hex(type2)):
                return True
        t1 = str(type1).lower()
        t2 = str(type2).lower()
        return t1 == t2 or ("0x" + t1) == t2 or ("0x" + t2) == t1

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return str(getattr(self, "_name", self._id))

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def type(self) -> str:
        return self._type

    @property
    def model(self) -> str:
        return self._type

    @property
    def online(self) -> bool:
        return self._online

    def process_response(self, data: bytes) -> None:
        _LOGGER.debug("Ignored process_response %r", self)
        pass

    def process_response_device_capabilities(
        self, data: bytes, sequence: int = 0
    ) -> None:
        _LOGGER.debug("Ignored process_response_device_capabilities %r", self)
        pass

    def refresh_command(self) -> MideaCommand:
        return MideaCommand()

    def apply_command(self) -> MideaCommand:
        return MideaCommand()

    def __str__(self) -> str:
        return "[UnknownAppliance]{id=%s type=%s}" % (self.id, self.type)


class DehumidifierAppliance(Appliance):
    def __init__(self, id, appliance_type: str = "") -> None:
        super().__init__(id, appliance_type)

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
        self.supports = {}

    @staticmethod
    def supported(type: str | int) -> bool:
        lwr = str(type).lower()
        return lwr == "a1" or lwr == "0xa1" or type == 161 or type == -95

    def process_response(self, data: bytes) -> None:
        _LOGGER.log(
            SPAM,
            "Processing response for dehumidifier id=%s data=%s",
            self._id,
            data,
        )
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
        cmd.running = self.running
        cmd.sleep_switch = self.sleep_mode
        cmd.target_humidity = self.target_humidity
        return cmd

    def process_response_device_capabilities(self, data: bytes, sequence: int = 0):
        if data:
            if data[0] != 0xB5:
                _LOGGER.debug("Not a B5 response")
                return
            properties_count = data[1]
            i = 2
            if sequence == 0:
                self.supports = {}
            for _ in range(properties_count):
                if data[i + 1] == 0x02:
                    if data[i] == 0x20:
                        self.supports["dry_clothes"] = data[i + 3]
                    elif data[i] == 0x1F:
                        self.supports["auto"] = data[i + 3]
                    elif data[i] == 0x10:
                        self.supports["fan_speed"] = data[i + 3]
                    elif data[i] == 0x1E:
                        self.supports["ion"] = data[i + 3]
                    elif data[i] == 0x17:
                        self.supports["filter"] = data[i + 3]
                    elif data[i] == 0x1D:
                        self.supports["pump"] = data[i + 3]
                    elif data[i] == 0x2D:
                        self.supports["water_level"] = data[i + 3]
                    elif data[i] == 0x14:
                        self.supports["mode"] = data[i + 3]
                    elif data[i] == 0x24:
                        self.supports["light"] = data[i + 3]
                    else:
                        _LOGGER.warning("unknown property=%02X02", data[i])
                else:
                    _LOGGER.warning("unknown property=%02X%02X", data[i], data[i + 1])
                i += 4

    @property
    def tank_full(self) -> bool:
        return self._tank_full

    @property
    def tank_level(self) -> int:
        return self._tank_level

    @property
    def current_humidity(self) -> int:
        return self._current_humidity

    @property
    def current_temperature(self) -> float:
        return self._current_temperature

    @property
    def error_code(self) -> int:
        return self._error

    @property
    def running(self) -> bool:
        """turn on/off"""
        return self._running

    @running.setter
    def running(self, value: bool | int | str) -> None:
        self._running = _as_bool(value)

    @property
    def fan_speed(self) -> int:
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
    def target_humidity(self) -> int:
        return self._target_humidity

    @target_humidity.setter
    def target_humidity(self, target_humidity: float) -> None:
        target_humidity = float(target_humidity)
        if target_humidity < 0:
            _LOGGER.debug(
                "Tried to set target humidity to less than 0%: %s",
                target_humidity,
            )
            self._target_humidity = 0
        elif target_humidity > 100:
            _LOGGER.debug(
                "Tried to set target humidity to greater than 100%: %s",
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
        if 0 <= mode and mode <= 15:
            self._mode = mode
        else:
            raise MideaError(f"Tried to set mode to invalid value: {mode}")

    @property
    def model(self) -> str:
        return "Dehumidifier"

    @property
    def filter_indicator(self) -> bool:
        return self._filter_indicator

    @property
    def defrosting(self) -> bool:
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
            " defrosting=%s, filter=%s, tank_level=%s, "
            " error_code=%s, prompt=%s, supports=%s}"
            % (
                self.id,
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
                self.supports,
            )
        )


class AirConditionerAppliance(Appliance):
    def __init__(self, id, appliance_type: str = "") -> None:
        super().__init__(id, appliance_type)

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
        self.supports = {}

    @staticmethod
    def supported(type: str | int) -> bool:
        lwr = str(type).lower()
        return lwr == "ac" or lwr == "0xac" or type == 172 or type == -84

    def process_response(self, data: bytes) -> None:
        _LOGGER.log(
            SPAM,
            "Processing response for air conditioner id=%s data=%s",
            self._id,
            data,
        )
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

    def process_response_device_capabilities(self, data: bytes):
        if data:
            if data[0] != 0xB5:
                _LOGGER.debug("Not a B5 response")
                return
            properties_count = data[1]
            i = 2
            self.supports = {}
            for _ in range(properties_count):
                if data[i + 1] == 0x02:
                    if data[i] == 0x14:
                        self.supports["mode"] = data[i + 3]
                    elif data[i] == 0x2A:
                        self.supports["strong_fan"] = data[i + 3]
                    elif data[i] == 0x1F:
                        self.supports["humidity"] = data[i + 3]
                    elif data[i] == 0x10:
                        self.supports["fan_speed"] = data[i + 3]
                    elif data[i] == 0x25:
                        for j in range(7):
                            self.supports[f"temperature{j}"] = data[i + 3 + j]
                        i += 6
                    elif data[i] == 0x12:
                        self.supports["eco"] = data[i + 3]
                    elif data[i] == 0x17:
                        self.supports["filter_reminder"] = data[i + 3]
                    elif data[i] == 0x21:
                        self.supports["filter_check"] = data[i + 3]
                    elif data[i] == 0x22:
                        self.supports["fahrenheit"] = data[i + 3]
                    elif data[i] == 0x13:
                        self.supports["heat_8"] = data[i + 3]
                    elif data[i] == 0x16:
                        self.supports["electricity"] = data[i + 3]
                    elif data[i] == 0x19:
                        self.supports["ptc"] = data[i + 3]
                    elif data[i] == 0x32:
                        self.supports["fan_straight"] = data[i + 3]
                    elif data[i] == 0x33:
                        self.supports["fan_avoid"] = data[i + 3]
                    elif data[i] == 0x15:
                        self.supports["fan_swing"] = data[i + 3]
                    elif data[i] == 0x18:
                        self.supports["no_fan_sense"] = data[i + 3]
                    elif data[i] == 0x24:
                        self.supports["screen_display"] = data[i + 3]
                    elif data[i] == 0x1E:
                        self.supports["anion"] = data[i + 3]
                    elif data[i] == 0x39:
                        self.supports["self_clean"] = data[i + 3]
                    elif data[i] == 0x43:
                        self.supports["fa_no_fan_sense"] = data[i + 3]
                    elif data[i] == 0x30:
                        self.supports["energy_save_on_absence"] = data[i + 3]
                    elif data[i] == 0x42:
                        self.supports["prevent_direct_fan"] = data[i + 3]
                    else:
                        _LOGGER.warning("unknown property=%02X02", data[i])
                else:
                    _LOGGER.warning("unknown property=%02X%02X", data[i], data[i + 1])
                i += 4

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
        return self._running

    @running.setter
    def running(self, value: bool | int | str) -> None:
        self._running = _as_bool(value)

    @property
    def target_temperature(self) -> float:
        return self._target_temperature

    @target_temperature.setter
    def target_temperature(self, temperature: float | str) -> None:
        temperature = float(temperature)
        if temperature < AC_MIN_TEMPERATURE or temperature > AC_MAX_TEMPERATURE:
            raise MideaError(
                f"Tried to set target temperature {temperature} out of allowed range"
            )
        else:
            self._target_temperature = temperature

    @property
    def outdoor_temperature(self) -> float:
        return self._outdoor_temperature or sys.float_info.min

    @property
    def indoor_temperature(self) -> float:
        return self._indoor_temperature or sys.float_info.min

    @property
    def fan_speed(self) -> int:
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, fan_speed: int) -> None:
        self._fan_speed = fan_speed

    @property
    def mode(self) -> int:
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        mode = int(mode)
        if 0 <= mode and mode <= 15:
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
        return self._turbo_fan

    @turbo_fan.setter
    def turbo_fan(self, value: bool | int | str) -> None:
        """turbo fan mode on/off"""
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

    @property
    def error_code(self) -> int:
        return self._error

    def __str__(self) -> str:
        return (
            "[Air conditioner]{id=%s, type=%s, "
            " mode=%d,"
            " running=%s,"
            " turbo=%s,"
            " fan_speed=%d, "
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
            " prompt=%s, supports=%s}"
            % (
                self.id,
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
                self.supports,
            )
        )
