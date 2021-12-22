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
* current relative humidity (read-only)
* target relative humidity (can be set)
* active mode (can be set)
* fan speed (can be set)
* ion mode status (boolean, can be set)
* tank is full (boolean, read-only)
* appliance name (read-only). Set through Midea mobile application.
* appliance serial number (read-only) 
* appliance IPv4 address (read-only)
* token and key for local network access (read-only)


## Discovery

This library discovers appliances on local network. This is done by broadcasting UDP packets on all local networks interfaces to ports 6445. Appliances will respond to this broadcast with their description packet. Following discovery, communication switchers to TCP over port 6444. This communication is encrypted, and the library needs a token and a key for each appliance. This can be either provided or retrieved from Midea app account. The library can also retrieve the list of registered appliances from Midea app account and obtain additional information for devices (eg. name). 

Library connects to Midea cloud API using credentials from NetHome Plus mobile app. You can use other Midea app mobile applications if you obtain their application key and id. See [midea_beautiful_dehumidifier/midea.py](midea_beautiful_dehumidifier/midea.py) for some examples. Application key and application id must match, otherwise library won't be able to sign in.

The discovery should work on Linux and Windows based systems, however it doesn't work in Windows Subsystem for Linux and may not work in Docker containers or VMs depending on network setup. For example, VM or container needs to have rights to broadcast to physical network to make discovery work. On workaround is to run discovery from non-virtualized environment host. 

### Network considerations

Discovery requires that both appliance and the machine performing discovery are present on the same subnet. Discovery process will issue UDP broadcast request on the local private networks discovered from host's network adapters. The library only scans private network ranges using this method (e.g. 10.0.0.0 – 10.255.255.255, 	172.16.0.0 – 172.31.255.255 and 192.168.0.0 – 192.168.255.255) It is also possible to explicitly provide networks or even single addresses to scan and in this case there is no limitation on address ranges, however, beware of sending broadcast requests to public ip networks.


## Logging

Library logs additional information at log level 5. Credentials information like username, password or token keys should never be logged, but you can use command line tool to display token and key data. 


## Command Line Usage

### Installing package

```shell
pip install --upgrade midea-beautiful-dehumidifier
```

### Command line tool help

```shell
midea_beautiful_dehumidifier-cli --help
midea_beautiful_dehumidifier-cli discover --help
midea_beautiful_dehumidifier-cli set --help
midea_beautiful_dehumidifier-cli status --help
```

### Discovery

Discover dehumidifier appliances on the local network:

```shell
midea_beautiful_dehumidifier-cli discover --account ACCOUNT_EMAIL --password PASSWORD
```

Show tokens used to connect to appliances via local network
```shell
midea_beautiful_dehumidifier-cli discover --account ACCOUNT_EMAIL --password PASSWORD --credentials
```

Search for devices by providing explicit network address

```shell
midea_beautiful_dehumidifier-cli discover --account ACCOUNT_EMAIL --password PASSWORD --network 192.0.1.3 --credentials
```

Search for devices by providing explicit network range

```shell
midea_beautiful_dehumidifier-cli discover --account ACCOUNT_EMAIL --password PASSWORD --network 192.0.1.2/24 --credentials
```

### Appliance status

Get status of an appliance using known TOKEN and KEY (e.g. retrieved using `discover` command)

```shell
midea_beautiful_dehumidifier-cli status --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY
```

Get status of an appliance using Midea app credentials

```shell
midea_beautiful_dehumidifier-cli status --ip APPLIANCE_IP_ADDRESS --account ACCOUNT_EMAIL --password PASSWORD
```

### Set appliance attribute

Set target relative humidity (0-100)

```shell
midea_beautiful_dehumidifier-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --humidity 55
```
Sets operating mode (number 1 to 4)
```shell
midea_beautiful_dehumidifier-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --mode 1
```
Set fan strength (0-100)
```shell
midea_beautiful_dehumidifier-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --fan 40
```
Turn on/off ion mode (0 or 1)
```shell
midea_beautiful_dehumidifier-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --ion 1
```
Turn on/off ion mode (0 or 1)
```shell
midea_beautiful_dehumidifier-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --on 1
```
Combinations multiple settings
```shell
midea_beautiful_dehumidifier-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --fan 60 --humidity 50
```

### Watch appliance status

Watch appliance status allows to debug packets received when polling it. It will repeatedly retrieve appliance status with specified pauses between each poll. Polling can be interrupted via keyboard.

Continuously watch status of an appliance using known TOKEN and KEY (e.g. retrieved using `discover` command) with interval of 10 seconds between polling

```shell
midea_beautiful_dehumidifier-cli watch --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --interval 10
```

Continuously watch status of an appliance using Midea app credentials with interval of 30 seconds between polling

```shell
midea_beautiful_dehumidifier-cli status --ip APPLIANCE_IP_ADDRESS --account ACCOUNT_EMAIL --password PASSWORD --interval 30
```

### Specifying log level

Log level is specified using `--log` option:

`DEBUG` level

```shell
midea_beautiful_dehumidifier-cli --log DEBUG discover --account ACCOUNT_EMAIL --password PASSWORD
```
Very verbose level (may contain confidential information)
```shell
midea_beautiful_dehumidifier-cli --log NOTSET discover --account ACCOUNT_EMAIL --password PASSWORD
```
`WARNING` level (default log level if option was not specified)
```shell
midea_beautiful_dehumidifier-cli --log DEBUG discover --account ACCOUNT_EMAIL --password PASSWORD
```

## Code examples

Discover appliances on local network:

```python
from midea_beautiful_dehumidifier import find_appliances

appliances = find_appliances(
    account=USER_EMAIL,
    password=PASSWORD,
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

* https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan