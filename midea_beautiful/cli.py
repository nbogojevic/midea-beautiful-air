""" Discover Midea Humidifiers on local network using command-line """
from __future__ import annotations

from argparse import ArgumentParser, Namespace
from binascii import unhexlify
import importlib
import logging
import pprint
import sys
from typing import Any, Sequence, cast

from midea_beautiful import appliance_state, connect_to_cloud, find_appliances
from midea_beautiful.appliance import AirConditionerAppliance, DehumidifierAppliance
from midea_beautiful.cloud import MideaCloud
from midea_beautiful.command import AirConditionerResponse, DehumidifierResponse
from midea_beautiful.lan import LanDevice
from midea_beautiful.midea import (
    DEFAULT_API_SERVER_URL,
    DEFAULT_APP_ID,
    DEFAULT_APPKEY,
    DEFAULT_HMACKEY,
    DEFAULT_IOTKEY,
    DEFAULT_SIGNKEY,
)
from midea_beautiful.util import Redacted, very_verbose

_LOGGER = logging.getLogger(__name__)


def _logs_install(level, **kw) -> None:
    try:
        module = importlib.import_module(kw.get("logmodule", "coloredlogs"))
        module.install(level=level, **kw)
    except Exception:  # pylint: disable=broad-except
        logging.basicConfig(level=level)


def _output(appliance: LanDevice, show_credentials: bool = False) -> None:
    print(f"id {appliance.serial_number}/{appliance.appliance_id}")
    print(f"  id      = {appliance.appliance_id}")
    print(f"  addr    = {appliance.address if appliance.address else 'Unknown'}")
    print(f"  s/n     = {appliance.serial_number}")
    print(f"  model   = {appliance.model}")
    print(f"  ssid    = {appliance.ssid}")
    print(f"  online  = {appliance.online}")
    print(f"  name    = {appliance.name}")
    if DehumidifierAppliance.supported(appliance.type):
        state = cast(DehumidifierAppliance, appliance.state)
        print(f"  running = {state.running}")
        print(f"  humid%  = {state.current_humidity}")
        print(f"  target% = {state.target_humidity}")
        print(f"  temp    = {state.current_temperature}")
        print(f"  fan     = {state.fan_speed}")
        print(f"  tank    = {state.tank_full}")
        print(f"  mode    = {state.mode}")
        print(f"  ion     = {state.ion_mode}")
        print(f"  filter  = {state.filter_indicator}")
        print(f"  pump    = {state.pump}")
        print(f"  defrost = {state.defrosting}")
        print(f"  sleep   = {state.sleep_mode}")
    elif AirConditionerAppliance.supported(appliance.type):
        state = cast(AirConditionerAppliance, appliance.state)
        print(f"  running = {state.running}")
        print(f"  target  = {state.target_temperature}")
        print(f"  indoor  = {state.indoor_temperature}")
        print(f"  outdoor = {state.outdoor_temperature}")
        print(f"  fan     = {state.fan_speed}")
        print(f"  mode    = {state.mode}")
        print(f"  purify  = {state.purifier}")
        print(f"  eco     = {state.eco_mode}")
        print(f"  sleep   = {state.comfort_sleep}")
        print(f"  F       = {state.fahrenheit}")

    print(f"  error   = {getattr(appliance.state, 'error_code')}")
    print(f"  supports= {getattr(appliance.state, 'capabilities')}")

    print(f"  version = {appliance.version}")

    if show_credentials:
        print(f"  token   = {appliance.token}")
        print(f"  key     = {appliance.key}")


def _run_discover_command(args: Namespace) -> int:
    appliances = find_appliances(
        appkey=args.appkey,
        account=args.account,
        password=args.password,
        appname=args.app,
        appid=args.appid,
        addresses=args.address,
        hmackey=args.hmackey,
        iotkey=args.iotkey,
        api_url=args.apiurl,
        proxied="v5" if args.proxied else None,
    )
    for appliance in appliances:
        _output(appliance, args.credentials)
    return 0


