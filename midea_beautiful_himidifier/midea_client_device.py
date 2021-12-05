from __future__ import annotations

import logging
from enum import Enum

from midea_client_command import (ac_response, ac_set_command,
                                  ac_status_command, base_command,
                                  dehumidifier_response,
                                  dehumidifier_set_command,
                                  dehumidifier_status_command)
from midea_client_service import midea_service
from midea_client_util import hex4logging

VERSION = '0.1.40'

_LOGGER = logging.getLogger(__name__)


class midea_device:

    def __init__(self, service: midea_service):
        self._clear_device_details()
        self._service = service

    def _clear_device_details(self):
        self._id = None
        self._keep_last_known_online_state = False
        self._type = 0xac
        self._updating = False
        self._defer_update = False
        self._support = False
        self._online = True
        self._active = True
        self._protocol_version = 3
        self._support = False

    def set_device_detail(self, device_detail: dict):
        self._clear_device_details()
        self._id = device_detail['id']
        self._name = device_detail['name']
        self._model_number = device_detail['modelNumber']
        self._serial_number = device_detail['sn']
        self._type = int(device_detail['type'], 0)
        self._active = device_detail['activeStatus'] == '1'
        self._online = device_detail['onlineStatus'] == '1'

    def refresh(self):
        cmd = self.refresh_command()
        responses = self._service.status(
            cmd, id=self._id, protocol=self._protocol_version)
        for response in responses:
            _LOGGER.debug("Processing response: %s", response)
            self.process_response(response)

    def refresh_command(self) -> base_command:
        return base_command()

    def process_response(self, response: bytearray):
        pass

    def apply(self):
        pass

    def get_service(self):
        return self._service

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    @property
    def support(self):
        return self._support

    @property
    def model_number(self):
        return self._model_number

    @property
    def serial_number(self):
        return self._serial_number

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


