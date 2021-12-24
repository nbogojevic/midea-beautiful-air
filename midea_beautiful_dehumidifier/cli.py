""" Discover Midea Humidifiers on local network using command-line """
from __future__ import annotations

# Use colored logs if installed
try:
    from coloredlogs import install as coloredlogs_install
except Exception:

    def coloredlogs_install(level):
        pass


from argparse import ArgumentParser, Namespace
import logging
from time import sleep

from midea_beautiful_dehumidifier import (
    appliance_state,
    connect_to_cloud,
    find_appliances,
)
from midea_beautiful_dehumidifier.appliance import set_watch_level
from midea_beautiful_dehumidifier.lan import LanDevice
from midea_beautiful_dehumidifier.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

_LOGGER = logging.getLogger(__name__)


def output(appliance: LanDevice, show_credentials: bool = False):
    print(f"addr={appliance.ip if appliance.ip else 'Unknown'}:{appliance.port}")
    print(f"        id      = {appliance.id}")
    print(f"        s/n     = {appliance.sn}")
    print(f"        model   = {appliance.model}")
    print(f"        ssid    = {appliance.ssid}")
    print(f"        online  = {appliance.online}")
    print(f"        name    = {getattr(appliance.state, 'name')}")
    print(f"        running = {getattr(appliance.state, 'running')}")
    print(f"        humid%  = {getattr(appliance.state, 'current_humidity')}")
    print(f"        target% = {getattr(appliance.state, 'target_humidity')}")
    print(f"        fan     = {getattr(appliance.state, 'fan_speed')}")
    print(f"        tank    = {getattr(appliance.state, 'tank_full')}")
    print(f"        mode    = {getattr(appliance.state, 'mode')}")
    print(f"        ion     = {getattr(appliance.state, 'ion_mode')}")
    print(f"        error   = {getattr(appliance.state, 'error_code')}")
    if show_credentials:
        print(f"        token   = {appliance.token}")
        print(f"        key     = {appliance.key}")


def run_discover_command(args: Namespace):
    appliances = find_appliances(
        appkey=args.appkey,
        account=args.account,
        password=args.password,
        appid=args.appid,
        networks=args.network,
    )
    for appliance in appliances:
        output(appliance, args.credentials)


def run_status_command(args: Namespace):
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                args.account, args.password, args.appkey, args.appid
            )
            appliance = appliance_state(args.ip, cloud=cloud)
        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return
    else:
        appliance = appliance_state(args.ip, token=args.token, key=args.key)
    if appliance:
        output(appliance, args.credentials)
    else:
        _LOGGER.error("Unable to get appliance status %s", args.ip)


def run_set_command(args: Namespace):
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                args.account, args.password, args.appkey, args.appid
            )
            appliance = appliance_state(args.ip, cloud=cloud)
        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return
    else:
        appliance = appliance_state(args.ip, token=args.token, key=args.key)
    if appliance:
        appliance.set_state(
            target_humidity=args.humidity,
            fan_speed=args.fan,
            mode=args.mode,
            ion_mode=args.ion,
            running=args.on,
        )
        output(appliance, args.credentials)


def run_watch_command(args: Namespace):
    cloud = None
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                args.account, args.password, args.appkey, args.appid
            )
        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return
    else:
        set_watch_level(args.watchlevel)
        if not _LOGGER.isEnabledFor(args.watchlevel):
            try:
                coloredlogs_install(level=args.watchlevel)
            except Exception:
                logging.basicConfig(level=args.watchlevel)
        _LOGGER.info("Watching %s with period %d", args.ip, args.interval)
        try:
            while True:
                appliance = appliance_state(
                    args.ip, token=args.token, key=args.key, cloud=cloud
                )
                if appliance:
                    _LOGGER.log(args.watchlevel, "%r", appliance)
                else:
                    _LOGGER.error("Unable to get appliance status %s", args.ip)
                sleep(args.interval)
        except KeyboardInterrupt:
            _LOGGER.info("Finished watching")


def _add_standard_options(parser: ArgumentParser, with_token: bool = True) -> None:
    if with_token:
        parser.add_argument("--ip", help="IP address of the appliance", required=True)
        parser.add_argument(
            "--token",
            help="token used to communicate with appliance",
            default="",
        )
        parser.add_argument(
            "--key", help="key used to communicate with appliance", default=""
        )
    parser.add_argument(
        "--account", help="Midea app account", default="", required=False
    )
    parser.add_argument(
        "--password", help="Midea app password", default="", required=False
    )
    parser.add_argument(
        "--appkey",
        help="Midea app key",
        default=DEFAULT_APPKEY,
    )
    parser.add_argument(
        "--appid",
        help="Midea app id. Note that appid must correspond to app key",
        default=DEFAULT_APP_ID,
    )
    parser.add_argument(
        "--credentials", action="store_true", help="show credentials in output"
    )


def cli() -> None:
    """Command line interface for the library"""
    parser = ArgumentParser(
        prog="midea-beautiful-dehumidifier-cli",
        description="Discovers and manages Midea dehumidifiers on local network(s).",
    )

    parser.add_argument(
        "--log",
        help="sets the logging level (DEBUG, INFO, WARNING, ERROR or numeric 0-50) ",
        default="WARNING",
        dest="loglevel",
    )
    subparsers = parser.add_subparsers(metavar="subcommand", help="", dest="command")

    parser_discover = subparsers.add_parser(
        "discover",
        help="discovers appliances on local network(s)",
        description="Discovers appliances on local network(s)",
    )
    _add_standard_options(parser_discover, False)
    parser_discover.add_argument(
        "--network",
        nargs="+",
        help="network addresses or range(s) for discovery (e.g. 192.0.0.0/24).",
    )

    parser_status = subparsers.add_parser(
        "status",
        help="gets status from appliance",
        description="Gets status from appliance.",
    )
    _add_standard_options(parser_status)

    parser_set = subparsers.add_parser(
        "set",
        help="sets status of appliance",
        description="Sets status of an appliance.",
    )
    _add_standard_options(parser_set)
    parser_set.add_argument("--humidity", help="target humidity", default=None)
    parser_set.add_argument("--fan", help="fan strength", default=None)
    parser_set.add_argument("--mode", help="dehumidifier mode switch", default=None)
    parser_set.add_argument("--ion", help="ion mode switch", default=None)
    parser_set.add_argument("--on", help="turn on/off", default=None)
    parser_watch = subparsers.add_parser(
        "watch",
        help="watches status of appliance",
        description="Watches status of an appliance.",
    )
    _add_standard_options(parser_watch)
    parser_watch.add_argument(
        "--interval", help="time to sleep between polling", default=10, type=int
    )
    parser_watch.add_argument(
        "--watchlevel", help="level of watch logging", default=20, type=int
    )
    args = parser.parse_args()

    log_level = int(args.loglevel) if args.loglevel.isdigit() else args.loglevel
    try:
        coloredlogs_install(level=log_level)
    except Exception:
        logging.basicConfig(level=log_level)

    if args.command == "discover":
        run_discover_command(args)

    elif args.command == "status":
        run_status_command(args)

    elif args.command == "set":
        run_set_command(args)

    elif args.command == "watch":
        run_watch_command(args)


if __name__ == "__main__":
    cli()