def _check_ip_id(args: Namespace) -> bool:
    if args.ip and args.id:
        _LOGGER.error("Both ip address and id provided. Please provide only one")
        return False
    if not args.ip and not args.id:
        _LOGGER.error("Missing ip address or appliance id")
        return False
    return True


def _run_dump_command(args: Namespace) -> int:
    data = unhexlify(args.payload)
    appliance: DehumidifierResponse | AirConditionerResponse
    if args.dehumidifier:
        appliance = DehumidifierResponse(data)
    elif args.airconditioner:
        appliance = AirConditionerResponse(data)
    else:
        return 21
    for i, byt in enumerate(data):
        print(f"{i:2d} {byt:3d} {byt:2x}")
    pprint.pprint(appliance.__dict__)
    return 0


def _run_status_command(args: Namespace) -> int:
    if not _check_ip_id(args):
        return 7
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                account=args.account,
                password=args.password,
                appname=args.app,
                appkey=args.appkey,
                appid=args.appid,
                hmackey=args.hmackey,
                iotkey=args.iotkey,
                api_url=args.apiurl,
                proxied="v5" if args.proxied else None,
            )
            appliance = appliance_state(
                address=args.ip, cloud=cloud, use_cloud=args.cloud, appliance_id=args.id
            )

        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return 8
    else:
        appliance = appliance_state(
            address=args.ip, token=args.token, key=args.key, appliance_id=args.id
        )
    if appliance:
        _output(appliance, args.credentials)
    else:
        _LOGGER.error(
            "Unable to get appliance status for '%s'",
            args.ip or args.id,
        )
        return 9
    return 0


_COMMON_ARGUMENTS = [
    "account",
    "apiurl",
    "app",
    "appid",
    "appkey",
    "cloud",
    "command",
    "credentials",
    "hmackey",
    "id",
    "iotkey",
    "ip",
    "key",
    "loglevel",
    "no_redact",
    "signkey",
    "verbose",
    "password",
    "proxied",
    "token",
]


def _process_attr_arguments(
    args: Namespace, appliance: LanDevice, cloud: MideaCloud | None
):
    all_args = {**vars(args)}
    typ = type(appliance.state)
    for arg in _COMMON_ARGUMENTS:
        all_args.pop(arg)

    set_args: dict[str, Any] = {}
    for attr in dir(typ):
        if not attr.startswith("_") and attr not in _EXCLUDED_PROPERTIES:
            if all_args.get(attr) is not None:
                prop_candidate = getattr(typ, attr)
                if isinstance(prop_candidate, property):
                    if prop_candidate.fset:
                        _LOGGER.debug(
                            "Setting attribute '%s' to %r", attr, all_args[attr]
                        )
                        set_args[attr] = all_args[attr]
                    else:
                        _LOGGER.warning("Read-only attribute '%s'", attr)
                        return 10
        all_args.pop(attr, None)

    unused_args = []
    for unused, value in all_args.items():
        if value is not None:
            unused_args.append(unused)
    if len(unused_args) > 0:
        _LOGGER.error("Not applicable options: %s", unused_args)
        return 11
    if cloud:
        set_args["cloud"] = cloud
    appliance.set_state(**set_args)
    _output(appliance, args.credentials)
    return 0


