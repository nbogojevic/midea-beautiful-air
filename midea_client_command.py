from __future__ import annotations

import logging
from midea_client_util import crc8, hex4logging

VERSION = '0.1.40'

_LOGGER = logging.getLogger(__name__)

_order = 0


class base_command:

    def __init__(self, device_type=0xAC):
        # Command structure
        self.data = bytearray([
            # 0 header
            0xaa,
            # 1 command lenght: N+10
            0x20,
            # 2 device type 0xAC - airconditioning, 0xA1 - dehumidifier
            device_type,
            # 3 Frame SYN CheckSum
            0x00,
            # 4-5 Reserved
            0x00, 0x00,
            # 6 Message ID
            0x00,
            # 7 Frame Protocol Version
            0x00,
            # 8 Device Protocol Version
            0x03,
            # 9 Messgae Type: request is 0x03; setting is 0x02
            0x03,
            # Byte0 - Data request/response type:
            # 0x41 - check status;
            # 0x40 - Set up
            0x41,
            # Byte1
            0x81,
            # Byte2 - operational_mode
            0x00,
            # Byte3
            0xff,
            # Byte4
            0x03,
            # Byte5
            0xff,
            # Byte6
            0x00,
            # Byte7 - Room Temperature Request:
            # 0x02 - indoor_temperature,
            # 0x03 - outdoor_temperature
            # when set, this is swing_mode
            0x02,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            # Message ID
            0x00,
            # CRC8
            0x00,
            # Checksum
            0x00
        ])
        self.data[0x02] = device_type

    def _checksum(self, data):
        return (~ sum(data) + 1) & 0xff

    def finalize(self):
        global _order
        _order = (_order + 1) & 0xff
        self.data[30] = _order
        # Add the CRC8
        self.data[31] = crc8(self.data[10:31])
        # Add checksum
        self.data[32] = self._checksum(self.data[1:32])

        return self.data


class ac_set_command(base_command):

    def __init__(self, device_type):
        base_command.__init__(self, device_type)
        self.data[0x01] = 0x23
        self.data[0x09] = 0x02
        # Set up Mode
        self.data[0x0a] = 0x40
        # prompt_tone
        self.data[0x0b] = 0x40
        self.data.extend(bytearray([0x00, 0x00, 0x00]))

    @property
    def prompt_tone(self):
        return self.data[0x0b] & 0x42

    @prompt_tone.setter
    def prompt_tone(self, feedback_anabled: bool):
        self.data[0x0b] &= ~ 0x42  # Clear the audible bits
        self.data[0x0b] |= 0x42 if feedback_anabled else 0

    @property
    def power_state(self):
        return self.data[0x0b] & 0x01

    @power_state.setter
    def power_state(self, state: bool):
        self.data[0x0b] &= ~ 0x01  # Clear the power bit
        self.data[0x0b] |= 0x01 if state else 0

    @property
    def target_temperature(self):
        return self.data[0x0c] & 0x1f

    @target_temperature.setter
    def target_temperature(self, temperature_celsius: float):
        # Clear the temperature bits.
        self.data[0x0c] &= ~ 0x0f
        # Clear the temperature bits, except the 0.5 bit,
        # which will be set properly in all cases
        self.data[0x0c] |= (int(temperature_celsius) & 0xf)
        # set the +0.5 bit
        self.temperature_dot5 = (int(round(temperature_celsius*2)) % 2 != 0)

    @property
    def operational_mode(self):
        return (self.data[0x0c] & 0xe0) >> 5

    @operational_mode.setter
    def operational_mode(self, mode: int):
        self.data[0x0c] &= ~ 0xe0  # Clear the mode bit
        self.data[0x0c] |= (mode << 5) & 0xe0

    @property
    def fan_speed(self):
        return self.data[0x0d]

    @fan_speed.setter
    def fan_speed(self, speed: int):
        self.data[0x0d] = speed

    @property
    def eco_mode(self):
        return self.data[0x13] > 0

    @eco_mode.setter
    def eco_mode(self, eco_mode_enabled: bool):
        self.data[0x13] = 0xFF if eco_mode_enabled else 0

    @property
    def swing_mode(self):
        return self.data[0x11]

    @swing_mode.setter
    def swing_mode(self, mode: int):
        self.data[0x11] = 0x30  # Clear the mode bit
        self.data[0x11] |= mode & 0x3f

    @property
    def turbo_mode(self):
        return self.data[0x14] > 0

    @turbo_mode.setter
    def turbo_mode(self, turbo_mode_enabled: bool):
        if (turbo_mode_enabled):
            self.data[0x14] |= 0x02
        else:
            self.data[0x14] &= (~0x02)

    @property
    def screen_display(self):
        return self.data[0x14] & 0x10 > 0

    @screen_display.setter
    def screen_display(self, screen_display_enabled: bool):
        # the LED lights on the AC. these display temperature and are
        # often too bright during nights
        if screen_display_enabled:
            self.data[0x14] |= 0x10
        else:
            self.data[0x14] &= (~0x10)

    @property
    def temperature_dot5(self):
        return self.data[0x0c] & 0x10 > 0

    @temperature_dot5.setter
    def temperature_dot5(self, temperature_dot5_enabled: bool):
        # add 0.5C to the temperature value.
        # not intended to be called directly.
        # target_temperature setter calls this if needed
        if temperature_dot5_enabled:
            self.data[0x0c] |= 0x10
        else:
            self.data[0x0c] &= (~0x10)

    @property
    def fahrenheit(self):
        # is the temperature unit fahrenheit? (celcius otherwise)
        return self.data[0x14] & 0x04 > 0

    @fahrenheit.setter
    def fahrenheit(self, fahrenheit_enabled: bool):
        # set the unit to fahrenheit from celcius
        if fahrenheit_enabled:
            self.data[0x14] |= 0x04
        else:
            self.data[0x14] &= (~0x04)