class ac_device(midea_device):

    class fan_speed_enum(Enum):
        Auto = 102
        Full = 100
        High = 80
        Medium = 60
        Low = 40
        Silent = 20

        @staticmethod
        def list():
            return list(map(lambda c: c.name, ac_device.fan_speed_enum))

        @staticmethod
        def get(value):
            if(value in ac_device.fan_speed_enum._value2member_map_):
                return ac_device.fan_speed_enum(value)
            _LOGGER.debug("Unknown Fan Speed: %s", value)
            return ac_device.fan_speed_enum.Auto

    class operational_mode_enum(Enum):
        auto = 1
        cool = 2
        dry = 3
        heat = 4
        fan_only = 5

        @staticmethod
        def list():
            return list(map(lambda c: c.name, ac_device.operational_mode_enum))

        @staticmethod
        def get(value):
            if(value in ac_device.operational_mode_enum._value2member_map_):
                return ac_device.operational_mode_enum(value)
            _LOGGER.debug("Unknown Operational Mode: %s", value)
            return ac_device.operational_mode_enum.fan_only

    class swing_mode_enum(Enum):
        Off = 0x0
        Vertical = 0xC
        Horizontal = 0x3
        Both = 0xF

        @staticmethod
        def list():
            return list(map(lambda c: c.name, ac_device.swing_mode_enum))

        @staticmethod
        def get(value):
            if(value in ac_device.swing_mode_enum._value2member_map_):
                return ac_device.swing_mode_enum(value)
            _LOGGER.debug("Unknown Swing Mode: %s", value)
            return ac_device.swing_mode_enum.Off

    def __init__(self, *args, **kwargs):
        super(ac_device, self).__init__(*args, **kwargs)
        self._prompt_tone = False
        self._power_state = False
        self._target_temperature = 17.0
        self._operational_mode = ac_device.operational_mode_enum.auto
        self._fan_speed = ac_device.fan_speed_enum.Auto
        self._swing_mode = ac_device.swing_mode_enum.Off
        self._eco_mode = False
        self._turbo_mode = False
        # default unit is Celsius.
        # this is just to control the temperatue unit of the AC's display.
        # the target_temperature setter always expects a celcius temperature
        # (resolution of 0.5C), as does the midea API
        self.fahrenheit_unit = False

        self._on_timer = None
        self._off_timer = None
        self._online = True
        self._active = True
        self._indoor_temperature = 0.0
        self._outdoor_temperature = 0.0

        self._half_temp_step = False

    def __str__(self):
        return str(self.__dict__)

    def refresh_command(self):
        return ac_status_command()

    def process_response(self, data: bytearray):
        _LOGGER.debug(
            "Update from %s %s", self.id, hex4logging(data, _LOGGER))
        if len(data) > 0:
            self._online = True
            self._active = True
            if data == b'ERROR':
                self._support = False
                _LOGGER.warn(
                    "Got ERROR from %s", self.id)
                return
            response = ac_response(data)
            self._defer_update = False
            self._support = True
            if not self._defer_update:
                if data[0xa] == 0xc0:
                    self.update(response)
                if data[0xa] == 0xa1 or data[0xa] == 0xa0:
                    # only update indoor_temperature and outdoor_temperature
                    _LOGGER.debug("Update - Special Respone. %s %s",
                                  self.id, 
                                  hex4logging(data[0xa:], _LOGGER))
                    pass
                    # self.update_special(response)
                self._defer_update = False
        elif not self._keep_last_known_online_state:
            self._online = False

    def apply(self):
        self._updating = True
        try:
            cmd = ac_set_command(self.type)
            cmd.prompt_tone = self._prompt_tone
            cmd.power_state = self._power_state
            cmd.target_temperature = self._target_temperature
            cmd.operational_mode = self._operational_mode.value
            cmd.fan_speed = self._fan_speed.value
            cmd.swing_mode = self._swing_mode.value
            cmd.eco_mode = self._eco_mode
            cmd.turbo_mode = self._turbo_mode
            cmd.fahrenheit = self.fahrenheit_unit
            data: bytearray = self._service.apply(
                cmd, id=self._id, protocol=self._protocol_version)
            self.process_response(data)
        finally:
            self._updating = False
            self._defer_update = False

    def update(self, res: ac_response):
        self._power_state = res.power_state
        self._target_temperature = res.target_temperature
        self._operational_mode = ac_device.operational_mode_enum.get(
            res.operational_mode)
        self._fan_speed = ac_device.fan_speed_enum.get(
            res.fan_speed)
        self._swing_mode = ac_device.swing_mode_enum.get(
            res.swing_mode)
        self._eco_mode = res.eco_mode
        self._turbo_mode = res.turbo_mode
        indoor_temperature = res.indoor_temperature
        if indoor_temperature != 0xff:
            self._indoor_temperature = indoor_temperature
        outdoor_temperature = res.outdoor_temperature
        if outdoor_temperature != 0xff:
            self._outdoor_temperature = outdoor_temperature
        self._on_timer = res.on_timer
        self._off_timer = res.off_timer

    def update_special(self, res: ac_response):
        indoor_temperature = res.indoor_temperature
        if indoor_temperature != 0xff:
            self._indoor_temperature = indoor_temperature
        outdoor_temperature = res.outdoor_temperature
        if outdoor_temperature != 0xff:
            self._outdoor_temperature = outdoor_temperature

    @property
    def prompt_tone(self):
        return self._prompt_tone

    @prompt_tone.setter
    def prompt_tone(self, feedback: bool):
        if self._updating:
            self._defer_update = True
        self._prompt_tone = feedback

    @property
    def power_state(self):
        return self._power_state

    @power_state.setter
    def power_state(self, state: bool):
        if self._updating:
            self._defer_update = True
        self._power_state = state

    @property
    def target_temperature(self):
        return self._target_temperature

    @target_temperature.setter
    # the implementation later rounds the temperature down to the nearest 0.5'C resolution.
    def target_temperature(self, temperature_celsius: float):
        if self._updating:
            self._defer_update = True
        self._target_temperature = temperature_celsius

    @property
    def operational_mode(self):
        return self._operational_mode

    @operational_mode.setter
    def operational_mode(self, mode: operational_mode_enum):
        if self._updating:
            self._defer_update = True
        self._operational_mode = mode

    @property
    def fan_speed(self):
        return self._fan_speed

    @fan_speed.setter
    def fan_speed(self, speed: fan_speed_enum):
        if self._updating:
            self._defer_update = True
        self._fan_speed = speed

    @property
    def swing_mode(self):
        return self._swing_mode

    @swing_mode.setter
    def swing_mode(self, mode: swing_mode_enum):
        if self._updating:
            self._defer_update = True
        self._swing_mode = mode

    @property
    def eco_mode(self):
        return self._eco_mode

    @eco_mode.setter
    def eco_mode(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._eco_mode = enabled

    @property
    def turbo_mode(self):
        return self._turbo_mode

    @turbo_mode.setter
    def turbo_mode(self, enabled: bool):
        if self._updating:
            self._defer_update = True
        self._turbo_mode = enabled

    @property
    def indoor_temperature(self):
        return self._indoor_temperature

    @property
    def outdoor_temperature(self):
        return self._outdoor_temperature

    @property
    def on_timer(self):
        return self._on_timer

    @property
    def off_timer(self):
        return self._off_timer


class unknown_device(midea_device):

    def __init__(self, service: midea_service):
        super().__init__(service)

    def refresh_command(self):
        return base_command(self.type)

    def process_response(self, data: bytearray):
        if len(data) > 0:
            self._online = True
            response = ac_response(data)
            _LOGGER.warning("Decoded Data: %s", {
                'target_temperature': response.target_temperature,
                'indoor_temperature': response.indoor_temperature,
                'outdoor_temperature': response.outdoor_temperature,
                'operational_mode': response.operational_mode,
                'fan_speed': response.fan_speed,
                'swing_mode': response.swing_mode,
                'eco_mode': response.eco_mode,
                'turbo_mode': response.turbo_mode
            })
        elif not self._keep_last_known_online_state:
            self._online = False

    def apply(self):
        _LOGGER.warning(
            "Cannot apply, device is not fully supported yet type=%s", self._type)


class dehumidifier_device(midea_device):

    def __init__(self, service: midea_service):
        super().__init__(service)

    def set_device_detail(self, device_detail: dict):
        self._clear_device_details()
        super().set_device_detail(device_detail)

    def _clear_device_details(self):
        super()._clear_device_details()

        self._type = 0xA1
        self._is_on = False
        self._ion_mode = False
        self._mode = 0
        self._target_humidity = 50
        self._current_humidity = 45
        self._fan_speed = 40
        self._err_code = 0
        self._tank_full = False

    def process_response(self: dehumidifier_device, data: bytearray):
        _LOGGER.debug("Processing response for dehumidifier %s", data)
        if len(data) > 0:
            self._online = True
            self._active = True
            self._support = True

            if not self._defer_update:
                _LOGGER.debug("process_response: %s",
                              hex4logging(data, _LOGGER))
                response = dehumidifier_response(data)
                self._update(response)
                self._defer_update = False
        elif not self._keep_last_known_online_state:
            self._online = False

    def refresh_command(self) -> base_command:
        return dehumidifier_status_command()

    def apply(self: dehumidifier_device):
        self._updating = True
        try:
            cmd = dehumidifier_set_command()
            cmd.is_on = self._is_on
            cmd.target_humidity = self._target_humidity
            cmd.mode = self._mode
            cmd.fan_speed = self._fan_speed

            data: bytearray = self._service.apply(
                cmd, id=self._id, protocol=self._protocol_version)
            self.process_response(data)
        finally:
            self._updating = False
            self._defer_update = False

    def _update(self: dehumidifier_device, response: dehumidifier_response):
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


def device_from_type(type: str | int, service: midea_service) -> midea_device:
    if str(type).lower() == 'ac' or str(type).lower() == '0xac' or type == 172:
        return ac_device(service)
    if str(type).lower() == 'a1' or str(type).lower() == '0xa1' or type == 161:
        return dehumidifier_device(service)
    return unknown_device(service)


def device_name_from_type(type: str | int) -> str:
    if str(type).lower() == 'ac' or str(type).lower() == '0xac' or type == 172:
        return 'air_conditioning'
    if str(type).lower() == 'a1' or str(type).lower() == '0xa1' or type == 161:
        return 'dehumidifier'
    return f"unknown({type})"
