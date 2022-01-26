""" Commands for Midea appliance """
from __future__ import annotations

from multiprocessing import RLock
from typing import ByteString

from midea_beautiful.crypto import crc8
from midea_beautiful.midea import AC_MAX_TEMPERATURE, AC_MIN_TEMPERATURE


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
# pylint: disable=duplicate-code


# Lock for command sequence increment
_order_lock = RLock()


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-instance-attributes
class MideaCommand:
    """Base command interface"""

    def __init__(self) -> None:
        self.data = bytearray()
        """Command payload"""

    def finalize(self) -> bytes:
        """Creates bytes sequence that represents a command to send.

        Returns:
            bytes: bytes representing the command
        """
        # Add the CRC8
        self.data[-2] = crc8(self.data[10:-2])
        # Add Message check code
        self.data[-1] = (~sum(self.data[1:-1]) + 1) & 0b11111111
        # Set the length of the command data
        return bytes(self.data)


class MideaSequenceCommand(MideaCommand):
    """Base command with sequence id/unique id"""

    # Each command has unique command id. We generate it as single byte
    # sequence with roll-over
    _sequence = 0

    @staticmethod
    def reset_sequence(value: int = 0) -> None:
        """Resets sequence generator for unique command id"""
        MideaSequenceCommand._sequence = value

    def __init__(self, sequence_idx: int = 30) -> None:
        super().__init__()
        self._sequence_idx = sequence_idx

    def finalize(self) -> bytes:
        with _order_lock:
            MideaSequenceCommand._sequence = (
                MideaSequenceCommand._sequence + 1
            ) & 0b11111111
        # Add the sequence
        self.data[self._sequence_idx] = MideaSequenceCommand._sequence
        return super().finalize()


class DeviceCapabilitiesCommand(MideaCommand):
    """B5 Command"""

    def __init__(self, appliance_type: int = 0xA1) -> None:
        super().__init__()
        # pylint: disable=duplicate-code
        self.data = bytearray(
            [
                0xAA,
                0x0E,
                appliance_type,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x03,
                0x03,
                0xB5,
                0x01,
                0x11,
                0x00,
                0x00,
            ]
        )


class DeviceCapabilitiesCommandMore(MideaCommand):
    """B5 Command"""

    def __init__(self, appliance_type: int = 0xA1) -> None:
        super().__init__()
        # pylint: disable=duplicate-code
        self.data = bytearray(
            [
                0xAA,
                0x0E,
                appliance_type,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x03,
                0x03,
                0xB5,
                0x01,
                0x01,
                0x00,
                0x00,
            ]
        )

    def finalize(self) -> bytes:
        # Add the CRC8
        self.data[-2] = crc8(self.data[10:-2])
        # Add Message check code
        self.data[-1] = (~sum(self.data[1:-1]) + 1) & 0b11111111
        return bytes(self.data)


class DehumidifierStatusCommand(MideaSequenceCommand):
    """Command that retrieves dehumidifier status"""

    def __init__(self) -> None:
        super().__init__()
        # Command structure
        # pylint: disable=duplicate-code
        self.data = bytearray(
            [
                # 0 header
                0xAA,
                # 1 command length: N+10
                0x20,
                # 2 appliance type 0xAC - airconditioning, 0xA1 - dehumidifier
                0xA1,
                # 3 Frame SYN CheckSum
                0x00,
                # 4-5 Reserved
                0x00,
                0x00,
                # 6 Message ID
                0x00,
                # 7 Frame Protocol Version
                0x00,
                # 8 Device Protocol Version
                0x00,
                # 9 Message Type: querying is 0x03; setting is 0x02
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
                0xFF,
                # Byte4
                0x03,
                # Byte5
                0xFF,
                # Byte6
                0x00,
                # Byte7 - Room Temperature Request:
                # 0x02 - indoor_temperature,
                # 0x03 - outdoor_temperature
                # when set, this is swing_mode
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                # Message ID
                0x00,
                # CRC8
                0x00,
                # Checksum
                0x00,
            ]
        )


