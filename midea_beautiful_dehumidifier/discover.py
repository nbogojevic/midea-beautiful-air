""" Discover Midea Humidifiers on local network using command-line """
from __future__ import annotations

try:
    from coloredlogs import install as coloredlogs_install
except:
    def coloredlogs_install(level):
        pass
import argparse
import logging

from midea_beautiful_dehumidifier import find_devices

_LOGGER = logging.getLogger(__name__)


account = ""
password = ""
app_key = "3742e9e5842d4ad59c2db887e12449f9"
use_midea_cloud = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Discover Midea dehumidifiers.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--account', required=True)
    parser.add_argument('--password', required=True)

    args = parser.parse_args()
    try:
        coloredlogs_install(level='DEBUG' if args.debug else 'INFO')
    except:
        logging.basicConfig(
            level=logging.DEBUG if args.debug else logging.INFO)
    account = args.account
    password = args.password
    devices = find_devices(app_key=app_key, account=account, password=password)
    for device in devices:
        _LOGGER.debug("Device: %s", device)
