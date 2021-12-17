""" Model for midea dehumidifier appliances """
from __future__ import annotations

import logging

from midea_beautiful_dehumidifier.command import (
    MideaCommand,
    DehumidifierResponse,
    DehumidifierSetCommand,
    DehumidifierStatusCommand,
)

_LOGGER = logging.getLogger(__name__)


class Appliance:
    def __init__(self, id, type: str = ""):
        self._id = id
        self._type = type
        self._online = False
        self._active = False
        self._keep_last_known_online_state = False

    @staticmethod
    def instance(id, type: str = "") -> Appliance:
        if Appliance.supported(type):
            return DehumidifierAppliance(id=id, type=type)
        return Appliance(id, type)

    @staticmethod
    def supported(type: str | int) -> bool:
        lcase = str(type).lower()
        return lcase == "a1" or lcase == "0xa1" or type == 161

    @staticmethod
    def same_types(type1: str | int, type2: str | int) -> bool:
        if type1 == type2:
            return True
        lcase1 = str(type1).lower()
        lcase2 = str(type2).lower()
        return (
            lcase1 == lcase2
            or ("0x" + lcase1) == lcase2
            or ("0x" + lcase2) == lcase1
        )

    def update_info(self, details: dict):
        if self._id != 0 and str(self._id) != str(details["id"]):
            raise ValueError(
                f"Can't change id from {self._id} to {details['id']}"
            )
        self._id = details["id"]
        if not Appliance.same_types(self._type, details["type"]):
            raise ValueError(
                f"Can't change type from {self._type} to {details['type']}"
            )
        self._type = details["type"]
        self._name = details["name"]
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

    def process_response(self, data: bytes):
        pass

    def refresh_command(self) -> MideaCommand:
        return MideaCommand()

    def apply_command(self) -> MideaCommand:
        return MideaCommand()


class DehumidifierAppliance(Appliance):
    def __init__(self, id, type: str = ""):
        super().__init__(id, type)

        self.is_on = False
        self.ion_mode = False
        self._mode = 0
        self._target_humidity = 50
        self._current_humidity = 45
        self._fan_speed = 40
        self._err_code = 0
        self._tank_full = False

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

    def _update(self, response: DehumidifierResponse):
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
