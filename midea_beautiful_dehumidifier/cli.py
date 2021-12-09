""" Discover Midea Humidifiers on local network using command-line """
from __future__ import annotations

try:
    from coloredlogs import install as coloredlogs_install
except Exception:

    def coloredlogs_install(level):
        pass


import argparse
import logging

from midea_beautiful_dehumidifier import appliance_state, find_appliances
from midea_beautiful_dehumidifier.lan import LanDevice


def output(appliance: LanDevice, show_credentials: bool = False):
    print(f"addr={appliance.ip}:{appliance.port}")
    print(f"        id      = {appliance.id}")
    print(f"        name    = {appliance.state.name}")
    print(f"        hum%    = {appliance.state.current_humidity}")
    print(f"        target% = {appliance.state.target_humidity}")
    print(f"        fan     = {appliance.state.fan_speed}")
    print(f"        tank    = {appliance.state.tank_full}")
    print(f"        mode    = {appliance.state.mode}")
    print(f"        ion     = {appliance.state.ion_mode}")
    if show_credentials:
        print(f"        token   = {appliance.token}")
        print(f"        key     = {appliance.key}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="midea_beautiful_dehumidifier.cli",
        description="Discovers Midea dehumidifiers on local network.",
    )

    parser.add_argument(
        "--log",
        help="sets logging level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING"],
    )
    subparsers = parser.add_subparsers(help="sub-commands", dest="command")
    parser_discover = subparsers.add_parser(
        "discover", help="discovers appliances on local network"
    )
    parser_discover.add_argument(
        "--account", help="Midea cloud account", required=True
    )
    parser_discover.add_argument(
        "--password", help="Midea cloud password", required=True
    )
    parser_discover.add_argument(
        "--appkey",
        help="Midea app key",
        default="3742e9e5842d4ad59c2db887e12449f9",
    )
    parser_discover.add_argument(
        "--credentials", action="store_true", help="show credentials"
    )

    parser_status = subparsers.add_parser(
        "status", help="gets status from appliance"
    )
    parser_status.add_argument(
        "--ip", help="IP address of the appliance", required=True
    )
    parser_status.add_argument(
        "--port", help="port of the appliance", default=6444
    )
    parser_status.add_argument(
        "--token",
        help="token used to communicate with appliance",
        default=None,
    )
    parser_status.add_argument(
        "--key", help="key used to communicate with appliance", default=None
    )
    parser_status.add_argument(
        "--credentials", action="store_true", help="show credentials"
    )
    parser_status.add_argument(
        "--account", help="Midea cloud account", default=None
    )
    parser_status.add_argument(
        "--password", help="Midea cloud password", default=None
    )

    parser_set = subparsers.add_parser("set", help="sets status of appliance")
    parser_set.add_argument(
        "--ip", help="IP address of the appliance", required=True
    )
    parser_set.add_argument(
        "--port", help="port of the appliance", default=6444
    )
    parser_set.add_argument(
        "--token",
        help="token used to communicate with appliance",
        default=None,
    )
    parser_set.add_argument(
        "--key", help="key used to communicate with appliance", default=None
    )
    parser_set.add_argument(
        "--credentials", action="store_true", help="show credentials"
    )
    parser_set.add_argument(
        "--humidity", help="target humidity", default=None
    )
    parser_set.add_argument("--fan", help="fan strength", default=None)
    parser_set.add_argument(
        "--mode", help="dehumidifier mode switch", default=None
    )
    parser_set.add_argument("--ion", help="ion mode switch", default=None)
    parser_set.add_argument("--on", help="turn on/off", default=None)

    args = parser.parse_args()
    try:
        coloredlogs_install(level=args.log)
    except Exception:
        logging.basicConfig(level=args.log)

    if args.command == "discover":
        appliances = find_appliances(
            app_key=args.appkey, account=args.account, password=args.password,
            broadcast_retries=2,
            broadcast_timeout=3

        )
        for appliance in appliances:
            output(appliance, args.credentials)

    elif args.command == "status":
        appliance = appliance_state(
            args.ip, int(args.port), token=args.token, key=args.key
        )
        if appliance is not None:
            output(appliance, args.credentials)

    elif args.command == "set":
        appliance = appliance_state(
            args.ip, int(args.port), token=args.token, key=args.key
        )
        if appliance is not None:
            appliance.set_state(
                target_humidity=args.humidity,
                fan_speed=args.fan,
                mode=args.mode,
                ion=args.ion,
                is_on=args.on,
            )
            output(appliance, args.credentials)
