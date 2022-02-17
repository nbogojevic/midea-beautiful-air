This is a library that allows communication with Midea air conditioner and dehumidifier via the local area network.

# midea-beautiful-air
[![Build Status](https://github.com/nbogojevic/midea-beautiful-air/actions/workflows/python-publish.yml/badge.svg)](https://github.com/nbogojevic/midea-beautiful-air/actions/workflows/python-publish.yml)
[![PyPI](https://img.shields.io/pypi/v/midea_beautiful_air.svg?maxAge=3600)](https://pypi.org/project/midea_beautiful_air/)

This library allows discovering Midea air conditioners and dehumidifiers on local network, getting their state and controlling then. The name comes from Chinese name for Midea (美的) which translates to _beautiful_ in English. 

This library inspired from the repository at [mac-zhou/midea-msmart](https://github.com/mac-zhou/midea-msmart) which provides similar functionality for air conditioners and [barban-dev/midea_inventor_dehumidifier](https://github.com/barban-dev/midea_inventor_dehumidifier) cloud based functionality for dehumidifiers. This library may include verbatim or adapted portions of the code from those two projects.


Thanks also to [yitsushi's project](https://github.com/yitsushi/midea-air-condition), [NeoAcheron's project](https://github.com/NeoAcheron/midea-ac-py), [andersonshatch's project](https://github.com/andersonshatch/midea-ac-py).


## Supported appliances

The library works with Midea air conditioners and dehumidifiers supporting V2 and V3 protocol. 

Some examples of supported dehumidifiers:

* Comfee MDDF-16DEN7-WF or MDDF-20DEN7-WF (tested with 20L version)
* Inventor EVA ΙΟΝ Pro Wi-Fi (EP3-WiFi 16L/20L) (tested with 20L version)
* Inventor Eva II Pro Wi-Fi (EVP-WF16L/20L)
* Pro Breeze 30L Smart Dehumidifier with Wifi / App Control
* Midea SmartDry dehumidifiers (22, 35, 50 pint models )
* Midea Cube dehumidifiers (20, 35, 50 pint models)

It may as well work with other Midea Wi-Fi air conditioners and dehumidifiers.

## Dehumidifier data

The following dehumidifier data is accessible through this library: 

* on/off switch (boolean, can be set)
* current relative humidity (read-only)
* target relative humidity (can be set)
* active mode (can be set)
* fan speed (can be set)
* (an)ion mode status (boolean, can be set)
* tank is full (boolean, read-only)
* appliance name (read-only). Set through Midea mobile application.
* appliance serial number (read-only) 
* appliance IPv4 address (read-only)
* token and key for local network access (read-only, only v3 appliances)
* filter replacement indicator (boolean, read-only, if supported on appliance)
* pump on/off switch (boolean, can be set, if supported on appliance)
* sleep mode on/off switch (boolean,  can be set, if supported on appliance)
* defrosting mode indicator (boolean, read-only, if supported on appliance)
* internal error code (read-only)
* appliance characteristics, i.e. support for special modes, fan presets etc (read-only)
* beep prompt (write-only)
* tank water level (read-only, if supported by appliance)
* current ambient temperature (read-only)

## Air Conditioner Data

The following air conditioner data is accessible through this library: 

* on/off switch (boolean, can be set)
* target temperature(celsius, can be set)
* indoor temperature (celsius, read-only)
* outdoor temperature (celsius, read-only)
* active mode (can be set)
* air purifier mode (boolean, can be set)
* air drying mode (boolean, can be set)
* horizontal swing operation (boolean, can be set)
* vertical swing operation (boolean, can be set)
* fahrenheit degree display (boolean, can be set)
* internal error code (read-only)
* appliance characteristics, i.e. support for special modes, fan presets etc (read-only)
* beep prompt (write-only)
* appliance name (read-only). Set through Midea mobile application.
* appliance serial number (read-only) 
* appliance IPv4 address (read-only)
* token and key for local network access (read-only, only v3 appliances)

## Discovery

This library is able to discover appliances on local network. This is done by broadcasting UDP packets to port 6445. Appliances will respond to this broadcast with their description packet. Following discovery, communication switchers to TCP over port 6444. This communication is encrypted, and, for appliances with version 3 firmware the library needs a token/key (K1) combination associated to each appliance. This can be either provided as arguments or retrieved from Midea app account. Once obtained, the token/key (K1) pair can be reused for an appliance multiple times. The library can also retrieve the list of registered appliances from Midea app account and obtain additional information for devices (eg. name). 

Library connects to Midea cloud API using credentials from NetHome Plus mobile app. You can use other Midea app mobile applications if you obtain their application key and id. See [midea_beautiful/midea.py](midea_beautiful/midea.py) for some examples. Application key and application id must match, otherwise library won't be able to sign in.

The discovery should work on Linux and Windows based systems, however it doesn't work in Windows Subsystem for Linux and may not work in Docker containers or VMs depending on network setup. For example, a VM or a container needs to have rights to broadcast to physical network to make discovery work. One workaround, if physical network access is not possible, is to run discovery from non-virtualized environment host. 

If this discovery mechanism doesn't work on particular set-up, it is still possible to either target appliances directly using their IP address when it is known or to retrieve or set their status using cloud service. 

### Network considerations

Discovery requires that both appliance and the machine performing discovery are present on the same broadcast subnet. By default library issues broadcast to all network, i.e. address `255.255.255.255`, but it is possible to restrict broadcast subnet (e.g. 192.0.2.255)

## Local protocol support

Library supports following protocols:

* cloud based status reading and writing (no local access needed)
* v3 local protocol with compatible devices (requires TOKEN/KEY combination)
* v2 local protocol with compatible devices

## Logging

Credentials information like username, password or token keys are redacted by default. When using command line, pass `--no-redact` option to show them in the logs. You can use command line tool to display token and key (K1) data. 


## Command Line Usage

### Installing package

```shell
pip install --upgrade midea-beautiful-air
```

### Command line tool help

```shell
midea-beautiful-air-cli --help
midea-beautiful-air-cli discover --help
midea-beautiful-air-cli set --help
midea-beautiful-air-cli status --help
```

### Discovery

Discover appliances on the local network:

```shell
midea-beautiful-air-cli discover --account ACCOUNT_EMAIL --password PASSWORD
```

Show tokens used to connect to appliances via local network
```shell
midea-beautiful-air-cli discover --account ACCOUNT_EMAIL --password PASSWORD --credentials
```

Search for devices by providing explicit network address

```shell
midea-beautiful-air-cli discover --account ACCOUNT_EMAIL --password PASSWORD --address 192.0.2.3 --credentials
```

Search for devices by providing broadcast address

```shell
midea-beautiful-air-cli discover --account ACCOUNT_EMAIL --password PASSWORD --address 192.0.2.255 --credentials
```

Disovery when appliances are registered to new API:

```shell
midea-beautiful-air-cli --verbose ---log DEBUG discover --account ACCOUNT --password PASSWORD --credentials --appkey APPKEY --appid APPID --hmackey HMACKEY --iotkey IOTKEY --apiurl https://mp-prod.appsmb.com/mas/v5/app/proxy?alias= --proxied
```

### Appliance status

Get status of an appliance using known TOKEN and KEY (e.g. retrieved using `discover` command)

```shell
midea-beautiful-air-cli status --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY
```

Get status of an appliance using Midea app credentials

```shell
midea-beautiful-air-cli status --ip APPLIANCE_IP_ADDRESS --account ACCOUNT_EMAIL --password PASSWORD
```

Get status of an appliance through Midea cloud API (note the usage of `--id` and `--cloud` options)

```shell
midea-beautiful-air-cli status --id APPLIANCE_ID --account ACCOUNT_EMAIL --password PASSWORD --cloud
```

### Set appliance attribute

Following are some examples of usage:

Set target relative humidity (0-100)

```shell
midea-beautiful-air-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --target-humidity 55
```
Sets operating mode (number 1 to 4)
```shell
midea-beautiful-air-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --mode 1
```
Turn on/off ion mode (0 or 1)
```shell
midea-beautiful-air-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --ion-mode 1
```
Turn appliance on/off mode (0 or 1)
```shell
midea-beautiful-air-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --running 1
```
Turn on/off pump (0 or 1)
```shell
midea-beautiful-air-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --pump 1
```
Combinations of multiple settings
```shell
midea-beautiful-air-cli set --ip APPLIANCE_IP_ADDRESS --token TOKEN --key KEY --fan-speed 60 --target-humidity 50
```
Set target humidity through Midea cloud API (note the usage of `--id` and `--cloud` options)
```shell
midea-beautiful-air-cli set --id APPLIANCE_ID --account ACCOUNT_EMAIL --password PASSWORD --target-humidity 55 --cloud
```
Get list of all settable attributes:
```shell
midea-beautiful-air-cli set --help
```


### Specifying log level

Log level is specified using `--log` option.

Set `DEBUG` level

```shell
midea-beautiful-air-cli --log DEBUG discover --account ACCOUNT_EMAIL --password PASSWORD
```
Very verbose level (may contain confidential information)
```shell
midea-beautiful-air-cli --log NOTSET discover --account ACCOUNT_EMAIL --password PASSWORD
```
Set `WARNING` level (default log level if option was not specified)
```shell
midea-beautiful-air-cli --log WARNING discover --account ACCOUNT_EMAIL --password PASSWORD
```

Additional logging is enabled by passing `--verbose` option. Redacting of sensitive information can be disabled by passing `--no-redact` option.

## Code examples

Discover appliances on local network:

```python
from midea_beautiful import find_appliances

appliances = find_appliances(
    account="USER_EMAIL@example.com",  # Account e-mail
    password="secret_password",  # Account password
)
for appliance in appliances:
    print(f"{appliance!r}")
```

Get appliance state:

```python
from midea_beautiful import appliance_state

appliance = appliance_state(
    address=192.0.2.2,  # APPLIANCE_IP_ADDRESS 
    token="TOKEN",  # TOKEN obtained from Midea API
    key="KEY",  # Token KEY obtained from Midea API
)
print(f"{appliance!r}")
```


Get appliance state from cloud:

```python
from midea_beautiful import appliance_state

appliance = appliance_state( 
    account="USER_EMAIL@example.com",  # Account e-mail
    password="secret_password",  # Account password
    id=123412341234,  # Appliance id obtained from Midea API 
)
print(f"{appliance!r}")
```

## Build the library

Library is automatically built, packaged and published to [PyPI](https://pypi.org/project/midea-beautiful-air/) when a Git Hub release is published.

## Known issues

* Some of values are not available on all appliances. Some appliances may acknowledge action which has no effect (e.g. ion mode)
* Temperature sensor is often under-reporting real ambient temperature. This may be due to sensor proximity to cooling pipes of the humidifier, algorithm or electronics error. The under-reporting depends on the active mode, and stronger modes may result in larger offset from real temperature.


## See also

* https://github.com/nbogojevic/homeassistant-midea-dehumidifier-lan


## Notice

Midea, Inventor, Comfee', Pro Breeze, and other names are trademarks of their respective owners.