class DehumidifierSetCommand(MideaSequenceCommand):
    """Command that sets dehumidifier controls"""

    def __init__(self) -> None:
        super().__init__()
        # Command structure
        # pylint: disable=duplicate-code
        self.data = bytearray(
            [
                # Sync header
                0xAA,
                # Length
                0x20,
                # Device type: Dehumidifier
                0xA1,
                # Frame synchronization check
                0x00,
                # Reserved
                0x00,
                0x00,
                # Message id
                0x00,
                # Framework protocol
                0x00,
                # Home appliance protocol
                0x03,
                # Message Type: querying is 0x03; control is 0x02
                0x02,
                # Payload
                # Data request/response type:
                # 0x41 - check status
                # 0x48 - write
                0x48,
                # Flags: On bit0 (byte 11)
                0x00,
                # Mode (byte 12)
                0x01,
                # Fan (byte 13)
                0x32,
                0x00,
                0x00,
                0x00,
                # Humidity (byte 17)
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ]
        )

    @property
    def running(self) -> bool:
        """Is appliance running"""
        return self.data[11] & 0b00000001 != 0

    @running.setter
    def running(self, state: bool) -> None:
        self.data[11] &= ~0b00000001  # Clear the power bit
        self.data[11] |= 0b00000001 if state else 0

    @property
    def ion_mode(self) -> bool:
        """Is anion mode active"""
        return self.data[19] & 0b01000000 != 0

    @ion_mode.setter
    def ion_mode(self, on_off: bool) -> None:
        self.data[19] &= ~0b01000000  # Clear the ion switch bit
        self.data[19] |= 0b01000000 if on_off else 0

    @property
    def target_humidity(self) -> int:
        """Target humidity for dehumidifier"""
        return self.data[17] & 0b01111111

    @target_humidity.setter
    def target_humidity(self, humidity: int) -> None:
        self.data[17] &= ~0b01111111  # Clear the humidity part
        self.data[17] |= humidity

    @property
    def mode(self) -> int:
        """Current operating mode"""
        return self.data[12] & 0b00001111

    @mode.setter
    def mode(self, mode: int) -> None:
        self.data[12] &= ~0b00001111  # Clear the mode bits
        self.data[12] |= mode

    @property
    def fan_speed(self) -> int:
        """Current fan speed"""
        return self.data[13] & 0b01111111

    @fan_speed.setter
    def fan_speed(self, speed: int) -> None:
        self.data[13] &= ~0b01111111  # Clear the fan speed part
        self.data[13] |= speed & 0b01111111

    @property
    def pump_switch(self) -> bool:
        """Turns pump on/off"""
        return self.data[19] & 0b00001000 != 0

    @pump_switch.setter
    def pump_switch(self, on_off: bool) -> None:
        self.data[19] &= ~0b00001000  # Clear the pump switch bit
        self.data[19] |= 0b00001000 if on_off else 0

    @property
    def pump_switch_flag(self) -> bool:
        """Pump switch flag - Disables pump"""
        return self.data[19] & 0b00010000 != 0

    @pump_switch_flag.setter
    def pump_switch_flag(self, on_off: bool) -> None:
        self.data[19] &= ~0b00010000  # Clear the pump switch bit
        self.data[19] |= 0b00010000 if on_off else 0

    @property
    def sleep_switch(self) -> bool:
        """Turn sleep mode on/off"""
        return self.data[19] & 0b00100000 != 0

    @sleep_switch.setter
    def sleep_switch(self, on_off: bool) -> None:
        self.data[19] &= ~0b00100000  # Clear the sleep switch bit
        self.data[19] |= 0b00100000 if on_off else 0

    @property
    def vertical_swing(self) -> bool:
        """Turn vertical swing on/off"""
        return self.data[20] & 0b00100000 != 0

    @vertical_swing.setter
    def vertical_swing(self, on_off: bool) -> None:
        self.data[20] &= ~0b00100000  # Clear the sleep switch bit
        self.data[20] |= 0b00100000 if on_off else 0

    @property
    def beep_prompt(self) -> bool:
        """Activates beep on action"""
        return self.data[11] & 0b01000000 != 0

    @beep_prompt.setter
    def beep_prompt(self, state: bool) -> None:
        self.data[11] &= ~0b01000000  # Clear the beep prompt bit
        self.data[11] |= 0b01000000 if state else 0

    @property
    def tank_warning_level(self) -> int:
        """Target humidity for dehumidifier"""
        return self.data[23]

    @tank_warning_level.setter
    def tank_warning_level(self, level: int) -> None:
        self.data[23] = level


