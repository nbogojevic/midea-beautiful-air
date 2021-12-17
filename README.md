This is a library that allows communication with Midea dehumidifier appliances via the local area network.

# midea_beautiful_dehumidifier
[![Build Status](https://github.com/nbogojevic/midea-beautiful-dehumidifier/actions/workflows/python-publish.yml/badge.svg)](https://github.com/nbogojevic/midea-beautiful-dehumidifier/actions/workflows/python-publish.yml)
[![PyPI](https://img.shields.io/pypi/v/midea_beautiful_dehumidifier.svg?maxAge=3600)](https://pypi.org/project/midea_beautiful_dehumidifier/)

This library allows discovering Midea dehumidifiers on local networkg, getting and updating their state.

This libary inspired from the repository at [mac-zhou/midea-msmart](https://github.com/mac-zhou/midea-msmart) which provides similar functionality for air conditioners.


Thanks for [yitsushi's project](https://github.com/yitsushi/midea-air-condition), [NeoAcheron's project](https://github.com/NeoAcheron/midea-ac-py), [andersonshatch's project](https://github.com/andersonshatch/midea-ac-py).


## Supported appliances

The library works only Midea dehumidifiers supporting V3 protocol. Both appliances with and without ion function are supported.

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
* appliance IP address (read-only)
* token and key for local network access (read-only)


## Discovery

Library can discover appliances on local network. This is done by broadcasting UDP packets on all local networks interfaces to ports 6445. Appliances will respond to this broadcast with description information. It also retrieves known appliances from Midea cloud account and then matches this information with information retrieved via local network.

## Usage

Discover appliances on the local network:

```shell
pip install midea-beautiful-dehumidifier
python -m midea_beautiful_dehumidifier.cli discover --account ACCOUNT_EMAIL --password PASSWORD
# Show tokens used to connect to appliances via local network
python -m midea_beautiful_dehumidifier.cli discover --account ACCOUNT_EMAIL --password PASSWORD --credentials
```

Get status of an appliance:

```shell
pip install midea-beautiful-dehumidifier
python -m midea_beautiful_dehumidifier.cli status --ip APPLIANCE_IP --token TOKEN --key KEY
```


Set appliance attribute (target humidity, mode, ion switch, fan speed):

```shell
pip install midea-beautiful-dehumidifier
python -m midea_beautiful_dehumidifier.cli set --ip APPLIANCE_IP --token TOKEN --key KEY --mode MODE
```