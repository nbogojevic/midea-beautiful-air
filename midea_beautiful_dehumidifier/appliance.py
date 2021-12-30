""" Model for Midea dehumidifier appliances """
from __future__ import annotations

import logging

from distutils.util import strtobool
from typing import Any

from midea_beautiful_dehumidifier.command import (
    DehumidifierResponse,
    DehumidifierSetCommand,
    DehumidifierStatusCommand,
    MideaCommand,
)
from midea_beautiful_dehumidifier.exceptions import MideaError
from midea_beautiful_dehumidifier.util import _Hex

_LOGGER = logging.getLogger(__name__)

# Used when watch mechanism is active
_watch_level: int = 5


def set_watch_level(level: int) -> None:
    global _watch_level
    _watch_level = level


def _as_bool(value: Any) -> bool:
    return strtobool(value) if isinstance(value, str) else bool(value)


class Appliance:
    """Base model for any Midea appliance"""

    def __init__(self, id, appliance_type: str = "") -> None:
        self._id = str(id)
        self._type = appliance_type
        self._online = False
        self._active = False

    @staticmethod
    def instance(id, appliance_type: str = "") -> Appliance:
        """
        Factory method to create an instance of appliance corresponding to
        requested type.
        """
        if Appliance.supported(appliance_type):
            return DehumidifierAppliance(id=id, appliance_type=appliance_type)
        _LOGGER.warning("Creating unsupported appliance %s %s", id, appliance_type)
        return Appliance(id, appliance_type)

    @staticmethod
    def supported(appliance_type: str | int) -> bool:
        return DehumidifierAppliance.supported(appliance_type)

    @staticmethod
    def same_types(type1: str | int, type2: str | int) -> bool:
        if type1 == type2:
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
    def active(self) -> bool:
        return self._active

    @property
    def online(self) -> bool:
        return self._online

    def process_response(self, data: bytes) -> None:
        _LOGGER.debug("Ignored process_response %r", self)
        pass

    def process_response_device_capabilities(self, data: bytes) -> None:
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
        return lwr == "a1" or lwr == "0xa1" or type == 161

    def process_response(self, data: bytes) -> None:
        global _watch_level
        _LOGGER.log(
            _watch_level,
            "Processing response for dehumidifier id=%s data=%s",
            self._id,
            _Hex(data),
        )
        if len(data) > 0:
            self._online = True
            self._active = True
            for i in range(len(data)):
                if _LOGGER.isEnabledFor(_watch_level):
                    _LOGGER.log(
                        _watch_level,
                        f"{i:2} {data[i]:3} {data[i]:02X} {data[i]:08b}",
                    )
            response = DehumidifierResponse(data)
            _LOGGER.debug("Decoded response %s", response)

            self.running = bool(response.run_status)

            self._ion_mode = response.ion_mode
            self.mode = response.mode
            self.target_humidity = response.target_humidity
            self._current_humidity = int(response.current_humidity)
            if self._current_humidity < 0:
                _LOGGER.warning(
                    "Current humidity measurement less than 0%, was %s",
                    response.current_humidity,
                )
                self._current_humidity = 0
            elif self._current_humidity > 100:
                _LOGGER.warning(
                    "Current humidity measurement grater than 100%, was %s",
                    response.current_humidity,
                )
                self._current_humidity = 0
            self.fan_speed = response.fan_speed
            self._tank_full = response.tank_full
            self._tank_level = response.tank_level
            self._current_temperature = response.indoor_temperature
            self._error = response.err_code
            self._defrosting = response.defrosting
            self._filter_indicator = response.filter_indicator
            self._pump = response.pump_switch
            self._sleep = response.sleep_switch
        else:
            self._online = False

    def refresh_command(self) -> DehumidifierStatusCommand:
        return DehumidifierStatusCommand()

    def apply_command(self) -> DehumidifierSetCommand:
        cmd = DehumidifierSetCommand()
        cmd.running = self.running
        cmd.target_humidity = self.target_humidity
        cmd.mode = self.mode
        cmd.fan_speed = self.fan_speed
        cmd.ion_mode = self.ion_mode
        cmd.pump_switch = self.pump
        cmd.sleep_switch = self.sleep
        cmd.beep_prompt = self.beep_prompt
        return cmd

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
                        _LOGGER.debug("property=%x 0x02", data[i])
                else:
                    _LOGGER.debug("property=%x %x", data[i], data[i + 1])
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
        return self._pump

    @pump.setter
    def pump(self, value: bool | int | str) -> None:
        self._pump = _as_bool(value)

    @property
    def sleep(self) -> bool:
        return self._sleep

    @sleep.setter
    def sleep(self, value: bool | int | str) -> None:
        self._sleep = _as_bool(value)

    @property
    def beep_prompt(self) -> bool:
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
                self.error_code,
                self.beep_prompt,
                self.supports,
            )
        )