class DehumidifierResponse:
    """Response from dehumidifier queries"""

    def __init__(self, data: ByteString) -> None:
        # pylint: disable=too-many-statements
        self.fault = (data[1] & 0b10000000) != 0
        self.run_status = (data[1] & 0b00000001) != 0
        self.i_mode = (data[1] & 0b00000100) != 0
        self.timing_mode = (data[1] & 0b00010000) != 0
        self.quick_check = (data[1] & 0b00100000) != 0
        self.mode = data[2] & 0b00001111
        self.mode_fc = (data[2] & 0b11110000) >> 4
        self.fan_speed = data[3] & 0b01111111
        self.on_timer_set = (data[4] & 0b10000000) != 0
        self.on_timer_hour = (data[4] & 0b01111100) >> 2
        self.on_timer_minutes = (data[4] & 0b00000011) * 15 + (
            (data[6] & 0b11110000) >> 4
        )
        self.off_timer_set = (data[5] & 0b10000000) != 0
        self.off_timer_hour = (data[5] & 0b01111100) >> 2
        self.off_timer_minutes = (data[5] & 0b00000011) * 15 + (data[6] & 0b00001111)

        self.target_humidity = data[7]
        if self.target_humidity > 100:
            self.target_humidity = 100

        target_humidity_decimal: float = (data[8] & 15) * 0.0625
        # CONFLICT WITH tank full self.mode_FD_return = data[10] & 0b00000111
        self.target_humidity += target_humidity_decimal
        self.filter_indicator = (data[9] & 0b10000000) != 0
        self.ion_mode = (data[9] & 0b01000000) != 0
        self.sleep_switch = (data[9] & 0b00100000) != 0
        self.pump_switch_flag = (data[9] & 0b00010000) != 0
        self.pump_switch = (data[9] & 0b00001000) != 0
        self.display_class = data[9] & 0b00000111
        self.defrosting = (data[10] & 0b10000000) != 0
        self.tank_level = data[10] & 0b01111111
        self.tank_full = self.tank_level >= 100
        self.dust_time = data[11] * 2
        self.rare_show = (data[12] & 0b00111000) >> 3
        self.dust = data[12] & 0b00000111
        self.pm25 = data[13] + (data[14] * 256)
        self.tank_warning_level = data[15]
        self.current_humidity = data[16]
        self.indoor_temperature = (data[17] - 50) / 2
        if self.indoor_temperature < -19:
            self.indoor_temperature = -20
        if self.indoor_temperature > 50:
            self.indoor_temperature = 50
        # humidity_decimal = ((data[18] & 0b11110000) >> 4) * 0.1
        # self.current_humidity += humidity_decimal
        temperature_decimal = (data[18] & 0b00001111) * 0.1
        if self.indoor_temperature >= 0:
            self.indoor_temperature += temperature_decimal
        else:
            self.indoor_temperature -= temperature_decimal
        if len(data) > 19:
            self.light_class = (data[19] & 0b11000000) >> 6  # TO BE CHECKED
            self.vertical_swing = (data[19] & 0b00100000) != 0
            self.horizontal_swing = (data[19] & 0b00010000) != 0
        else:
            self.horizontal_swing = None
            self.vertical_swing = None
            self.light_class = None
        if len(data) > 20:
            self.light_value = data[20]
        else:
            self.light_value = None
        if len(data) > 21:
            self.err_code = data[21]
        else:
            self.err_code = 0

    def __str__(self) -> str:
        return str(self.__dict__)


