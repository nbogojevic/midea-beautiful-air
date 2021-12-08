""" Model for midea devices """
from __future__ import annotations

import logging

from midea_beautiful_dehumidifier.command import (DehumidifierResponse,
                                                  DehumidifierSetCommand,
                                                  DehumidifierStatusCommand)
from midea_beautiful_dehumidifier.util import hex4log
from midea_beautiful_dehumidifier.midea import MideaCommand

_LOGGER = logging.getLogger(__name__)

def is_supported_device(type: str | int) -> bool:
    return str(type).lower() == 'a1' or str(type).lower() == '0xa1' or type == 161

class DehumidifierDevice:

    def __init__(self, id):
        self._id = id
        self._keep_last_known_online_state = False
        self._updating = False
        self._defer_update = False
        self._online = False
        self._active = False
        self._type = "0xA1"
        self._is_on = False
        self._ion_mode = False
        self._mode = 0
        self._target_humidity = 50
        self._current_humidity = 45
        self._fan_speed = 40
        self._err_code = 0
        self._tank_full = False

    def set_device_detail(self, device_detail: dict):
        self._id = device_detail['id']
        self._name = device_detail['name']
        self._type = device_detail['type']
        self._active = device_detail['activeStatus'] == '1'
        self._online = device_detail['onlineStatus'] == '1'

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


    def process_response(self: DehumidifierDevice, data: bytearray):
        _LOGGER.debug("Processing response for dehumidifier id=%s data=%s",
                      self._id, hex4log(data, _LOGGER))
        if len(data) > 0:
            self._online = True
            self._active = True

            response = DehumidifierResponse(data)
            _LOGGER.debug("Decoded response %s", response)
        
            self._update(response)
        elif not self._keep_last_known_online_state:
            self._online = False

    def refresh_command(self) -> MideaCommand:
        return DehumidifierStatusCommand()

    def apply_command(self) -> MideaCommand:
        cmd = DehumidifierSetCommand()
        cmd.is_on = self._is_on
        cmd.target_humidity = self._target_humidity
        cmd.mode = self._mode
        cmd.fan_speed = self._fan_speed
        return cmd

    def _update(self: DehumidifierDevice, response: DehumidifierResponse):
        self._is_on = response.is_on

        self._ion_mode = response.ion_mode
        self._mode = response.mode
        self._target_humidity = response.target_humidity
        self._current_humidity = response.current_humidity
        self._fan_speed = response.fan_speed
        self._err_code = response.err_code
        self._tank_full = response.tank_full

    @property
    def is_on(self):
        return self._is_on

    @property
    def fan_speed(self):
        return self._fan_speed

    @property
    def mode(self):
        return self._mode

    @property
    def tank_full(self):
        return self._tank_full

    @property
    def ion_mode(self):
        return self._ion_mode

    @property
    def current_humidity(self):
        return self._current_humidity

    @property
    def target_humidity(self):
        return self._target_humidity

    @property
    def err_code(self):
        return self._err_code

    def __str__(self):
        return str(self.__dict__)