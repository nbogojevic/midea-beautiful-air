""" Model for midea dehumidifier appliances """
from __future__ import annotations

import logging

from midea_beautiful_dehumidifier.command import (
    DehumidifierResponse,
    DehumidifierSetCommand,
    DehumidifierStatusCommand,
)
from midea_beautiful_dehumidifier.util import hex4log

_LOGGER = logging.getLogger(__name__)


def is_supported_appliance(type: str | int) -> bool:
    lcase = str(type).lower()
    return lcase == "a1" or lcase == "0xa1" or type == 161


class DehumidifierAppliance:
    def __init__(self, id):
        self._id = id
        self._keep_last_known_online_state = False
        self._updating = False
        self._defer_update = False
        self._online = False
        self._active = False
        self._type = "0xA1"
        self.is_on = False
        self.ion_mode = False
        self._mode = 0
        self._target_humidity = 50
        self._current_humidity = 45
        self._fan_speed = 40
        self._err_code = 0
        self._tank_full = False

    def set_appliance_detail(self, details: dict):
        self._id = details["id"]
        self._name = details["name"]
        self._type = details["type"]
        self._active = details["activeStatus"] == "1"
        self._online = details["onlineStatus"] == "1"

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name if hasattr(self, "_name") else self._id

    @property
    def type(self):
        return self._type

    @property
    def active(self):
        return self._active

    @property
    def online(self):
        return self._online

    @property
    def keep_last_known_online_state(self):
        return self._keep_last_known_online_state

    @keep_last_known_online_state.setter
    def keep_last_known_online_state(self, feedback: bool):
        self._keep_last_known_online_state = feedback

    def process_response(self: DehumidifierAppliance, data: bytes):
        _LOGGER.debug(
            "Processing response for dehumidifier id=%s data=%s",
            self._id,
            hex4log(data, _LOGGER),
        )
        if len(data) > 0:
            self._online = True
            self._active = True

            response = DehumidifierResponse(data)
            _LOGGER.debug("Decoded response %s", response)

            self._update(response)
        elif not self._keep_last_known_online_state:
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

    def _update(self: DehumidifierAppliance, response: DehumidifierResponse):
        self.is_on = response.is_on

        self.ion_mode = response.ion_mode
        self.mode = response.mode
        self.target_humidity = response.target_humidity
        self._current_humidity = response.current_humidity
        self.fan_speed = response.fan_speed
        self._err_code = response.err_code
        self._tank_full = response.tank_full

    @property
    def tank_full(self):
        return self._tank_full

    @property
    def current_humidity(self):
        return self._current_humidity

    @property
    def err_code(self):
        return self._err_code

    @property
    def fan_speed(self):
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, fan_speed: int):
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
    def target_humidity(self, target_humidity: int):
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
    def mode(self, mode: int):
        if 0 <= mode and mode <= 15:
            self._mode = mode

    def __str__(self):
        return str(self.__dict__)