class AirConditionerStatusCommand(MideaSequenceCommand):
    """Command that retrieves air conditioner status"""

    def __init__(self) -> None:
        super().__init__()
        # Command structure
        # pylint: disable=duplicate-code
        self.data = bytearray(
            [
                # 0 header
                0xAA,
                # 1 command length: N+10
                0x20,
                # 2 appliance type 0xAC - airconditioning, 0xA1 - dehumidifier
                0xAC,
                # 3 Frame SYN CheckSum
                0x00,
                # 4-5 Reserved
                0x00,
                0x00,
                # 6 Message ID
                0x00,
                # 7 Frame Protocol Version
                0x00,
                # 8 Device Protocol Version
                0x00,
                # 9 Message Type: querying is 0x03; setting is 0x02
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
                0xFF,
                # Byte4
                0x03,
                # Byte5
                0xFF,
                # Byte6
                0x00,
                # Byte7 - Room Temperature Request:
                # 0x02 - indoor_temperature,
                # 0x03 - outdoor_temperature
                # when set, this is swing_mode
                0x02,
                # Byte 8
                0x00,
                # Byte 9
                0x00,
                # Byte 10
                0x00,
                # Byte 11
                0x00,
                # Byte 12
                0x00,
                # Byte 13
                0x00,
                # Byte 14
                0x00,
                # Byte 15
                0x00,
                # Byte 16
                0x00,
                # Byte 17
                0x00,
                # Byte 18
                0x00,
                # Byte 19
                0x00,
                # Byte 20
                # Message ID
                0x00,
                # CRC8
                0x00,
                # Checksum
                0x00,
            ]
        )


