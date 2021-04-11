# MagTag MQTT Time Ago

Display how much time has elapsed between a timestamp fetched from an MQTT broker and the current time. The current time
is also fetched from an MQTT broker so that a real-time clock is not needed on the MagTag e-ink display device.


## Quickstart

1. Clone this repository and its Git submodules:

        git clone https://github.com/garrettheath4/magtag-mqtt-timeago.git
        cd magtag-mqtt-timeago/
        git submodule init && git submodule update

1. Plug in MagTag to your computer with a USB-C cable and turn the physical switch on it to the _On_ position. A
   flash-drive-like file storage device called _CIRCUITPY_ should automatically mount.
1. Run `make` to copy the code and required libraries from this repository to the _CIRCUITPY_ drive.
1. Create a `secrets.py` file inside the _CIRCUITPY_ drive with the following contents:

        # This file is where you keep secret settings, passwords, and tokens!
        # If you put them in the code you risk committing that info or sharing it

        secrets = {
            'ssid': 'myWifiNetworkName',
            'password': 'myWifiPassword',
            'timezone': "America/New_York",  # http://worldtimeapi.org/timezones
            'broker': '192.168.0.50',  # IP or hostname of MQTT server
            'port': 1883,  # MQTT port, default: 1833
            'topic_past': 'dogs/last_time_out',
            'topic_now': 'time/now',
            'refresh_mins': 1,  # minutes between each screen refresh; optional
        }

1. Wait for the MagTag to restart and the code will run automatically.


## Requirements

* [Adafruit MagTag 2.9" E-Ink WiFi Display](https://www.adafruit.com/product/4800)
* MQTT broker server such as [Eclipse Mosquitto](https://mosquitto.org/)
  * Example: running on a Raspberry Pi or in a [Docker container](https://github.com/cmccambridge/mosquitto-unraid/)
    running on an [unRAID](https://unraid.net/) server on your network


## Home Assistant (Optional)

You can run Home Assistant on a Raspberry Pi or in a [Docker container](https://github.com/home-assistant/docker)
running on an unRAID server on your network. A [Home Assistant](https://www.home-assistant.io/) server is optional but
recommended since it provides:

1. an easy way to automatically publish the current time to a "now" topic on an MQTT broker
1. an easy way to configure a smart button to "reset" the timer by publishing the current time to a "past" topic on an
   MQTT broker


### MQTT Current Time Automation

Add this Automation to your Home Assistant to publish the current time to the `time/now` MQTT topic every minute:

```yaml
alias: MQTT Current Time
description: Publish the current time to MQTT every minute
trigger:
  - platform: time_pattern
    minutes: '*'
condition: []
action:
  - service: mqtt.publish
    data:
      topic: time/now
      retain: true
      qos: '1'
      payload_template: '{{ now().isoformat() }}'
mode: single
```

Be sure to configure the [MQTT integration](https://www.home-assistant.io/integrations/mqtt) on your Home Assistant
server first.


### Reset Timer with Smart Button Automation

Add this Automation to your Home Assistant to publish the current time to the `dogs/last_time_out` MQTT topic every time
you press a smart button:

```yaml
alias: Reset Dog Timer
description: ''
trigger:
  - device_id: b46f5fe1a48dae52a61ba4c47a06789f
    domain: zha
    platform: device
    type: remote_button_short_press
    subtype: turn_off
condition: []
action:
  - service: mqtt.publish
    data:
      topic: dogs/last_time_out
      retain: true
      qos: '1'
      payload_template: '{{ now().isoformat() }}'
mode: single
```

You can use any Zigbee button that is compatible with [ZHA](https://www.home-assistant.io/integrations/zha/) for Home
Assistant for this. It has been tested using an Ikea Trådfri on/off switch.



<!-- vim: set textwidth=120 columns=125 smarttab shiftround expandtab nosmartindent: -->
