# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense


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


MQTT_TOPIC_OUT = "dogs/last_time_out"
MQTT_TOPIC_NOW = "time/now"
SSID = secrets["ssid"]
HOSTNAME = secrets["broker"]
PORT = secrets["port"]

logger = adafruit_logging.getLogger("code.py")
logger.setLevel(adafruit_logging.DEBUG)


def main():
    magtag = MagTag(
        debug=True,
    )

    try:
        magtag.peripherals.neopixel_disable = True
    except Exception as neopixel_ex:
        logger.error("Failed to disable NeoPixels during init; skipping")
        logger.error("%s: %s", type(neopixel_ex).__name__, neopixel_ex.args)

    logger.info("WiFi connecting to %s", SSID)
    magtag.network.connect()
    logger.info("WiFi connected to %s", SSID)

    magtag.add_text(
        text_position=(
            (magtag.graphics.display.width // 2) - 1,
            (magtag.graphics.display.height // 2) - 1,
        ),
        text_scale=3,
        text_anchor_point=(0.5, 0.5),
        is_data=False,
    )

    time_out = None
    time_now = None
    screen_light_on = False

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
        nonlocal screen_light_on
        if topic == MQTT_TOPIC_OUT:
            time_out = datetime.datetime.fromisoformat(msg_text)
            logger.debug("Received out string: %s", time_out)
        elif topic == MQTT_TOPIC_NOW:
            time_now = datetime.datetime.fromisoformat(msg_text)
            logger.debug("Received now string: %s", time_now)
        if time_out and time_now:
            delta_time = time_now - time_out
            logger.debug("Delta: %s", delta_time)
            total_seconds = delta_time.seconds
            hours = total_seconds // (60 * 60)
            total_seconds = total_seconds - (hours * 60 * 60)
            minutes = total_seconds // 60
            delta_str = f"{hours} hr {minutes} min"
            magtag.set_text(delta_str)
            if not screen_light_on and hours > 2:
                screen_light_on = True
                magtag.peripherals.neopixel_disable = False
                magtag.peripherals.neopixels.brightness = 0.01
                magtag.peripherals.neopixels.fill((0xFF, 0xFF, 0xFF))

    # Create a socket pool
    pool = socketpool.SocketPool(wifi.radio)

    # Set up a MiniMQTT Client
    mqtt_client = MQTT.MQTT(
        broker=HOSTNAME,
        port=PORT,
        is_ssl=False,
        keep_alive=75,
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
        except MQTT.MMQTTException:
            logger.error("MQTT client is NOT connected")
            continue
        logger.debug(f"MQTT client connected")
        logger.debug("Starting MQTT client loop")
        # noinspection PyBroadException
        try:
            mqtt_client.loop(10)
        except Exception as loop_ex:  # catch *all* exceptions
            logger.error("Failed to get data; retrying")
            logger.error("%s: %s", type(loop_ex).__name__, loop_ex.args)
            # Don't resubscribe since the on_connect method always subscribes
            try:
                mqtt_client.reconnect(resub_topics=False)
            except Exception as reconnect_ex:
                logger.error("Failed to reconnect; resetting")
                logger.error("%s: %s", type(reconnect_ex).__name__, reconnect_ex.args)
                magtag.peripherals.deinit()
                return
            continue

        logger.info("Sleeping for 60 seconds...")
        time.sleep(60)
        logger.debug("Repeating main loop")


while True:
    try:
        main()
    except Exception as main_ex:
        logger.error("Exception from main loop; retrying")
        logger.error("%s: %s", type(main_ex).__name__, main_ex.args)
        time.sleep(10)
        continue