class AirConditionerSetCommand(MideaSequenceCommand):
    """Command that sets air conditioner controls"""

    def __init__(self) -> None:
        super().__init__()
        # Command structure
        # pylint: disable=duplicate-code
        self.data = bytearray(
            [
                # Sync header
                0xAA,
                # Length
                0x23,
                # Device type: Air conditioner
                0xAC,
                # Frame synchronization check
                0x00,
                # Reserved
                0x00,
                0x00,
                # Message id
                0x00,
                # Framework protocol
                0x00,
                # Home appliance protocol
                0x00,
                # Message Type: querying is 0x03; control is 0x02
                0x02,
                # Payload
                # Data request/response type:
                # 0x41 - check status
                # 0x40 - write
                0x40,
                # Flags: On bit0 (byte 11)
                0x00,
                # Mode (byte 12)
                0x00,
                # Fan (byte 13)
                0x00,
                0x00,
                0x00,
                0x00,
                # ? (byte 17)
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                # 3 more?
                0x00,
                0x00,
                0x00,
            ]
        )

    @property
    def running(self) -> bool:
        """Is appliance running"""
        return self.data[11] & 0b00000001 != 0

    @running.setter
    def running(self, state: bool) -> None:
        self.data[11] &= ~0b00000001  # Clear the power bit
        self.data[11] |= 0b00000001 if state else 0

    @property
    def beep_prompt(self) -> bool:
        """Activates beep on action"""
        return self.data[11] & 0b01000000 != 0

    @beep_prompt.setter
    def beep_prompt(self, state: bool) -> None:
        self.data[11] &= ~0b01000000  # Clear the beep prompt bit
        self.data[11] |= 0b01000000 if state else 0

    @property
    def mode(self) -> int:
        """Current operating mode"""
        return (self.data[12] & 0b11100000) >> 5

    @mode.setter
    def mode(self, mode: int) -> None:
        self.data[12] &= ~0b11100000  # Clear the mode bits
        self.data[12] |= (mode & 0b111) << 5

    @property
    def temperature(self) -> float:
        """Current target A/C temperature"""
        return (self.data[12] & 0b00001111) + 16 + self.temperature_decimal

    @temperature.setter
    def temperature(self, temperature: float) -> None:
        if temperature < AC_MIN_TEMPERATURE or temperature > AC_MAX_TEMPERATURE:
            self.data[12] &= ~0b00001111  # Clear the temperature bits
            self.temperature_decimal = 0
        else:
            temperature_int = int(temperature)
            self.temperature_decimal = temperature - temperature_int
            self.data[12] |= int(temperature_int) & 0b00001111

    @property
    def temperature_decimal(self) -> float:
        """Current target A/C temperature (decimals)"""
        return 0.5 if (self.data[12] & 0b00010000) != 0 else 0

    @temperature_decimal.setter
    def temperature_decimal(self, digit: float) -> None:
        self.data[12] &= ~0b00010000  # Clear the mode bits
        if digit == 0.5:
            self.data[12] |= 0b00010000

    @property
    def fan_speed(self) -> int:
        """Current fan speed"""
        return self.data[13] & 0b01111111

    @fan_speed.setter
    def fan_speed(self, speed: int) -> None:
        self.data[13] &= ~0b01111111  # Clear the fan speed part
        self.data[13] |= speed & 0b01111111

    @property
    def horizontal_swing(self):
        """Horizontal swing mode active"""
        return (self.data[17] & 0x0011) >> 2

    @horizontal_swing.setter
    def horizontal_swing(self, mode: int):
        self.data[17] &= ~0x0011  # Clear the mode bit
        self.data[17] |= 0x1110011 if mode else 0

    @property
    def vertical_swing(self):
        """Vertical swing mode active"""
        return (self.data[17] & 0x1100) >> 2

    @vertical_swing.setter
    def vertical_swing(self, mode: int):
        self.data[17] &= ~0x1100  # Clear the mode bit
        self.data[17] |= 0x111100 if mode else 0

    @property
    def turbo_fan(self) -> bool:
        """Turbo fan mode on/off"""
        return self.data[18] & 0b00100000 != 0

    @turbo_fan.setter
    def turbo_fan(self, turbo_fan: bool):
        self.data[18] &= ~0b001000000
        self.data[18] |= 0b00100000 if turbo_fan else 0

    @property
    def dryer(self) -> bool:
        """Dryer mode on/off"""
        return self.data[19] & 0b00000100 != 0

    @dryer.setter
    def dryer(self, dryer: bool):
        self.data[19] &= ~0b00000100
        self.data[19] |= 0b00000100 if dryer else 0

    @property
    def purifier(self) -> bool:
        """Air purifier mode on/off"""
        return self.data[19] & 0b00100000 != 0

    @purifier.setter
    def purifier(self, purifier: bool):
        self.data[19] &= ~0b00100000
        self.data[19] |= 0b00100000 if purifier else 0

    @property
    def eco_mode(self) -> bool:
        """Eco mode on/off"""
        return self.data[19] & 0b10000000 != 0

    @eco_mode.setter
    def eco_mode(self, eco_mode_enabled: bool):
        self.data[19] &= ~0b10000000
        self.data[19] |= 0b10000000 if eco_mode_enabled else 0

    @property
    def comfort_sleep(self) -> bool:
        """Activates sleep mode"""
        return self.data[20] & 0b10000000 != 0

    @comfort_sleep.setter
    def comfort_sleep(self, state: bool) -> None:
        self.data[20] &= ~0b10000000  # Clear the comfort sleep switch
        self.data[20] |= 0b10000000 if state else 0
        self.data[18] &= ~0b00000011  # Clear the comfort value
        self.data[18] |= 0b00000011 if state else 0

    @property
    def fahrenheit(self) -> bool:
        """Display degrees Fahrenheit (only impacts device display)"""
        return self.data[20] & 0b00000100 != 0

    @fahrenheit.setter
    def fahrenheit(self, fahrenheit: bool):
        self.data[20] &= ~0b00000100
        self.data[20] |= 0b00000100 if fahrenheit else 0

    @property
    def turbo(self) -> bool:
        """A/C turbo mode on/off"""
        return self.data[20] & 0b00000010 != 0

    @turbo.setter
    def turbo(self, turbo: bool):
        self.data[20] &= ~0b00000010
        self.data[20] |= 0b00000010 if turbo else 0

    @property
    def screen(self) -> bool:
        """A/C screen display on/off"""
        return self.data[20] & 0b00010000 != 0

    @screen.setter
    def screen(self, screen: bool):
        self.data[20] &= ~0b00010000
        self.data[20] |= 0b00010000 if screen else 0


