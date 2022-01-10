""" Discover Midea Humidifiers on local network using command-line """
from __future__ import annotations

import importlib
import sys
from typing import Any

from midea_beautiful.util import SPAM, TRACE

from argparse import ArgumentParser, Namespace
import logging

from midea_beautiful import appliance_state, connect_to_cloud, find_appliances
from midea_beautiful.appliance import (
    AirConditionerAppliance,
    DehumidifierAppliance,
)
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import DEFAULT_APP_ID, DEFAULT_APPKEY

_LOGGER = logging.getLogger(__name__)


def logs_install(level, **kw) -> None:
    try:
        module = importlib.import_module(kw.get("logmodule", "coloredlogs"))
        module.install(level=level, **kw)
    except Exception:
        logging.basicConfig(level=level)


def output(appliance: LanDevice, show_credentials: bool = False) -> None:
    print(f"id {appliance.unique_id}")
    print(f"  id      = {appliance.id}")
    print(f"  addr    = {appliance.ip if appliance.ip else 'Unknown'}")
    print(f"  s/n     = {appliance.sn}")
    print(f"  model   = {appliance.model}")
    print(f"  ssid    = {appliance.ssid}")
    print(f"  online  = {appliance.online}")
    print(f"  name    = {appliance.state.name}")
    if DehumidifierAppliance.supported(appliance.type):
        assert isinstance(appliance.state, DehumidifierAppliance)
        print(f"  running = {appliance.state.running}")
        print(f"  humid%  = {appliance.state.current_humidity}")
        print(f"  target% = {appliance.state.target_humidity}")
        print(f"  temp    = {appliance.state.current_temperature}")
        print(f"  fan     = {appliance.state.fan_speed}")
        print(f"  tank    = {appliance.state.tank_full}")
        print(f"  mode    = {appliance.state.mode}")
        print(f"  ion     = {appliance.state.ion_mode}")
        print(f"  filter  = {appliance.state.filter_indicator}")
        print(f"  pump    = {appliance.state.pump}")
        print(f"  defrost = {appliance.state.defrosting}")
        print(f"  sleep   = {appliance.state.sleep_mode}")
    elif AirConditionerAppliance.supported(appliance.type):
        assert isinstance(appliance.state, AirConditionerAppliance)
        print(f"  running = {appliance.state.running}")
        print(f"  target  = {appliance.state.target_temperature}")
        print(f"  indoor  = {appliance.state.indoor_temperature}")
        print(f"  outdoor = {appliance.state.outdoor_temperature}")
        print(f"  fan     = {appliance.state.fan_speed}")
        print(f"  mode    = {appliance.state.mode}")
        print(f"  purify  = {appliance.state.purifier}")
        print(f"  eco     = {appliance.state.eco_mode}")
        print(f"  sleep   = {appliance.state.comfort_sleep}")
        print(f"  F       = {appliance.state.fahrenheit}")

    print(f"  error   = {getattr(appliance.state, 'error_code')}")
    print(f"  supports= {getattr(appliance.state, 'supports')}")

    print(f"  version = {appliance.version}")

    if show_credentials:
        print(f"  token   = {appliance.token}")
        print(f"  k1      = {appliance.k1}")


def run_discover_command(args: Namespace) -> int:
    appliances = find_appliances(
        appkey=args.appkey,
        account=args.account,
        password=args.password,
        appid=args.appid,
        networks=args.network,
    )
    for appliance in appliances:
        output(appliance, args.credentials)
    return 0


def _check_ip_id(args: Namespace) -> bool:
    if args.ip and args.id:
        _LOGGER.error("Both ip address and id provided. Please provide only one")
        return False
    if not args.ip and not args.id:
        _LOGGER.error("Missing ip or appliance id")
        return False
    return True


def run_status_command(args: Namespace) -> int:
    if not _check_ip_id(args):
        return 7
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                args.account, args.password, args.appkey, args.appid
            )
            appliance = appliance_state(
                ip=args.ip, cloud=cloud, use_cloud=args.cloud, id=args.id
            )

        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return 8
    else:
        appliance = appliance_state(
            ip=args.ip, token=args.token, key=args.key, id=args.id
        )
    if appliance:
        output(appliance, args.credentials)
    else:
        _LOGGER.error(
            "Unable to get appliance status for '%s'",
            args.ip or args.id,
        )
        return 9
    return 0


_COMMON_ARGUMENTS = [
    "account",
    "appid",
    "appkey",
    "cloud",
    "command",
    "credentials",
    "id",
    "ip",
    "key",
    "loglevel",
    "password",
    "token",
]


