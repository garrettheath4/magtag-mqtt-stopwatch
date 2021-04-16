# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense


import sys
import time
import adafruit_datetime as datetime

# noinspection PyUnresolvedReferences
import socketpool
# noinspection PyUnresolvedReferences
import wifi

import adafruit_logging
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from adafruit_magtag.magtag import MagTag

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise


MQTT_TOPIC_OUT = secrets["topic_past"]
MQTT_TOPIC_NOW = secrets["topic_now"]
SSID = secrets["ssid"]
HOSTNAME = secrets["broker"]
PORT = secrets["port"]
REFRESH_INT_MINS = 1
LEDS_ON_MINS_THRESHOLD = -1
LEDS_ALWAYS_OFF_BEFORE_HOUR = 24

if "refresh_mins" in secrets:
    REFRESH_INT_MINS = secrets["refresh_mins"]
if "leds_on_mins_threshold" in secrets:
    LEDS_ON_MINS_THRESHOLD = secrets["leds_on_mins_threshold"]
if "leds_always_off_before_hour" in secrets:
    LEDS_ALWAYS_OFF_BEFORE_HOUR = secrets["leds_always_off_before_hour"]

logger = adafruit_logging.getLogger("code.py")
logger.setLevel(adafruit_logging.DEBUG)


def main(magtag):
    magtag.network.connect()
    logger.info("WiFi connected to %s", SSID)

    magtag.add_text(
        text_position=(
            (magtag.graphics.display.width // 2) - 1,
            (magtag.graphics.display.height // 2) - 1,
        ),
        text_scale=11,
        text_anchor_point=(0.5, 0.55),
        is_data=False,
    )

    time_out = None
    time_now = None
    leds_on = False

    # Define callback methods which are called when events occur
    # pylint: disable=unused-argument
    def connected(client, userdata, flags, rc):
        # This function will be called when the client is connected successfully to the broker.
        logger.debug("Connected to MQTT broker at %s:%d", HOSTNAME, PORT)
        logger.debug("Listening for topic changes on %s", MQTT_TOPIC_OUT)
        # Subscribe to all changes on the desired topic.
        client.subscribe(MQTT_TOPIC_OUT)
        logger.debug("Listening for topic changes on %s", MQTT_TOPIC_NOW)
        client.subscribe(MQTT_TOPIC_NOW)

    def disconnected(client, userdata, rc):
        # This method is called when the client is disconnected
        logger.warning("Disconnected from MQTT broker %s:%d", HOSTNAME, PORT)

    def message(client, topic, msg_text):
        # This method is called when a topic the client is subscribed to has a new message.
        logger.debug("New message on topic %s: %s", topic, msg_text)
        nonlocal time_out
        nonlocal time_now
        nonlocal leds_on
        if topic == MQTT_TOPIC_OUT:
            time_out = datetime.datetime.fromisoformat(msg_text)
            logger.debug("Received 'last out' string: %s", time_out)
            time_now = None
        elif topic == MQTT_TOPIC_NOW:
            time_now = datetime.datetime.fromisoformat(msg_text)
            logger.debug("Received now string: %s", time_now)
        if time_out and time_now:
            delta_time = time_now - time_out
            logger.debug("Delta: %s", delta_time)
            total_seconds = delta_time.seconds
            total_minutes = total_seconds / 60
            hours = total_seconds // (60 * 60)
            remaining_seconds = total_seconds - (hours * 60 * 60)
            minutes = remaining_seconds // 60
            delta_str = f"{hours}:{minutes:02}"
            magtag.set_text(delta_str)
            if LEDS_ON_MINS_THRESHOLD >= 0:
                if leds_on and (total_minutes < LEDS_ON_MINS_THRESHOLD or time_now.hour < LEDS_ALWAYS_OFF_BEFORE_HOUR):
                    leds_on = False
                    magtag.peripherals.neopixel_disable = True
                elif not leds_on and total_minutes >= LEDS_ON_MINS_THRESHOLD:
                    leds_on = True
                    magtag.peripherals.neopixel_disable = False
                    magtag.peripherals.neopixels.brightness = 0.01
                    magtag.peripherals.neopixels.fill((0, 0xFF, 0))

    # Create a socket pool
    pool = socketpool.SocketPool(wifi.radio)

    # Set up a MiniMQTT Client
    mqtt_client = MQTT.MQTT(
        broker=HOSTNAME,
        port=PORT,
        is_ssl=False,
        keep_alive=15,
        socket_pool=pool,
    )
    mqtt_client.enable_logger(adafruit_logging, log_level=adafruit_logging.DEBUG)

    # Setup the callback methods above
    mqtt_client.on_connect = connected
    mqtt_client.on_disconnect = disconnected
    mqtt_client.on_message = message

    # Connect the client to the MQTT broker.
    logger.info("Connecting to MQTT broker at %s:%d", HOSTNAME, PORT)
    mqtt_client.connect()

    mqtt_client.ping()

    # Start a blocking message loop...
    # NOTE: NO code below this loop will execute
    # NOTE: Network reconnection is handled within this loop
    while True:
        try:
            mqtt_client.is_connected()
        except MQTT.MMQTTException as mqtt_ex:
            logger.error("MQTT client is NOT connected")
            sys.print_exception(mqtt_ex)
            continue
        logger.debug("MQTT client connected")
        logger.debug("Starting MQTT client loop")
        # noinspection PyBroadException
        try:
            mqtt_client.loop(10)
        except Exception as loop_ex:  # catch *all* exceptions
            logger.error("Failed to get data; retrying")
            logger.error("%s: %s", type(loop_ex).__name__, loop_ex.args)
            sys.print_exception(loop_ex)
            # Don't resubscribe since the on_connect method always subscribes
            try:
                mqtt_client.reconnect(resub_topics=False)
            except Exception as reconnect_ex:
                logger.error("Failed to reconnect; resetting")
                logger.error("%s: %s", type(reconnect_ex).__name__, reconnect_ex.args)
                sys.print_exception(reconnect_ex)
                magtag.peripherals.deinit()
                return
            continue

        if leds_on:
            logger.info("Sleeping for %d minutes...", REFRESH_INT_MINS)
            time.sleep(REFRESH_INT_MINS * 60)
        else:
            logger.info("Sleeping deeply for %d minutes...", REFRESH_INT_MINS)
            magtag.exit_and_deep_sleep(REFRESH_INT_MINS * 60)
        logger.debug("Repeating main loop")


while True:
    try:
        magtag = MagTag(debug=True)
        main(magtag)
    except Exception as main_ex:
        logger.error("Exception from main loop; retrying")
        logger.error("%s: %s", type(main_ex).__name__, main_ex.args)
        sys.print_exception(main_ex)
        magtag.exit_and_deep_sleep(10)
        continue
