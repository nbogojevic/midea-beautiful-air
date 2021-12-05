from __future__ import annotations

try:
    from coloredlogs import install as coloredlogs_install
except:
    def coloredlogs_install(level):
        pass
import logging

import argparse
import asyncio

from midea_beautiful_dehumidifier.scanner import async_find_devices

VERSION = '0.1.40'

_LOGGER = logging.getLogger(__name__)


account = ""
password = ""
app_key = "3742e9e5842d4ad59c2db887e12449f9"
use_midea_cloud = False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Discover Midea dehumidifiers.')
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--account', required=True)
    parser.add_argument('--password', required=True)

    args = parser.parse_args()
    try:
        coloredlogs_install(level='DEBUG' if args.debug else 'INFO')
    except:
        logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    account = args.account
    password = args.password
    _LOGGER.debug("Allocating new event loop")
    loop = asyncio.new_event_loop()
    try:
        devices = loop.run_until_complete(async_find_devices(app_key=app_key, account=account, password=password))
        for device in devices: 
            _LOGGER.debug("Device: %s", device)
    finally:
        loop.close()
