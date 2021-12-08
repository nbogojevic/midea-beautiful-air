""" Discover Midea Humidifiers on local network using command-line """
from __future__ import annotations

try:
    from coloredlogs import install as coloredlogs_install
except:
    def coloredlogs_install(level):
        pass
import argparse
import logging

from midea_beautiful_dehumidifier import device_status, find_devices
from midea_beautiful_dehumidifier.lan import LanDevice


def output(device: LanDevice, show_credentials: bool = False):
    print(f"addr={device.ip}:{device.port}")
    print(f"        id      = {device.id}")
    print(f"        name    = {device.state.name}")
    print(f"        hum%    = {device.state.current_humidity}")
    print(f"        target% = {device.state.target_humidity}")
    print(f"        fan     = {device.state.fan_speed}")
    print(f"        tank    = {device.state.tank_full}")
    print(f"        mode    = {device.state.mode}")
    print(f"        ion     = {device.state.ion_mode}")
    if show_credentials:
        print(f"        token   = {device.token}")
        print(f"        key     = {device.key}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="midea_beautiful_dehumidifier.cli",
        description='Discovers Midea dehumidifiers on local network.')

    parser.add_argument('--log', help='sets logging level', default='WARNING', choices=['DEBUG', 'INFO', 'WARNING'])
    subparsers = parser.add_subparsers(help='sub-commands', dest="command")
    parser_discover = subparsers.add_parser('discover', help='discovers devices on local network')
    parser_discover.add_argument('--account', help='Midea cloud account', required=True)
    parser_discover.add_argument('--password', help='Midea cloud password', required=True)
    parser_discover.add_argument('--appkey', help='Midea app key', default='3742e9e5842d4ad59c2db887e12449f9')
    parser_discover.add_argument('--credentials', action='store_true', help='show credentials')

    parser_status = subparsers.add_parser('status', help='gets status from device')
    parser_status.add_argument('--ip', help='IP address of the device', required=True)
    parser_status.add_argument('--port', help='port of the device', default=6444)
    parser_status.add_argument('--token', help='token used to communicate with device', default=None)
    parser_status.add_argument('--key', help='key used to communicate with device', default=None)
    parser_status.add_argument('--credentials', action='store_true', help='show credentials')
    parser_status.add_argument('--account', help='Midea cloud account', default=None)
    parser_status.add_argument('--password', help='Midea cloud password', default=None)

    parser_set = subparsers.add_parser('set', help='sets status of device')
    parser_set.add_argument('--ip', help='IP address of the device', required=True)
    parser_set.add_argument('--port', help='port of the device', default=6444)
    parser_set.add_argument('--token', help='token used to communicate with device', default=None)
    parser_set.add_argument('--key', help='key used to communicate with device', default=None)
    parser_set.add_argument('--credentials', action='store_true', help='show credentials')
    parser_set.add_argument('--humidity', help='target humidity')
    parser_set.add_argument('--fan', help='fan strength')
    parser_set.add_argument('--ion', help='ion mode switch')


    args = parser.parse_args()
    try:
        coloredlogs_install(level=args.log)
    except:
        logging.basicConfig(level=args.log)

    if args.command == 'discover':
        devices = find_devices(app_key=args.appkey, account=args.account, password=args.password)
        for device in devices:
            output(device, args.credentials)

    elif args.command == 'status':
        device = device_status(args.ip, int(args.port), token=args.token, key=args.key)
        if device is not None:
            output(device, args.credentials)

