""" Commands for Midea appliance """
from __future__ import annotations
from multiprocessing import RLock

from midea_beautiful_dehumidifier.crypto import crc8

# Each command has unique sequence id (single byte with roll-over)
_command_sequence: int = 0
# Lock for command sequence increment
_order_lock = RLock()


class MideaCommand:
    """Base command interface"""

    def __init__(self) -> None:
        self.data = bytearray()

    def finalize(self) -> bytes:
        global _command_sequence
        with _order_lock:
            _command_sequence = (_command_sequence + 1) & 0xFF
        # Add the CRC8
        self.data[30] = _command_sequence
        # Add the CRC8
        self.data[31] = crc8(self.data[10:31])
        # Add checksum
        self.data[32] = (~sum(self.data[1:32]) + 1) & 0xFF
        # Set the length of the command data
        return bytes(self.data)


class DehumidifierStatusCommand(MideaCommand):
    """Command that retrieves dehumidifier status"""

    def __init__(self) -> None:
        # Command structure
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
                0x03,
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


class DehumidifierSetCommand(MideaCommand):
    """Command that sets dehumidifier controls"""

    def __init__(self) -> None:
        self.data = bytearray(
            [
                0xAA,
                # Length
                0x20,
                # Dehumidifier
                0xA1,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
                0x03,
                # Message Type: querying is 0x03; setting is 0x02
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
        return self.data[11] & 0x01 != 0

    @running.setter
    def running(self, state: bool) -> None:
        self.data[11] &= ~0x01  # Clear the power bit
        self.data[11] |= 0x01 if state else 0

    @property
    def ion_mode(self) -> bool:
        return self.data[19] & 0b01000000 != 0

    @ion_mode.setter
    def ion_mode(self, on_off: bool) -> None:
        self.data[19] &= ~0b01000000  # Clear the ion switch bit
        self.data[19] |= 0b01000000 if on_off else 0

    @property
    def target_humidity(self) -> int:
        return self.data[17] & 0x7F

    @target_humidity.setter
    def target_humidity(self, humidity: int) -> None:
        self.data[17] &= ~0x7F  # Clear the humidity part
        self.data[17] |= humidity

    @property
    def mode(self) -> int:
        return self.data[12] & 0x0F

    @mode.setter
    def mode(self, mode: int) -> None:
        self.data[12] &= ~0x0F  # Clear the mode bits
        self.data[12] |= mode

    @property
    def fan_speed(self) -> int:
        return self.data[13] & 0x7F

    @fan_speed.setter
    def fan_speed(self, speed: int) -> None:
        self.data[13] &= ~0x7F  # Clear the fan speed part
        self.data[13] |= speed & 0x7F

    @property
    def pump_switch(self) -> bool:
        return self.data[19] & 0b00001000 != 0

    @pump_switch.setter
    def pump_switch(self, on_off: bool) -> None:
        self.data[19] &= ~0b00001000  # Clear the pump switch bit
        self.data[19] |= 0b00001000 if on_off else 0

    @property
    def sleep_switch(self) -> bool:
        return self.data[19] & 0b00100000 != 0

    @sleep_switch.setter
    def sleep_switch(self, on_off: bool) -> None:
        self.data[19] &= ~0b00100000  # Clear the sleep switch bit
        self.data[19] |= 0b00100000 if on_off else 0


class DehumidifierResponse:
    """Response from dehumidifier queries"""
    def __init__(self, data: bytes) -> None:

        # self.faultFlag = (data[1] & 0x80) >> 7

        self.is_on = data[4] & 1 != 0

        # self.quickChkSts = (data[1] & 32) >> 5
        self.fault = data[1] & 0x10000000
        self.run_status = data[1] & 0x00000001
        self.i_mode = data[1] & 0x00000100
        self.timing_mode = data[1] & 0x00010000
        self.quick_check = data[1] & 0x00100000
        # self.mode_FC_return = (data[2] & 240) >> 4
        self.mode = data[2] & 0x0F
        self.mode_fc = data[2] & 0xF0
        self.fan_speed = data[3] & 0x7F

        self._on_timer_value = data[4]
        self._on_timer_minutes = data[6] & 0xF0
        self._off_timer_value = data[5]
        self._off_timer_minutes = data[6] & 0x0F

        self.target_humidity = data[7]
        if self.target_humidity > 100:
            self.target_humidity = 99

        humidity_decimal: float = (data[8] & 15) * 0.0625
        self.target_humidity += humidity_decimal
        # self.mode_FD_return = data[10] & 7
        self.filter_indicator = (data[9] & 0x10000000) != 0
        self.ion_mode = (data[9] & 0b01000000) != 0
        self.sleep_switch = (data[9] & 0b00100000) != 0
        # self.pumpSwitch_flag = (data[9] & 16) >> 4
        self.pump_switch = (data[9] & 0b00001000) != 0
        # self.displayClass = data[9] & 7
        self.defrosting = (data[10] & 0x10000000) != 0
        self.tank_full = data[10] & 0x7F >= 100
        # self.dustTimeShow = data[11] * 2
        # self.rareShow = (data[12] & 56) >> 3
        # self.dustShow = data[12] & 7
        # self.pmLowValue = data[13]
        # self.pmHighValue = data[14]
        # self.rareValue = data[15]
        self.current_humidity = data[16]
        self.indoor_temperature = int((data[17] - 50) / 2)
        if self.indoor_temperature < -19:
            self.indoor_temperature = -20
        if self.indoor_temperature > 50:
            self.indoor_temperature = 50
        humidity_decimal = ((data[18] & 0b11110000) >> 4) * 0.1
        self.current_humidity += humidity_decimal
        temperature_decimal = (data[18] & 0b00001111) * 0.1
        self.indoor_temperature += temperature_decimal
        # self.lightClass = data[19] & 240
        # self.upAndDownSwing = data[19]
        # self.leftandrightSwing = (data[19] & 32) >> 4
        # self.lightValue = data[20]
        self.err_code = data[21]

    # Byte 0x04 + 0x06
    @property
    def on_timer(self) -> dict:
        return {
            "status": (self._on_timer_value & 0x80) != 0,
            "set": self._on_timer_value != 0x7F,
            "hour": (
                (self._on_timer_value & 0x7C) >> 2
                if self._on_timer_value != 0x7F
                else 0
            ),
            "minutes": (
                (self._on_timer_value & 0x3)
                | (
                    ((self._on_timer_minutes & 0xF0) >> 4)
                    if self._on_timer_value != 0x7F
                    else 0
                )
            ),
            "on_timer_value": self._on_timer_value,
            "on_timer_minutes": self._on_timer_minutes,
        }

    # Byte 0x05 + 0x06
    @property
    def off_timer(self) -> dict:
        return {
            "status": (self._off_timer_value & 0x80) != 0,
            "set": self._off_timer_value != 0x7F,
            "hour": (self._off_timer_value & 0x7C) >> 2,
            "minutes": (
                (self._off_timer_value & 0x3) | (self._off_timer_minutes & 0xF)
            ),
            "off_timer_value": self._off_timer_value,
            "off_timer_minutes": self._off_timer_minutes,
        }

    def __str__(self) -> str:
        return str(self.__dict__)
