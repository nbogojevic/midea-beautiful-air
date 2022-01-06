from binascii import unhexlify
from typing import Final
import unittest

from midea_beautiful.command import (
    AirConditionerResponse,
    DehumidifierResponse,
    DehumidifierSetCommand,
    DeviceCapabilitiesCommand,
    DeviceCapabilitiesCommandMore,
    midea_command_reset_sequence,
)
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APPKEY,
)

APP_KEY: Final = DEFAULT_APPKEY


class TestCommand(unittest.TestCase):
    def test_device_capabilities_command(self) -> None:
        dc = DeviceCapabilitiesCommand()
        self.assertEqual("aa0ea100000000000303b501118ef6", dc.finalize().hex())

    def test_device_capabilities_command_more(self) -> None:
        dc = DeviceCapabilitiesCommandMore()
        self.assertEqual("aa0ea100000000000303b501011381", dc.finalize().hex())

    def test_dehumidifier_status(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        cmd = device.state.refresh_command().finalize()
        self.assertEqual(
            "aa20a100000000000003418100ff03ff000000000000000000000000000001294f",
            cmd.hex(),
        )

    def test_dehumidifier_set(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa20a100000000000302480000280000003200000000000000000000000001395e",
            cmd.hex(),
        )

    def test_dehumidifier_set_fan_speed(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        setattr(device.state, "fan_speed", 60)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa20a1000000000003024800003c0000003200000000000000000000000001dea5",
            cmd.hex(),
        )

    def test_dehumidifier_set_mode(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        setattr(device.state, "mode", 3)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa20a1000000000003024800032800000032000000000000000000000000014b49",
            cmd.hex(),
        )

    def test_dehumidifier_set_target_humidity(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        setattr(device.state, "target_humidity", 45)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa20a100000000000302480000280000002d000000000000000000000000017626",
            cmd.hex(),
        )

    def test_dehumidifier_set_various(self) -> None:
        command = DehumidifierSetCommand()
        self.assertEqual(command.running, False)
        self.assertEqual(command.ion_mode, False)
        self.assertEqual(command.pump_switch_flag, False)
        self.assertEqual(command.pump_switch, False)
        self.assertEqual(command.sleep_switch, False)
        self.assertEqual(command.beep_prompt, False)
        self.assertEqual(command.target_humidity, 45)
        self.assertEqual(command.fan_speed, 40)
        self.assertEqual(command.mode, 0)
        command.pump_switch_flag = True

        cmd = command.finalize()
        self.assertEqual(command.pump_switch_flag, True)
        self.assertEqual(
            "aa20a100000000000302480000280000002d001000000000000000000000024249",
            cmd.hex(),
        )

    def test_ac_status(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        cmd = device.state.refresh_command().finalize()
        self.assertEqual(
            "aa20ac00000000000003418100ff03ff00020000000000000000000000000171fa",
            cmd.hex(),
        )

        midea_command_reset_sequence(2)
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        cmd = device.state.refresh_command().finalize()
        self.assertEqual(
            "aa20ac00000000000003418100ff03ff000200000000000000000000000003cd9c",
            cmd.hex(),
        )

    def test_aircon_set_fan(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        setattr(device.state, "beep_prompt", True)
        setattr(device.state, "fan_speed", 48)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa23ac0000000000000240400030000000000000100000000000000000000100000078f6",
            cmd.hex(),
        )

    def test_aircon_set_mode(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        setattr(device.state, "beep_prompt", True)
        setattr(device.state, "fan_speed", 48)
        setattr(device.state, "mode", 2)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa23ac00000000000002404040300000000000001000000000000000000001000000ce60",
            cmd.hex(),
        )

    def test_aircon_set_turbo(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        setattr(device.state, "beep_prompt", True)
        setattr(device.state, "turbo", True)
        setattr(device.state, "fan_speed", 40)

        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa23ac000000000000024040002800000000000012000000000000000000010000000173",
            cmd.hex(),
        )

    def test_aircon_set_temperature(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        setattr(device.state, "beep_prompt", True)
        setattr(device.state, "turbo", True)
        setattr(device.state, "fan_speed", 45)
        setattr(device.state, "target_temperature", 20.5)

        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa23ac000000000000024040142d0000000000001200000000000000000001000000a7b4",
            cmd.hex(),
        )

    def test_dehumidifier_response(self):
        response = DehumidifierResponse(
            unhexlify("c80101287f7f003c00000000000000003f5000000000024238")
        )
        self.assertEqual(response.current_humidity, 63, "current_humidity")
        self.assertEqual(response.tank_full, False, "tank_full")
        self.assertEqual(response.target_humidity, 60, "target_humidity")
        self.assertEqual(response.off_timer["status"], False)
        self.assertEqual(response.off_timer["hour"], 31)
        self.assertEqual(response.on_timer["status"], False)
        self.assertEqual(response.on_timer["hour"], 0)

    def test_ac_response(self):
        response = AirConditionerResponse(
            unhexlify("c80101287f7f003c00000000000000003f5000000000024238")
        )
        self.assertIsNone(response.outdoor_temperature)
        self.assertIsNone(response.indoor_temperature)
        self.assertEqual(response.target_temperature, 17, "target_temperature")
        response = AirConditionerResponse(
            unhexlify("c80101287f7f003c00000040200000003f5000000000024238")
        )
        print(response)
        self.assertEqual(response.outdoor_temperature, -9, "outdoor_temperature")
        self.assertEqual(response.indoor_temperature, 7, "indoor_temperature")
