**InsteonLocal**

Python library for controlling Insteon Hub locally. This allows you to send direct commands to your Insteon Hub without having to go through the cloud, or obtain a developer API key 
(which can be hard or impossible to get from Insteon)

*If anyone would like to take over this project, please let me know via github issue. I'm mostly using ZWave/Hue and Homeseer now so I have limited hardware and time to test/work on this.*

## Troubleshooting/Reporting

1. Download the insteon local package from https://github.com/phareous/insteonlocal
2. Copy config.py.example to config.py and update the host/user/pass to your own hub's information
3. Edit example.py to call the commands you want to test such as:
hub.get_linked()
sys.exit(1)
4. Open an issue at https://github.com/phareous/insteonlocal
Include the log file, the list of device models and ID's, and your hub model

## Changes

0.54 2022-06-20 Changes to package and requirements to remove built-in package names that could be overwritten by hostile actor

0.53 2017-06-08 Fix typo in error logging

0.52 2017-06-01 Set path for cache files in constructor

0.51 2017-04-08 Use system temp dir

0.50 2017-04-06 Fix cache error parsing [@wardcraigj]

0.49 2017-03-16 Adds support for i2c2 checksums on extended msg, adds 
support for controlling on/off outlets (2663-222) [@phareous]

0.48 2017-03-09 Fixes with caching and device ids [@phareous]

0.47 2017-03-01 Caching and logging changes [@wardcraigj]

0.46 2017-02-28 More file caching changes [@wardcraigj]

0.45 2017-02-28 Switching caching to be file-based [@wardcraigj]

0.44 Bug fix for caching [@wardcraigj]

0.43 Better caching [@wardcraigj]

0.41 Add support for FanLinc, better status support [@jawilson]

0.40 Added caching to get device status [@wardcraigj]

0.39 Initial stable release for use in Home Assistant

## Hubs

This was developed and tested against the Insteon Hub 2245-222.

It may work for the Insteon Hub 2242-222, SmartLinc 2414N, or other hub with a HTTP local API. However, it has not been tested with these hubs.

## Devices

This version of the library should work with Insteon dimmers and switches, and FanLinc controls. It was developed against 
2466SW ToggleLinc Relay (Switch) and 2477D SwitchLinc Dual-Band Dimmer

## Unsupported Devices

At this time, these devices are supported:

-Switches
-Dimmers
-Receptacles
-FanLinc

To add support for future devices, we will need donations of equipment, or for device owners to directly 
contribute code.

Unsupported devices include (but aren't limited to):

* Keypads
* Thermostats
* Garage Door Interface
* Leak Detector
* Pool Devices
* Open/Close Sensor
* Door Sensor
* Motion Sensor
* Sprinkler Interfaces
* Smoke Bridge
* I/O Module
* Micro Dimmer
* On/Off Micro
* Open/Close Micro
* Ballast Dimmer
* In-line Dimmer
* Mini Remote

## Functionality

The library can currently do the following actions:

* Switches: 
  * On
  * Off
  * Beep

* Dimmers:
  * On (specified level)
  * On (fast: saved level)
  * Off
  * Off instant
  * Change level
  * Brighten one step
  * Dim one step
  * Start changing (up or down)
  * Stop changing (up or down)
  * Beep 

* Groups:
  * On
  * Off
  
For all devices, you can get the status of a device with getStatus which will query the device and return the result

You can request a list of all linked devices. For each device, it will also return the type of device 
and the model. This is accomplished by using two files from this library, device_categories.json and device_models.json

## Missing Functionality

It is suggested to use the mobile Insteon App for features that are missing from the library:

* You cannot link or unlink devices to your hub

* You cannot modify, create, or remove scenes/groups.

* You cannot change settings (operating flags) on a device (ramp rate, led brightness, beep, etc.)

* The library does not recognize double-tap, etc.

* The library cannot respond to broadcasts from devices that change state (aka instant notification when you turn on a switch).
This could probably be accomplished by the calling application polling the getBufferStatus but it may require library changes to respond to the
proper insteon command type.

## Using the Library

Because scene, room, and device names are stored in the cloud, they are not available to this library. You can use 
the getLinked() command to get a list of device ids, and their models/categories, and then store 
these locally in your application with the desired friendly names, etc.

The first thing to do is to instiniate a hub object:

```python
hub = Hub(ip, user, pass, port, log filename/path, enable console log (Tru eor False))
```

Example:
```python
hub = Hub('192.168.1.16', 'myuser', 'mypass', '25105', '/tmp/insteonlocal.log', True)
```

The port is normally 25105. The user/pass is on a sticker on the bottom of the hub (but can be changed via the mobile app). The
 IP address is available via the mobile app

After establishing a connection to the hub, you can create a Switch or Dimmer object (by giving the Insteon ID). See the example.py for examples.

Establish dimmer and turn on to 25%:

```python
dimmer1 = hub.dimmer('41902d')
dimmer1.on(25)
```

Turn on switch:

```python
switch1 = hub.switch('40465a')
switch1.on()
switch1.off()
```

Turn on group:

```python
group3 = hub.group("3")
group3.on()
```
