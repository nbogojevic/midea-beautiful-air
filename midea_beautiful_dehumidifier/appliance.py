""" Model for Midea dehumidifier appliances """
from __future__ import annotations

import logging

from midea_beautiful_dehumidifier.command import (
    DehumidifierResponse,
    DehumidifierSetCommand,
    DehumidifierStatusCommand,
    MideaCommand,
)

_LOGGER = logging.getLogger(__name__)


class Appliance:
    def __init__(self, id, appliance_type: str = ""):
        self._id = int(id)
        self._type = appliance_type
        self._online = False
        self._active = False

    @staticmethod
    def instance(id, appliance_type: str = "") -> Appliance:
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
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name if hasattr(self, "_name") else self._id

    @name.setter
    def name(self, name) -> None:
        self._name = name

    @property
    def type(self):
        return self._type

    @property
    def model(self):
        return self._type

    @property
    def active(self):
        return self._active

    @property
    def online(self):
        return self._online

    def process_response(self, data: bytes) -> None:
        pass

    def refresh_command(self) -> MideaCommand:
        return MideaCommand()

    def apply_command(self) -> MideaCommand:
        return MideaCommand()

    def __str__(self) -> str:
        return "[UnknownAppliance]{ id: %s type: '%s' }" % (self.id, self.type)


class DehumidifierAppliance(Appliance):
    def __init__(self, id, appliance_type: str = ""):
        super().__init__(id, appliance_type)

        self.is_on = False
        self.ion_mode = False
        self._mode = 0
        self._target_humidity = 50
        self._current_humidity = 45
        self._fan_speed = 40
        self._tank_full = False

    @staticmethod
    def supported(type: str | int) -> bool:
        lwr = str(type).lower()
        return lwr == "a1" or lwr == "0xa1" or type == 161

    def process_response(self, data: bytes):
        _LOGGER.log(
            5,
            "Processing response for dehumidifier id=%s data=%s",
            self._id,
            data,
        )
        if len(data) > 0:
            self._online = True
            self._active = True
            for i in range(len(data)):
                _LOGGER.log(5, "%2d %3d 0x%2x %8s", i, data[i], data[i], bin(data[i]))
            response = DehumidifierResponse(data)
            _LOGGER.debug("Decoded response %s", response)

            self.is_on = response.is_on

            self.ion_mode = response.ion_mode
            self.mode = response.mode
            self.target_humidity = response.target_humidity
            self._current_humidity = response.current_humidity
            self.fan_speed = response.fan_speed
            self._tank_full = response.tank_full

        else:
            self._online = False

    def refresh_command(self) -> DehumidifierStatusCommand:
        return DehumidifierStatusCommand()

    def apply_command(self) -> DehumidifierSetCommand:
        cmd = DehumidifierSetCommand()
        cmd.is_on = self.is_on
        cmd.target_humidity = self.target_humidity
        cmd.mode = self.mode
        cmd.fan_speed = self.fan_speed
        cmd.ion_mode = self.ion_mode
        return cmd

    @property
    def tank_full(self):
        return self._tank_full

    @property
    def current_humidity(self):
        return self._current_humidity

    @property
    def fan_speed(self):
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, fan_speed: int) -> None:
        if fan_speed < 0:
            self._fan_speed = 0
        elif fan_speed > 100:
            self._fan_speed = 100
        else:
            self._fan_speed = fan_speed

    @property
    def target_humidity(self):
        return self._target_humidity

    @target_humidity.setter
    def target_humidity(self, target_humidity: int) -> None:
        if target_humidity < 0:
            self._target_humidity = 0
        elif target_humidity > 100:
            self._target_humidity = 100
        else:
            self._target_humidity = target_humidity

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, mode: int) -> None:
        if 0 <= mode and mode <= 15:
            self._mode = mode

    @property
    def model(self) -> str:
        return "Dehumidifier"

    def __str__(self) -> str:
        return (
            "[Dehumidifier]{ id: %s, type: '%s', mode: %d,"
            " target_humidity: %d, fan_speed: %d, tank_full: %r }"
            % (
                self.id,
                self.type,
                self.mode,
                self.target_humidity,
                self.fan_speed,
                self.tank_full,
            )
        )
