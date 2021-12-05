from __future__ import annotations

try:
    from coloredlogs import install as coloredlogs_install
except:
    def coloredlogs_install(level):
        pass
import logging

import asyncio

from midea_client_scanner import async_find_devices

VERSION = '0.1.40'

_LOGGER = logging.getLogger(__name__)

"""
# 'ip': '10.0.4.210', 'id': 18691697890837, 'port': 6444, 'token': '3B662D0297A0246B9DCBDFF1C8D4B8E6C9309430FDF21B0262D48BBA263BC4098C1035800F2C0395DA43BC9DCA7AFA5AFCFE085149B3727C162E5B192CBB952F', 'key': '45E80C1E977B41C097A9CD3DAB580EFF0235804A62E84701B38CF6A716FFB689', 'ssid': 'net_a1_B5B1'
# 'ip': '10.0.7.130', 'id': 31885837452002, 'port': 6444, 'token': '9761A7A156C10906F29F78916824DB0388A32A8CE7F6DED9574BDED9B8EBEB18ABB0C952AAFC9D15B3A64249798E3997C7A96542BEE1F0D2FA36CC1DFECA8D78', 'key': 'D1D51863F5C3481A96F1A8EC019AC0DD0905D339F555462390F5130149783197', 'ssid': 'net_a1_7D60'
"""


app_key = "3742e9e5842d4ad59c2db887e12449f9"
use_midea_cloud = False

if __name__ == "__main__":
    try:
        coloredlogs_install(level='DEBUG')
    except:
        logging.basicConfig(level=logging.DEBUG)
    _LOGGER.info("Allocating new event loop")
    loop = asyncio.new_event_loop()
    try:
        devices = loop.run_until_complete(async_find_devices(app_key=app_key, account=account, password=password))
        for device in devices: 
            _LOGGER.debug("Device: %s", device)
    finally:
        loop.close()
