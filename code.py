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
REFRESH_INT_MINS_KEY = "refresh_mins"
REFRESH_INT_MINS_VAL = 1
LEDS_ON_MINS_THRESHOLD_KEY = "leds_on_mins_threshold"
LEDS_ON_MINS_THRESHOLD_VAL = -1
SLEEP_DAILY_BEFORE_HOUR_KEY = "sleep_daily_before_hour"
SLEEP_DAILY_BEFORE_HOUR_VAL = 24

logger = adafruit_logging.getLogger("code.py")
logger.setLevel(adafruit_logging.DEBUG)

if REFRESH_INT_MINS_KEY in secrets:
    REFRESH_INT_MINS_VAL = secrets[REFRESH_INT_MINS_KEY]
if LEDS_ON_MINS_THRESHOLD_KEY in secrets:
    LEDS_ON_MINS_THRESHOLD_VAL = secrets[LEDS_ON_MINS_THRESHOLD_KEY]
if SLEEP_DAILY_BEFORE_HOUR_KEY in secrets:
    SLEEP_DAILY_BEFORE_HOUR_VAL = secrets[SLEEP_DAILY_BEFORE_HOUR_KEY]

logger.info(f"{REFRESH_INT_MINS_KEY} = {REFRESH_INT_MINS_VAL}")
logger.info(f"{LEDS_ON_MINS_THRESHOLD_KEY} = {LEDS_ON_MINS_THRESHOLD_VAL}")
logger.info(f"{SLEEP_DAILY_BEFORE_HOUR_KEY} = {SLEEP_DAILY_BEFORE_HOUR_VAL}")


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

    time_outside = None
    time_now = None
    leds_on = False

    # Define callback methods which are called when events occur
    # pylint: disable=unused-argument
    def connected(client, userdata, flags, result_code):
        # This function will be called when the client is connected successfully to the broker.
        logger.debug("Connected to MQTT broker at %s:%d", HOSTNAME, PORT)
        logger.debug("Listening for topic changes on %s", MQTT_TOPIC_OUT)
        # Subscribe to all changes on the desired topic.
        client.subscribe(MQTT_TOPIC_OUT)
        logger.debug("Listening for topic changes on %s", MQTT_TOPIC_NOW)
        client.subscribe(MQTT_TOPIC_NOW)

    def disconnected(client, userdata, result_code):
        # This method is called when the client is disconnected
        logger.warning("Disconnected from MQTT broker %s:%d", HOSTNAME, PORT)

    def message(client, topic, msg_text):
        # This method is called when a topic the client is subscribed to has a new message.
        logger.debug("New message on topic %s: %s", topic, msg_text)
        nonlocal time_outside
        nonlocal time_now
        nonlocal leds_on
        if topic == MQTT_TOPIC_OUT:
            # example msg_text = "2021-04-19T10:28:42.061205-04:00"
            time_outside = datetime.datetime.fromisoformat(msg_text)
            logger.debug("Received 'last out' string: %s", time_outside)
            time_now = None
        elif topic == MQTT_TOPIC_NOW:
            # example msg_text = "2021-04-19T12:29:00.005120-04:00"
            time_now = datetime.datetime.fromisoformat(msg_text)
            logger.debug("Received now string: %s", time_now)
            if SLEEP_DAILY_BEFORE_HOUR_VAL < 24:
                msg_text_head = msg_text[:11]
                msg_text_tail = msg_text[26:]
                off_until_str = f"{msg_text_head}{SLEEP_DAILY_BEFORE_HOUR_VAL:02}:00:00.000000{msg_text_tail}"
                off_until_time = datetime.datetime.fromisoformat(off_until_str)
                until_on = off_until_time - time_now
                if until_on.total_seconds() > 0:
                    magtag.set_text("Zzz")
                    logger.info(f"Deep sleeping for {until_on.total_seconds()} seconds (until {off_until_str})")
                    magtag.exit_and_deep_sleep(until_on.total_seconds())
        if time_outside and time_now:
            delta_time = time_now - time_outside
            logger.debug("Delta: %s", delta_time)
            total_seconds = int(delta_time.total_seconds())
            total_minutes = total_seconds / 60
            hours = int(total_seconds // (60 * 60))
            remaining_seconds = total_seconds - (hours * 60 * 60)
            minutes = remaining_seconds // 60
            delta_str = f"{hours}:{minutes:02}"
            magtag.set_text(delta_str)
            if LEDS_ON_MINS_THRESHOLD_VAL >= 0:
                if leds_on and (total_minutes < LEDS_ON_MINS_THRESHOLD_VAL or time_now.hour < SLEEP_DAILY_BEFORE_HOUR_VAL):
                    leds_on = False
                    magtag.peripherals.neopixel_disable = True
                elif not leds_on and total_minutes >= LEDS_ON_MINS_THRESHOLD_VAL:
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
            sys.print_exception(mqtt_ex)  # pylint: disable=no-member
            continue
        logger.debug("MQTT client connected")
        logger.debug("Starting MQTT client loop")
        # noinspection PyBroadException
        try:
            mqtt_client.loop(10)
        except Exception as loop_ex:  # pylint: disable=broad-except
            # catch *all* exceptions
            logger.error("Failed to get data; retrying")
            logger.error("%s: %s", type(loop_ex).__name__, loop_ex.args)
            sys.print_exception(loop_ex)  # pylint: disable=no-member
            # Don't resubscribe since the on_connect method always subscribes
            try:
                mqtt_client.reconnect(resub_topics=False)
            except Exception as reconnect_ex:  # pylint: disable=broad-except
                logger.error("Failed to reconnect; resetting")
                logger.error("%s: %s", type(reconnect_ex).__name__, reconnect_ex.args)
                sys.print_exception(reconnect_ex)  # pylint: disable=no-member
                magtag.peripherals.deinit()
                return
            continue

        if leds_on:
            logger.info("Sleeping for %d minutes...", REFRESH_INT_MINS_VAL)
            time.sleep(REFRESH_INT_MINS_VAL * 60)
        else:
            logger.info("Sleeping deeply for %d minutes...", REFRESH_INT_MINS_VAL)
            magtag.exit_and_deep_sleep(REFRESH_INT_MINS_VAL * 60)
        logger.debug("Repeating main loop")


while True:
    outer_magtag = False
    try:
        outer_magtag = MagTag(debug=True)
        main(outer_magtag)
    except Exception as main_ex:  # pylint: disable=broad-except
        logger.error("Exception from main loop; retrying")
        logger.error("%s: %s", type(main_ex).__name__, main_ex.args)
        sys.print_exception(main_ex)  # pylint: disable=no-member
        if outer_magtag:
            outer_magtag.exit_and_deep_sleep(10)
        continue