class ac_response:

    def __init__(self, data: bytearray):
        # The response data from the appliance includes a
        #  packet header which we don't want
        self.data = data[0xa:]
        _LOGGER.debug("Appliance response data: %s", hex4logging(self.data))

    # Byte 0x01
    @property
    def power_state(self):
        return (self.data[0x01] & 0x1) > 0

    @property
    def imode_resume(self):
        return (self.data[0x01] & 0x4) > 0

    @property
    def timer_mode(self):
        return (self.data[0x01] & 0x10) > 0

    @property
    def appliance_error(self):
        return (self.data[0x01] & 0x80) > 0

    # Byte 0x02
    @property
    def target_temperature(self):
        return ((self.data[0x02] & 0xf) + 16.0
                + (0.5 if self.data[0x02] & 0x10 > 0 else 0.0))

    @property
    def operational_mode(self):
        return (self.data[0x02] & 0xe0) >> 5

    # Byte 0x03
    @property
    def fan_speed(self):
        return self.data[0x03] & 0x7f

    # Byte 0x04 + 0x06
    @property
    def on_timer(self):
        on_timer_value = self.data[0x04]
        on_timer_minutes = self.data[0x06]
        return {
            'status': ((on_timer_value & 0x80) >> 7) > 0,
            'hour': (on_timer_value & 0x7c) >> 2,
            'minutes': ((on_timer_value & 0x3)
                        | ((on_timer_minutes & 0xf0) >> 4))
        }

    # Byte 0x05 + 0x06
    @property
    def off_timer(self):
        off_timer_value = self.data[0x05]
        off_timer_minutes = self.data[0x06]
        return {
            'status': ((off_timer_value & 0x80) >> 7) > 0,
            'hour': (off_timer_value & 0x7c) >> 2,
            'minutes': (off_timer_value & 0x3) | (off_timer_minutes & 0xf)
        }

    # Byte 0x07
    @property
    def swing_mode(self):
        return self.data[0x07] & 0x0f

    # Byte 0x08
    @property
    def cozy_sleep(self):
        return self.data[0x08] & 0x03

    @property
    def save(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x08] & 0x08) > 0

    @property
    def low_frequency_fan(self):
        return (self.data[0x08] & 0x10) > 0

    @property
    def super_fan(self):
        return (self.data[0x08] & 0x20) > 0

    @property
    def feel_own(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x08] & 0x80) > 0

    # Byte 0x09
    @property
    def child_sleep_mode(self):
        return (self.data[0x09] & 0x01) > 0

    @property
    def exchange_air(self):
        return (self.data[0x09] & 0x02) > 0

    @property
    def dry_clean(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x09] & 0x04) > 0

    @property
    def aux_heat(self):
        return (self.data[0x09] & 0x08) > 0

    @property
    def eco_mode(self):
        return (self.data[0x09] & 0x10) > 0

    @property
    def clean_up(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x09] & 0x20) > 0

    @property
    def temp_unit(self):  # This needs a better name, dunno what it actually means
        return (self.data[0x09] & 0x80) > 0

    # Byte 0x0a
    @property
    def sleep_function(self):
        return (self.data[0x0a] & 0x01) > 0

    @property
    def turbo_mode(self):
        return (self.data[0x0a] & 0x02) > 0

    @property
    def catch_cold(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x08) > 0

    @property
    def night_light(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x10) > 0

    @property
    def peak_elec(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x20) > 0

    @property
    def natural_fan(self):   # This needs a better name, dunno what it actually means
        return (self.data[0x0a] & 0x40) > 0

    # Byte 0x0b
    @property
    def indoor_temperature(self):
        indoorTempInteger = 0
        indoorTempDecimal = 0
        if self.data[0] == 0xc0:
            if (int((self.data[11] - 50) / 2) < -19
                    or int((self.data[11] - 50) / 2) > 50):
                return 0xff
            else:
                indoorTempInteger = int((self.data[11] - 50) / 2)
            indoorTemperatureDot = getBits(self.data, 15, 0, 3)
            indoorTempDecimal = indoorTemperatureDot * 0.1
            if self.data[11] > 49:
                return indoorTempInteger + indoorTempDecimal
            else:
                return indoorTempInteger - indoorTempDecimal
        if self.data[0] == 0xa0 or self.data[0] == 0xa1:
            if self.data[0] == 0xa0:
                if (self.data[1] >> 2) - 4 == 0:
                    indoorTempInteger = -1
                else:
                    indoorTempInteger = (self.data[1] >> 2) + 12
                if (self.data[1] >> 1) & 0x01 == 1:
                    indoorTempDecimal = 0.5
                else:
                    indoorTempDecimal = 0
            if self.data[0] == 0xa1:
                if (int((self.data[13] - 50) / 2) < -19
                        or int((self.data[13] - 50) / 2) > 50):
                    return 0xff
                else:
                    indoorTempInteger = int((self.data[13] - 50) / 2)
                indoorTempDecimal = (self.data[18] & 0x0f) * 0.1
            if indoorTempInteger and int(self.data[13]) > 49:
                return indoorTempInteger + indoorTempDecimal
            else:
                return indoorTempInteger - indoorTempDecimal
        return 0xff

    # Byte 0x0c
    @property
    def outdoor_temperature(self):
        return (self.data[0x0c] - 50) / 2.0

    # Byte 0x0d
    @property
    def humidity(self):
        return (self.data[0x0d] & 0x7f)


