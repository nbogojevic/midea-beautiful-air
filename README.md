This is a library that allows communication with Midea dehumidifier appliances via the local area network.

# midea-beautiful-dehumidifier
[![Build Status](https://github.com/nbogojevic/midea-beautiful-dehumidifier/actions/workflows/python-publish.yml/badge.svg)](https://github.com/nbogojevic/midea-beautiful-dehumidifier/actions/workflows/python-publish.yml)
[![PyPI](https://img.shields.io/pypi/v/midea_beautiful_dehumidifier.svg?maxAge=3600)](https://pypi.org/project/midea_beautiful_dehumidifier/)

This library allows discovering Midea dehumidifiers on local network, getting their state and controlling then. The name comes from Chinese name for Midea (美的) which translates to _beautiful_ in English. 

This library inspired from the repository at [mac-zhou/midea-msmart](https://github.com/mac-zhou/midea-msmart) which provides similar functionality for air conditioners.


Thanks for [yitsushi's project](https://github.com/yitsushi/midea-air-condition), [NeoAcheron's project](https://github.com/NeoAcheron/midea-ac-py), [andersonshatch's project](https://github.com/andersonshatch/midea-ac-py), [barban's project](https://github.com/barban-dev/midea_inventor_dehumidifier)


## Supported appliances

The library works only Midea dehumidifiers supporting V3 protocol. Both appliances with and without ion function are supported.

Some examples of supported dehumidifiers:

* Comfee MDDF-16DEN7-WF or MDDF-20DEN7-WF (tested with 20L version)
* Inventor EVA ΙΟΝ Pro Wi-Fi (EP3-WiFi 16L/20L) (tested with 20L version)
* Inventor Eva II Pro Wi-Fi (EVP-WF16L/20L)
* Pro Breeze 30L Smart Dehumidifier with Wifi / App Control

It may as well work with other Midea Wi-Fi dehumidifiers.

## Dehumidifier data

The following dehumidifier data is accessible via library: 

* on/off switch (boolean, can be set)
* current humidity (read-only)
* target humidity (can be set)
* active mode (can be set)
* fan speed (can be set)
* ion switch status (boolean, can be set)
* tank is full (boolean, read-only)
* appliance name (read-only). This one is set through Midea application.
* appliance serial number (read-only) 
* appliance IPv4 address (read-only)
* token and key for local network access (read-only)


## Discovery

This library discovers appliances on local network. This is done by broadcasting UDP packets on all local networks interfaces to ports 6445. Appliances will respond to this broadcast with their description packet. Following discovery, communication switchers to TCP over port 6444. This communication is encrypted, and the library needs a token and a key for each appliance. This can be either provided or retrieved from Midea app account. The library can also retrieve the list of registered appliances from Midea app account and obtain additional information for devices (eg. name). 

Library connects to Midea cloud API using credentials from NetHome Plus mobile app. You can use other Midea app mobile applications if you obtain their application key and id. See [midea_beautiful_dehumidifier/midea.py](midea_beautiful_dehumidifier/midea.py) for some examples. Application key and application id must match, otherwise library won't be able to sign in.

The discovery should work on Linux and Windows based systems, however it doesn't work in Windows Subsystem for Linux and may not work in Docker containers or VMs depending on network setup. For example, VM or container needs to have rights to broadcast to physical network to make discovery work. On workaround is to run discovery from non-virtualized environment host. 


## Logging

Library logs additional information at log level 5. Credential information like username, password or token keys will never be logged, but you can use command line tool to display token and key data. 


## Usage

Install package:

```shell
pip install midea-beautiful-dehumidifier
```

### Command line tool

Help for command line tool:

```shell
python -m midea_beautiful_dehumidifier.cli --help
python -m midea_beautiful_dehumidifier.cli discover --help
python -m midea_beautiful_dehumidifier.cli set --help
python -m midea_beautiful_dehumidifier.cli status --help
```

Discover dehumidifier appliances on the local network:

```shell
pip install midea-beautiful-dehumidifier
python -m midea_beautiful_dehumidifier.cli discover --account ACCOUNT_EMAIL --password PASSWORD
# Show tokens used to connect to appliances via local network
python -m midea_beautiful_dehumidifier.cli discover --account ACCOUNT_EMAIL --password PASSWORD --credentials
```

Get status of an appliance:

```shell
pip install midea-beautiful-dehumidifier
python -m midea_beautiful_dehumidifier.cli status --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY
```

`TOKEN` and `KEY` can be retrieved using `discover` command.

Set appliance attribute (target humidity, mode, ion switch, fan speed):

```shell
pip install midea-beautiful-dehumidifier
python -m midea_beautiful_dehumidifier.cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --mode MODE
```

### Code

Discover appliances on local network:

```python
from midea_beautiful_dehumidifier import find_appliances

appliances = find_appliances(
    account=USER_EMAIL,
    password=PASSWORD,
    broadcast_retries=2,
    broadcast_timeout=3,
)
for appliance in appliances:
    output(appliance, args.credentials)
```

Get appliance state:

```python
from midea_beautiful_dehumidifier import appliance_state

appliance = appliance_state(APPLIANCE_IP_ADDRESS, token=TOKEN, key=KEY)
print(appliance)
```

## Build the library

Library is automatically built, packaged and published to [PyPI](https://pypi.org/project/midea-beautiful-dehumidifier/) when a Git Hub release is published.

## See also

* https://github.com/nbogojevic/midea-dehumidifier-lan