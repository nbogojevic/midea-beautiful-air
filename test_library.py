import binascii
from datetime import datetime
import logging
from typing import Final
import unittest

# Use colored logs if installed
try:
    from coloredlogs import install as coloredlogs_install
except Exception:

    def coloredlogs_install(level) -> None:
        pass


from midea_beautiful.command import (
    DeviceCapabilitiesCommand,
    DeviceCapabilitiesCommandMore,
    midea_command_reset_sequence,
)
from midea_beautiful.crypto import Security
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import (
    APPLIANCE_TYPE_AIRCON,
    APPLIANCE_TYPE_DEHUMIDIFIER,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
)

APP_KEY: Final = DEFAULT_APPKEY


class TestSecurity(unittest.TestCase):
    def test_aes_encrypt_string(self) -> None:
        access_token = (
            "87836529d24810fb715db61f2d3eba2ab920ebb829d567559397ded751813801"
        )
        security = Security(APP_KEY)
        security.access_token = access_token
        query = (
            "90,90,1,0,89,0,32,0,1,0,0,0,39,36,17,9,13,10,18,20,-38,73,0,0,0,16,0,0,0,"
            "0,0,0,0,0,0,0,0,0,0,0,-86,32,-95,0,0,0,0,0,3,3,65,33,0,-1,3,0,0,2,0,0,0,0,"
            "0,0,0,0,0,0,0,0,11,36,-92,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        )
        expected_encrypted_str = (
            "7c8911b6de8e29fa9a1538def06c9018a9995980893554fb80fd87c5478ac78b360f7b3543"
            "3b8d451464bdcd3746c4f5c05a8099eceb79aeb9cc2cc712f90f1c9b3bb091bcf0e90bddf6"
            "2d36f29550796c55acf8e637f7d3d68d11be993df933d94b2b43763219c85eb21b4d9bb989"
            "1f1ab4ccf24185ccbcc78c393a9212c24bef3466f9b3f18a6aabcd58e80ce9df61ccf13885"
            "ebd714595df69709f09722ff41eb37ea5b06f727b7fab01c94588459ccf13885ebd714595d"
            "f69709f09722ff32b544a259d2fa6e7ddaac1fdff91bb0"
        )
        encrypted_string = security.aes_encrypt_string(query)
        self.assertEqual(expected_encrypted_str, encrypted_string)

    def test_aes_decrypt_string(self) -> None:
        access_token = (
            "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        )
        security = Security(APP_KEY)
        security.access_token = access_token
        reply = (
            "02940d3220c4a1a1fcfb4e8593a93c0facebf2d3d170c089f8c9d7274f8048462f8d8a"
            "c5ab6b8073382dbc9b9dcc63c293b3dffc38a7bb66832fb4ae3514a40873768e0b3c6c"
            "c653c5802496e2b271cba2bfc89ca102623370e8901845328834c53227ac9ea088605e"
            "e64825413692b1df952de8baf0dd76ecd34202f91dcc4908baeaf21a29ca4c11203f2c"
            "984fd282ec23185ce83c99215494482d87bebdcb3b31f06f44f810c15404be14b1ed8b"
            "f090f1e835d796869adf20bf35ff5b7ebc73768e0b3c6cc653c5802496e2b271cb6eb1"
            "66994a36e79b29551a0dc87fed53"
        )
        expected_decoded_reply = (
            "90,90,1,0,91,0,32,-128,1,0,0,0,0,0,0,0,0,0,0,0,-38,73,"
            "0,0,0,16,0,0,0,0,0,0,0,0,0,0,1,0,0,0,-86,34,-95,0,0,0,"
            "0,0,3,3,-56,1,4,80,127,127,0,35,0,64,0,0,0,0,0,0,61,86,"
            "0,0,0,0,-92,-85,-41,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"
        )
        decoded_reply = security.aes_decrypt_string(reply)
        self.assertEqual(expected_decoded_reply, decoded_reply)

    def test_encrypt_password(self) -> None:
        security = Security(APP_KEY)
        expected_encrypted_password = (
            "f6a8f970344eb9b84f770d8eb9e8b511f4799bbce29bdef6990277783c243b5f"
        )
        encrypted_password = security.encrypt_password(
            "592758da-e522-4263-9cea-3bac916a0416", "passwordExample"
        )
        self.assertEqual(expected_encrypted_password, encrypted_password)

    def test_sign(self) -> None:
        security = Security(APP_KEY)
        expected_sign = (
            "d1d0b37a6cc407e9b8fcecc1f2e250f6a9cfd83cfbf7e4443d30a34cb4e9a62d"
        )
        args = {
            "loginAccount": "user@example.com",
            "appId": DEFAULT_APP_ID,
            "clientType": 1,
            "format": 2,
            "language": "en_US",
            "src": 17,
            "stamp": 20211226190000,
        }
        sign = security.sign("/v1/user/login/id/get", args)
        self.assertEqual(expected_sign, sign)

    def test_data_key(self) -> None:
        security = Security(APP_KEY)
        security.access_token = (
            "f4fe051b7611d07d54a7f0a5e07ca2beb920ebb829d567559397ded751813801"
        )
        self.assertEqual("23f4b15525824bc3", security.data_key)


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
        cmd = device.state.refresh_command()
        self.assertEqual(
            "aa20a100000000000003418100ff03ff000000000000000000000000000001294f",
            cmd.finalize().hex(),
        )

    def test_dehumidifier_set(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        cmd = device.state.apply_command()
        self.assertEqual(
            "aa20a100000000000302480000280000003200000000000000000000000001395e",
            cmd.finalize().hex(),
        )

    def test_dehumidifier_set_fan_speed(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        setattr(device.state, "fan_speed", 60)
        cmd = device.state.apply_command()
        self.assertEqual(
            "aa20a1000000000003024800003c0000003200000000000000000000000001dea5",
            cmd.finalize().hex(),
        )

    def test_dehumidifier_set_mode(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        setattr(device.state, "mode", 3)
        cmd = device.state.apply_command()
        self.assertEqual(
            "aa20a1000000000003024800032800000032000000000000000000000000014b49",
            cmd.finalize().hex(),
        )

    def test_dehumidifier_set_target_humidity(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        setattr(device.state, "target_humidity", 45)
        cmd = device.state.apply_command()
        self.assertEqual(
            "aa20a100000000000302480000280000002d000000000000000000000000017626",
            cmd.finalize().hex(),
        )

    def test_ac_status(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        cmd = device.state.refresh_command().finalize().hex()
        self.assertEqual(
            "aa20ac00000000000003418100ff03ff00020000000000000000000000000171fa",
            cmd,
        )

        midea_command_reset_sequence(2)
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        cmd = device.state.refresh_command().finalize().hex()
        self.assertEqual(
            "aa20ac00000000000003418100ff03ff000200000000000000000000000003cd9c",
            cmd,
        )

    def test_aircon_set_fan(self) -> None:
        midea_command_reset_sequence()
        device = LanDevice(id="12345", appliance_type=APPLIANCE_TYPE_AIRCON)
        setattr(device.state, "beep_prompt", True)
        setattr(device.state, "fan_speed", 48)
        cmd = device.state.apply_command().finalize()
        self.assertEqual(
            "aa23ac000000000000024040003000000000000000000000000000000000010000008af4",
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
            "aa23ac000000000000024040403000000000000000000000000000000000010000003c02",
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
            "aa23ac00000000000002404000280000000000000200000000000000000001000000f391",
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
            "aa23ac000000000000024040142d00000000000002000000000000000000010000005516",
            cmd.hex(),
        )


BROADCAST_PAYLOAD: Final = (
    "020100c02c190000"
    "3030303030305030303030303030513131323334353637383941424330303030"
    "0b6e65745f61315f394142430000000001000000040000000000"
    "a1"
    "00000000000000"
    "123456789abc069fcd0300080103010000000000000000000000000000000000000000"
)


class TestLanDevice(unittest.TestCase):
    def test_lan_packet_header_ac(self) -> None:
        expected_header = binascii.unhexlify("5a5a01116800200000000000")

        device = LanDevice(id=str(0x12345), appliance_type=APPLIANCE_TYPE_AIRCON)
        cmd = device.state.refresh_command()
        now = datetime.now()
        res = device._lan_packet(cmd)
        self.assertEqual(expected_header, res[: len(expected_header)])
        if now.minute < 59:
            self.assertEqual(now.hour, res[15])
            if now.hour < 23:
                self.assertEqual(now.day, res[16])
                self.assertEqual(now.month, res[17])
                self.assertEqual(now.year % 100, res[18])
                self.assertEqual(int(now.year / 100), res[19])

        self.assertEqual(0x45, res[20])
        self.assertEqual(0x23, res[21])
        self.assertEqual(0x01, res[22])
        self.assertEqual(0x00, res[23])

    def test_lan_packet_header_dehumidifier(self) -> None:
        expected_header = binascii.unhexlify("5a5a01116800200000000000")

        device = LanDevice(id=str(0x12345), appliance_type=APPLIANCE_TYPE_DEHUMIDIFIER)
        cmd = device.state.refresh_command()
        now = datetime.now()
        res = device._lan_packet(cmd)
        self.assertEqual(expected_header, res[: len(expected_header)])
        if now.minute < 59:
            self.assertEqual(now.hour, res[15])
            if now.hour < 23:
                self.assertEqual(now.day, res[16])
                self.assertEqual(now.month, res[17])
                self.assertEqual(now.year % 100, res[18])
                self.assertEqual(int(now.year / 100), res[19])

        self.assertEqual(0x45, res[20])
        self.assertEqual(0x23, res[21])
        self.assertEqual(0x01, res[22])
        self.assertEqual(0x00, res[23])

    def test_appliance_from_broadcast(self):
        msg = (
            "837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
            "0000000000000000000000000000"
            "c136771d628d08f90ca694ad1a5893b77c7ea4ac6fed1dc7e2670058df2f44675638"
            "d33cddd5727c581d84b87f54b944bbc7440daf21c3fa9cab7b342b84ac6a630967cd"
            "7d9364d23d4d7a91591e277d90b13be000894715b606127e07c2fecff31443d17c3a"
            "ac03a7656614ae1dca44"
            "8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
        )
        response = binascii.unhexlify(msg)
        token = "TOKEN"
        key = "KEY"
        appliance = LanDevice(data=response, token=token, key=key)
        self.assertEqual("12:34:56:78:9a:bc", appliance.mac)
        self.assertEqual("000000P0000000Q1123456789ABC0000", appliance.sn)
        self.assertEqual("net_a1_9ABC", appliance.ssid)
        self.assertEqual("0xa1", appliance.type)

    def test_appliance_from_broadcast_dehumidifier(self):
        payload = bytearray(binascii.unhexlify(BROADCAST_PAYLOAD))
        encrypted = Security().aes_encrypt(payload)
        msg = (
            f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
            f"0000000000000000000000000000"
            f"{encrypted.hex()}"
            f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
        )
        response = binascii.unhexlify(msg)
        token = "TOKEN"
        key = "KEY"
        appliance = LanDevice(data=response, token=token, key=key)
        self.assertEqual("12:34:56:78:9a:bc", appliance.mac)
        self.assertEqual("000000P0000000Q1123456789ABC0000", appliance.sn)
        self.assertEqual("net_a1_9ABC", appliance.ssid)
        self.assertEqual("0xa1", appliance.type)

    def test_appliance_from_broadcast_ac(self):
        payload = bytearray(binascii.unhexlify(BROADCAST_PAYLOAD))
        payload[46] = 0x63  # Letter c
        payload[66] = int(APPLIANCE_TYPE_AIRCON, base=16)
        encrypted = Security().aes_encrypt(payload)
        msg = (
            f"837000b8200f04035a5a0111a8007a80000000000000000000000000010203040506"
            f"0000000000000000000000000000"
            f"{encrypted.hex()}"
            f"8c53d543ede4d8d26c2008f541b804dc5b24fc8c2735ead584edc8dda92b243d"
        )
        response = binascii.unhexlify(msg)
        token = "TOKEN"
        key = "KEY"
        appliance = LanDevice(data=response, token=token, key=key)
        self.assertEqual("12:34:56:78:9a:bc", appliance.mac)
        self.assertEqual("000000P0000000Q1123456789ABC0000", appliance.sn)
        self.assertEqual("net_ac_9ABC", appliance.ssid)
        self.assertEqual("0xac", appliance.type)
        self.assertEqual("Air conditioner", appliance.state.model)


if __name__ == "__main__":
    log_level = logging.WARNING
    try:
        coloredlogs_install(level=log_level)
    except Exception:
        logging.basicConfig(level=log_level)

    unittest.main()