class AirConditionerResponse:
    """Response from air conditioner queries"""

    def __init__(self, data: bytes) -> None:
        # pylint: disable=too-many-statements
        self.run_status = (data[1] & 0b00000001) != 0
        self.i_mode = (data[1] & 0b00000100) != 0
        self.timing_mode = (data[1] & 0b00010000) != 0
        self.quick_check = (data[1] & 0b00100000) != 0
        self.appliance_error = (data[1] & 0b10000000) != 0

        self.mode = data[2] & 0b01110000
        self.target_temperature = (
            (data[2] & 0b00001111)
            + 16.0
            + (0.5 if (data[2] & 0b10000000) != 0 else 0.0)
        )

        self.fan_speed = data[3] & 0b01111111

        self.on_timer_set = (data[4] & 0b10000000) != 0
        self.on_timer_hours = (data[4] & 0b01111100) >> 2
        self.on_timer_minutes = (data[4] & 0b00000011) * 15 + (
            (data[6] & 0b11110000) >> 4
        )
        self.off_timer_set = (data[5] & 0b10000000) != 0
        self.off_timer_hours = (data[5] & 0b01111100) >> 2
        self.off_timer_minutes = (data[5] & 0b00000011) * 15 + (data[6] & 0b00001111)

        self.vertical_swing = (data[7] & 0b00001100) >> 2
        self.horizontal_swing = data[7] & 0b00000011

        self.comfort_sleep_value = data[8] & 0b00000011
        self.power_saving = (data[8] & 0b00001000) != 0
        self.low_frequency_fan = (data[8] & 0b00010000) != 0
        self.turbo_fan = (data[8] & 0b00100000) != 0
        self.feel_own = (data[8] & 0b10000000) != 0

        self.comfort_sleep = (data[9] & 0b01000000) != 0
        self.natural_wind = (data[9] & 0b00000010) != 0
        self.eco = (data[9] & 0b00010000) != 0
        self.purifier = (data[9] & 0b00100000) != 0
        self.dryer = (data[9] & 0b00000100) != 0
        self.ptc = (data[9] & 0b00011000) >> 3
        self.aux_heat = (data[9] & 0b00001000) != 0

        self.turbo = (data[10] & 0b00000010) != 0
        self.fahrenheit = (data[10] & 0b00000100) != 0
        self.prevent_freezing = (data[10] & 0b00100000) != 0

        self.pmv = (data[14] & 0b00001111) * 0.5 - 3.5
        if data[12] != 0 and data[12] != 0xFF:
            self.outdoor_temperature = (data[12] - 50) / 2
            digit = 0.1 * ((data[15] & 0b11110000) >> 4)
            if self.outdoor_temperature < 0:
                self.outdoor_temperature -= digit
            else:
                self.outdoor_temperature += digit
        else:
            self.outdoor_temperature = None
        if data[11] != 0 and data[11] != 0xFF:
            self.indoor_temperature = (data[11] - 50) / 2
            digit = 0.1 * (data[15] & 0b00001111)
            if self.indoor_temperature < 0:
                self.indoor_temperature -= digit
            else:
                self.indoor_temperature += digit
        else:
            self.indoor_temperature = None
        self.err_code = data[16]

        if len(data) > 20:
            self.humidity = data[19]
        else:
            self.humidity = None

    def __str__(self) -> str:
        return str(self.__dict__)