def run_set_command(args: Namespace) -> int:
    if not _check_ip_id(args):
        return 7
    cloud = None
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                args.account, args.password, args.appkey, args.appid
            )
            appliance = appliance_state(
                ip=args.ip, cloud=cloud, use_cloud=args.cloud, id=args.id
            )
        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return 8
    else:
        appliance = appliance_state(
            ip=args.ip, token=args.token, key=args.key, id=args.id
        )

    if not appliance:
        _LOGGER.error(
            "Unable to get appliance status id=%s",
            args.ip if hasattr(args, "ip") else args.id,
        )
        return 9

    all_args = {**vars(args)}
    typ = type(appliance.state)
    for a in _COMMON_ARGUMENTS:
        all_args.pop(a)

    set_args: dict[str, Any] = {}
    for attr in dir(typ):
        if not attr.startswith("_") and attr not in _EXCLUDED_PROPERTIES:
            if all_args.get(attr) is not None:
                p = getattr(typ, attr)
                if isinstance(p, property):
                    if p.fset:
                        _LOGGER.debug(
                            "Setting attribute '%s' to %r", attr, all_args[attr]
                        )
                        set_args[attr] = all_args[attr]
                    else:
                        _LOGGER.warning("Read-only attribute '%s'", attr)
                        return 10
        all_args.pop(attr, None)

    unused_args = []
    for u, v in all_args.items():
        if v is not None:
            unused_args.append(u)
    if len(unused_args) > 0:
        _LOGGER.error("Not applicable options: %s", unused_args)
        return 11
    if cloud:
        set_args["cloud"] = cloud
    appliance.set_state(**set_args)
    output(appliance, args.credentials)
    return 0


def _add_standard_options(parser: ArgumentParser) -> None:
    parser.add_argument("--ip", help="IP address of the appliance")
    parser.add_argument("--id", help="appliance id")
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


def cli(argv) -> int:
    """Command line interface for the library"""
    parser = configure_argparser()
    args = parser.parse_args(argv)

    log_level = int(args.loglevel) if args.loglevel.isdigit() else args.loglevel
    logging.addLevelName(TRACE, "TRACE")
    logging.addLevelName(SPAM, "SPAM")
    logs_install(
        level=log_level,
        level_styles=dict(
            spam=dict(color="white", faint=True),
            trace=dict(color="green", faint=True),
            debug=dict(color="green"),
            verbose=dict(color="blue"),
            info=dict(),
            warning=dict(color="yellow"),
            error=dict(color="red"),
            critical=dict(color="red", bold=True),
        ),
    )

    commands = {
        "discover": run_discover_command,
        "status": run_status_command,
        "set": run_set_command,
    }

    fn = commands.get(args.command, lambda _: 1)

    return fn(args)


def configure_argparser():
    parser = ArgumentParser(
        prog="midea-beautiful-air-cli",
        description=(
            "Discovers and manages Midea air conditioners"
            " and dehumidifiers on local network(s)."
        ),
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
    _add_standard_options(parser_discover)
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
    parser_status.add_argument("--cloud", action="store_true")

    parser_set = subparsers.add_parser(
        "set",
        help="sets status of appliance",
        description="Sets status of an appliance.",
    )
    _add_standard_options(parser_set)
    parser_set.add_argument("--cloud", action="store_true")

    attrs = _settings_arguments()

    group = parser_set.add_argument_group("set attribute arguments")

    for attr, item in attrs.items():
        group.add_argument(
            f"--{attr}", help=f"{item['desc']})", metavar=item["metavar"], default=None
        )

    return parser


def _settings_arguments():
    objs = {
        DehumidifierAppliance: "dehumidifier",
        AirConditionerAppliance: "air conditioner",
    }
    attrs: dict[str, Any] = {}
    for typ, name in objs.items():
        for attr in dir(typ):
            if not attr.startswith("_") and attr not in _EXCLUDED_PROPERTIES:
                p = getattr(typ, attr)
                if isinstance(p, property) and p.fset:
                    metavar = attr.upper()
                    opt = attr.replace("_", "-")
                    desc = p.__doc__ or attr.replace("_", " ")
                    if attrs.get(opt):
                        attrs[opt]["desc"] = f"{attrs[opt]['desc']}, {name}"
                    else:
                        attrs[opt] = {
                            "desc": f"{desc} ({name}",
                            "metavar": metavar,
                        }

    return attrs


_EXCLUDED_PROPERTIES = ["name"]

if __name__ == "__main__":
    ret = cli(sys.argv[1:])
    exit(ret)