def _run_set_command(args: Namespace) -> int:
    if not _check_ip_id(args):
        return 7
    cloud = None
    if not args.token:
        if args.account and args.password:
            cloud = connect_to_cloud(
                account=args.account,
                password=args.password,
                appname=args.app,
                appkey=args.appkey,
                appid=args.appid,
                hmackey=args.hmackey,
                iotkey=args.iotkey,
                api_url=args.apiurl,
                proxied="v5" if args.proxied else None,
            )
            appliance = appliance_state(
                address=args.ip, cloud=cloud, use_cloud=args.cloud, appliance_id=args.id
            )
        else:
            _LOGGER.error("Missing token/key or cloud credentials")
            return 8
    else:
        appliance = appliance_state(
            address=args.ip, token=args.token, key=args.key, appliance_id=args.id
        )

    if not appliance:
        _LOGGER.error(
            "Unable to get appliance status id=%s",
            args.ip if hasattr(args, "ip") else args.id,
        )
        return 9

    return _process_attr_arguments(args, appliance, cloud)


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
    parser.add_argument("--app", help="Midea app being used", default=None)
    parser.add_argument("--appkey", help="Midea app key", default=DEFAULT_APPKEY)
    parser.add_argument(
        "--appid",
        help="Midea app id. Note that appid must correspond to app key",
        default=DEFAULT_APP_ID,
    )
    parser.add_argument("--hmackey", help="Midea HMAC key", default=DEFAULT_HMACKEY)
    parser.add_argument(
        "--apiurl", help="Midea API server url", default=DEFAULT_API_SERVER_URL
    )
    parser.add_argument("--iotkey", help="Midea IOT key", default=DEFAULT_IOTKEY)
    parser.add_argument("--signkey", help="Midea sign key", default=DEFAULT_SIGNKEY)
    parser.add_argument(
        "--credentials", action="store_true", help="show credentials in output"
    )
    parser.add_argument(
        "--proxied",
        help="activates proxy api",
        action="store_true",
        dest="proxied",
    )


def cli(argv: Sequence[str] | None = None) -> int:
    """Command line interface for the library"""
    if argv is None:
        argv = sys.argv[1:]
    parser = _configure_argparser()
    args = parser.parse_args(argv)

    log_level = int(args.loglevel) if args.loglevel.isdigit() else args.loglevel
    if "no_redact" in args and args.no_redact:
        Redacted.redacting = False
    if "verbose" in args and args.verbose:
        very_verbose(True)
    _logs_install(
        level=log_level,
        level_styles=dict(
            debug=dict(color="green"),
            verbose=dict(color="blue"),
            info=dict(),
            warning=dict(color="yellow"),
            error=dict(color="red"),
            critical=dict(color="red", bold=True),
        ),
    )

    commands = {
        "discover": _run_discover_command,
        "status": _run_status_command,
        "set": _run_set_command,
        "dump": _run_dump_command,
    }

    function = commands.get(args.command, lambda _: 1)

    return function(args)


def _configure_argparser():
    parser = ArgumentParser(
        prog="midea-beautiful-air-cli",
        description=(
            "Discovers and manages Midea air conditioners"
            " and dehumidifiers on local network."
        ),
    )

    parser.add_argument(
        "--log",
        help="sets the logging level (DEBUG, INFO, WARNING, ERROR or numeric 0-50) ",
        default="WARNING",
        dest="loglevel",
    )
    parser.add_argument(
        "--no-redact",
        help="disables redacting sensitive information in logs",
        action="store_true",
        dest="no_redact",
    )
    parser.add_argument(
        "--verbose",
        help="activates very verbose logging",
        action="store_true",
        dest="verbose",
    )
    subparsers = parser.add_subparsers(metavar="subcommand", help="", dest="command")

    parser_discover = subparsers.add_parser(
        "discover",
        help="discovers appliances on local network",
        description="Discovers appliances on local network",
    )
    _add_standard_options(parser_discover)
    parser_discover.add_argument(
        "--address",
        nargs="+",
        help="network addresses for discovery (e.g. 192.0.2.2 or 192.0.2.255).",
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

    parser_dump = subparsers.add_parser(
        "dump",
        help="dumps parsed status payload",
        description="Processes status payload and displays result",
    )
    parser_dump.add_argument("--dehumidifier", action="store_true")
    parser_dump.add_argument("--airconditioner", action="store_true")
    parser_dump.add_argument(
        "--payload", help="status payload in hexadecimal form", required=True
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
                prop_candidate = getattr(typ, attr)
                if isinstance(prop_candidate, property) and prop_candidate.fset:
                    metavar = attr.upper()
                    opt = attr.replace("_", "-")
                    desc = prop_candidate.__doc__ or attr.replace("_", " ")
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
    sys.exit(cli(sys.argv[1:]))