def getBit(pByte, pIndex):
    return (pByte >> pIndex) & 0x01


def getBits(pBytes, pIndex, pStartIndex, pEndIndex):
    if pStartIndex > pEndIndex:
        StartIndex = pEndIndex
        EndIndex = pStartIndex
    else:
        StartIndex = pStartIndex
        EndIndex = pEndIndex
    tempVal = 0x00
    i = StartIndex
    while (i <= EndIndex):
        tempVal = tempVal | getBit(pBytes[pIndex], i) << (i-StartIndex)
        i += 1
    return tempVal


class dehumidifier_status_command(base_command):

    def __init__(self, device_type: int = 0xA1):
        super().__init__(device_type)

class ac_status_command(base_command):

    def __init__(self, device_type: int = 0xAC):
        super().__init__(device_type)

class dehumidifier_set_command(base_command):

    def __init__(self: dehumidifier_set_command):
        self.data: bytearray = bytearray([
            0xaa, 0x00, 0xA1, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x03, 0x03, 0x48, 0x21, 0x00, 0xff, 0x03, 0x00,
            0x00, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        ])

    def set_order(self: dehumidifier_set_command, order):
        self.data[0x1e] = order

    def finalize(self: dehumidifier_set_command):
        global _order
        _order = (_order + 1) & 0xff
        # Add the CRC8
        self.data[0x1f] = crc8(self.data[10:31])
        # Set the length of the command data
        self.data[0x01] = len(self.data)
        return self.data

    @property
    def is_on(self):
        return self.data[0x0b] & 0x01 != 0

    @is_on.setter
    def is_on(self, state: bool):
        self.data[0x0b] &= ~ 0x01  # Clear the power bit
        self.data[0x0b] |= 0x01 if state else 0

    @property
    def ion_mode(self):
        return self.data[0x0b] & 0x01

    @ion_mode.setter
    def ion_mode(self, mode: bool):
        self.data[0x0b] &= ~ 0x01  # Clear the power bit
        self.data[0x0b] |= 0x01 if mode else 0

    @property
    def target_humidity(self):
        return self.data[0x11] & 0x7f

    @target_humidity.setter
    def target_humidity(self, humidity: int):
        self.data[0x11] &= ~ 0x7f  # Clear the power bit
        self.data[0x1] |= humidity

    @property
    def mode(self):
        return self.data[0x0c] & 0x0f

    @mode.setter
    def mode(self, mode: int):
        self.data[0x0c] &= ~ 0x0f  # Clear the power bit
        self.data[0x0c] |= mode

    @property
    def fan_speed(self):
        return self.data[0x0d] & 0x7f

    @fan_speed.setter
    def fan_speed(self, speed: int):
        self.data[0x0d] &= ~ 0x7f  # Clear the power bit
        self.data[0x0d] |= speed


class dehumidifier_response:

    def __init__(self: dehumidifier_response, data: bytearray):
        # The response data from the appliance includes
        # a packet header which we don't want
        _LOGGER.debug("dehumidifier_response: payload: %s",
                      hex4logging(data, _LOGGER))

        # self.faultFlag = (data[1] & 0x80) >> 7

        self._is_on = data[0x04] & 1 != 0

        # self.quickChkSts = (data[1] & 32) >> 5
        # self.mode_FC_return = (data[2] & 240) >> 4
        self._mode = data[0x02] & 15
        self._fan_speed = data[0x03] & 0x7f
        self.on_timer_value = data[0x04]
        self.on_timer_minutes = data[0x06]
        self.off_timer_value = data[0x05]
        self.off_timer_minutes = data[0x06]

        self._target_humidity = data[0x07]
        if self._target_humidity > 100:
            self._target_humidity = 99

        # self.humidity_set_dot = data[8] & 15
        # self.mode_FD_return = data[10] & 7
        # self.filterShow = (data[9] & 0x80) >> 7
        self._ion_mode = (data[0x09] & 64) >> 6 != 0
        # self.sleepSwitch = (data[9] & 32) >> 5
        # self.pumpSwitch_flag = (data[9] & 16) >> 4
        # self.pumpSwitch = (data[9] & 8) >> 3
        # self.displayClass = data[9] & 7
        # self.defrostingShow = (data[10] & 0x80) >> 7
        self._tank_full = data[0x0a] & 0x7f >= 100
        # self.dustTimeShow = data[11] * 2
        # self.rareShow = (data[12] & 56) >> 3
        # self.dustShow = data[12] & 7
        # self.pmLowValue = data[13]
        # self.pmHighValue = data[14]
        # self.rareValue = data[15]
        self._current_humidity = data[0x10]

        # self.indoorTmp = data[17]
        # self.humidity_cur_dot = data[18] & 240
        # self.indoorTmpT1_dot = (data[18] & 15) >> 4
        # self.lightClass = data[19] & 240
        # self.upanddownSwing = data[19]
        # self.leftandrightSwing = (data[19] & 32) >> 4
        # self.lightValue = data[20]
        self._err_code = data[0x15]

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

    # Byte 0x04 + 0x06
    @property
    def on_timer(self):
        return {
            'status': (self.on_timer_value & 0x80) != 0,
            'set': self.on_timer_value != 0x7f,
            'hour': ((self.on_timer_value & 0x7c) >> 2
                     if self.on_timer_value != 0x7f else 0),
            'minutes': ((self.on_timer_value & 0x3)
                        | (((self.on_timer_minutes & 0xf0) >> 4)
                            if self.on_timer_value != 0x7f else 0)),
            'on_timer_value': self.on_timer_value,
            'on_timer_minutes': self.on_timer_minutes
        }

    # Byte 0x05 + 0x06
    @property
    def off_timer(self):
        return {
            'status': (self.off_timer_value & 0x80) != 0,
            'set': self.off_timer_value != 0x7f,
            'hour': (self.off_timer_value & 0x7c) >> 2,
            'minutes': ((self.off_timer_value & 0x3)
                        | (self.off_timer_minutes & 0xf)),
            'off_timer_value': self.off_timer_value,
            'off_timer_minutes': self.off_timer_minutes
        }
