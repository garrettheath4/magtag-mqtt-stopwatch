# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense


import sys
import time
import adafruit_datetime

# noinspection PyUnresolvedReferences
import socketpool
# noinspection PyUnresolvedReferences
import wifi

import adafruit_logging
import adafruit_minimqtt.adafruit_minimqtt as mqtt
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


# Optional configuration keys and defaults
REFRESH_INT_MINS_KEY = "refresh_mins"
REFRESH_INT_MINS_DEFAULT = 1
LEDS_ON_MINS_THRESHOLD_KEY = "leds_on_mins_threshold"
LEDS_ON_MINS_THRESHOLD_DEFAULT = -1
SLEEP_DAILY_BEFORE_HOUR_KEY = "sleep_daily_before_hour"
SLEEP_DAILY_BEFORE_HOUR_DEFAULT = 24
BACKLIGHT_BRIGHTNESS_KEY = "backlight_brightness"
BACKLIGHT_BRIGHTNESS_DEFAULT = 0.0
TIMEZONE_OFFSET_KEY = "timezone_offset"
TIMEZONE_OFFSET_DEFAULT = -4  # America/New_York

# Required configurations
MQTT_TOPIC_OUT = secrets["topic_past"]
MQTT_TOPIC_NOW = secrets["topic_now"]
SSID = secrets["ssid"]
HOSTNAME = secrets["broker"]
PORT = secrets["port"]

# Optional configurations
refresh_int_mins_val = REFRESH_INT_MINS_DEFAULT
leds_on_mins_threshold_val = LEDS_ON_MINS_THRESHOLD_DEFAULT
sleep_daily_before_hour_val = SLEEP_DAILY_BEFORE_HOUR_DEFAULT
backlight_brightness_val = BACKLIGHT_BRIGHTNESS_DEFAULT
timezone_offset_val = TIMEZONE_OFFSET_DEFAULT

logger = adafruit_logging.getLogger("code.py")
logger.setLevel(adafruit_logging.DEBUG)


def get_optional_config(key, default):
    if key in secrets:
        logger.info("%s = %s", key, secrets[key])
        return secrets[key]
    logger.info("%s = %s  [default value]", key, default)
    return default


refresh_int_mins_val = get_optional_config(REFRESH_INT_MINS_KEY, refresh_int_mins_val)
leds_on_mins_threshold_val = get_optional_config(LEDS_ON_MINS_THRESHOLD_KEY, leds_on_mins_threshold_val)
sleep_daily_before_hour_val = get_optional_config(SLEEP_DAILY_BEFORE_HOUR_KEY, sleep_daily_before_hour_val)
backlight_brightness_val = get_optional_config(BACKLIGHT_BRIGHTNESS_KEY, backlight_brightness_val)
timezone_offset_val = get_optional_config(TIMEZONE_OFFSET_KEY, timezone_offset_val)

timezone_name = "UTC"
if timezone_offset_val >= 0:
    timezone_name += "+"
timezone_name += str(timezone_offset_val)
timezone_obj = adafruit_datetime.timezone(adafruit_datetime.timedelta(hours=timezone_offset_val),
                                          name=timezone_name)


class LEDS:
    OFF = 0
    ALERT = 1
    BACKLIGHT = 2

    STATUS_STR = {
        OFF: 'OFF',
        ALERT: 'ALERT',
        BACKLIGHT: 'BACKLIGHT',
    }

    def __init__(self, peripherals):
        self.status = LEDS.OFF
        self._peripherals = peripherals

    def check(self, time_now, total_minutes):
        if LEDS.should_leds_alert(time_now, total_minutes):
            if self.status != LEDS.ALERT:
                logger.debug("Setting LEDs to ALERT (green)")
                self.status = LEDS.ALERT
                self._peripherals.neopixel_disable = False
                self._peripherals.neopixels.brightness = 1.0
                self._peripherals.neopixels.fill((0, 0xFF, 0))
        elif LEDS.should_leds_backlight():
            if self.status != LEDS.BACKLIGHT:
                logger.debug("Setting LEDs to BACKLIGHT")
                self.status = LEDS.BACKLIGHT
                self._peripherals.neopixel_disable = False
                self._peripherals.neopixels.brightness = backlight_brightness_val
                self._peripherals.neopixels.fill((0xFF, 0xFF, 0xFF))
        else:  # the LEDs should be OFF
            if self.status != LEDS.OFF:
                logger.debug("Setting LEDs to OFF (from %s)", LEDS.STATUS_STR[self.status])
                self.status = LEDS.OFF
                self._peripherals.neopixel_disable = True

    @classmethod
    def should_leds_alert(cls, time_now, total_minutes):
        return total_minutes >= leds_on_mins_threshold_val >= 0 and time_now.hour >= sleep_daily_before_hour_val

    @classmethod
    def should_leds_backlight(cls):
        return backlight_brightness_val > 0.0

    @classmethod
    def leds_should_be_off(cls, time_now, total_minutes):
        return not cls.should_leds_alert(time_now, total_minutes) and not cls.should_leds_backlight()


class MagTagStopwatch:
    def __init__(self, logging_level=adafruit_logging.DEBUG):
        self._logger = adafruit_logging.getLogger("MagTagStopwatch")
        self._logger.setLevel(logging_level)

        self._magtag = MagTag(debug=(logging_level == adafruit_logging.DEBUG))
        self._magtag.network.connect()
        self._logger.info("WiFi connected to %s", SSID)
        self._leds = LEDS(self._magtag.peripherals)

        self._magtag.get_local_time()

        time_now = adafruit_datetime.datetime.now()
        time_now._tzinfo = timezone_obj
        self._past_time_objs = [time_now, None]
        self._current_displayed_text = "0:00"

        # Create big text box
        self._magtag.add_text(
            text_position=(
                (self._magtag.graphics.display.width // 2),
                (self._magtag.graphics.display.height // 2),
            ),
            text_scale=11,
            text_anchor_point=(0.5, 0.55),
            is_data=False,
        )

        # Create duo text box #1
        self._magtag.add_text(
            text_position=(
                (self._magtag.graphics.display.width // 2) + 1,
                (self._magtag.graphics.display.height // 4) + 1,
            ),
            text_scale=8,
            text_anchor_point=(0.5, 0.55),
            is_data=False,
        )

        # Create duo text box #2
        self._magtag.add_text(
            text_position=(
                (self._magtag.graphics.display.width // 2) - 1,
                (self._magtag.graphics.display.height // 4 * 3) - 1,
            ),
            text_scale=4,
            text_anchor_point=(0.5, 0.55),
            is_data=False,
        )

    def set_past_time(self, past_time, time_idx=0, auto_refresh_display=True):
        self._past_time_objs[time_idx] = past_time
        if auto_refresh_display:
            self.refresh_display()

    def get_past_time(self, time_idx=0):
        return self._past_time_objs[time_idx]

    def _should_show_2_times(self) -> bool:
        return self._past_time_objs[1]

    @staticmethod
    def timedelta_to_hours_minutes(delta_time: adafruit_datetime.timedelta):
        total_seconds = int(delta_time.total_seconds())
        hours = int(total_seconds // (60 * 60))
        remaining_seconds = total_seconds - (hours * 60 * 60)
        minutes = remaining_seconds // 60
        return hours, minutes

    def refresh_display(self):
        time_now = adafruit_datetime.datetime.now()
        time_now._tzinfo = timezone_obj
        self._logger.debug("Time now:  %s", str(time_now))
        delta_strs = []

        # Primary time
        self._logger.debug("Past time 1: %s", str(self.get_past_time(0)))
        delta_time_1 = time_now - self.get_past_time(0)
        self._logger.debug("Delta time 1: %s", delta_time_1)
        (hours_1, minutes_1) = self.timedelta_to_hours_minutes(delta_time_1)
        delta_strs.append(f"{hours_1}:{minutes_1:02}")
        self._leds.check(time_now, hours_1 * 60 + minutes_1)

        # Secondary time
        if self._should_show_2_times():
            self._logger.debug("Past time 2: %s", str(self.get_past_time(1)))
            delta_time_2 = time_now - self.get_past_time(1)
            self._logger.debug("Delta time 2: %s", delta_time_2)
            (hours_2, minutes_2) = self.timedelta_to_hours_minutes(delta_time_2)
            delta_strs.append(f"{hours_2}:{minutes_2:02}")

        delta_strs_joined = " ".join(delta_strs)
        if delta_strs_joined != self._current_displayed_text:
            self._current_displayed_text = delta_strs_joined
            if self._should_show_2_times():
                self._magtag.set_text("", 0, auto_refresh=False)
                self._magtag.set_text(delta_strs[0], 1, auto_refresh=False)
                self._magtag.set_text(delta_strs[1], 2, auto_refresh=True)
            else:
                self._magtag.set_text(delta_strs[0], 0, auto_refresh=False)
                self._magtag.set_text("", 1, auto_refresh=False)
                self._magtag.set_text("", 2, auto_refresh=True)

    def leds_are_off(self) -> bool:
        return self._leds.status == LEDS.OFF

    def deinit_peripherals(self):
        self._magtag.peripherals.deinit()

    def reset_system(self):
        self._magtag.exit_and_deep_sleep(10)


while True:
    mtStopwatch = MagTagStopwatch(logging_level=adafruit_logging.DEBUG)
    try:
        # Define callback methods which are called when events occur
        # pylint: disable=unused-argument
        def connected(client, userdata, flags, result_code):
            # This function will be called when the client is connected successfully to the broker.
            logger.debug("Connected to MQTT broker at %s:%d", HOSTNAME, PORT)
            logger.debug("Listening for topic changes on %s", MQTT_TOPIC_OUT)
            # Subscribe to all changes on the desired topic.
            client.subscribe(MQTT_TOPIC_OUT)

        def disconnected(client, userdata, result_code):
            # This method is called when the client is disconnected
            logger.warning("Disconnected from MQTT broker %s:%d", HOSTNAME, PORT)

        def message(client, topic, msg_text):
            # This method is called when a topic the client is subscribed to has a new message.
            logger.debug("New message on topic %s: %s", topic, msg_text)
            if topic == MQTT_TOPIC_OUT:
                # example msg_text = "2021-04-19T10:28:42.061205-04:00"
                time_outside = adafruit_datetime.datetime.fromisoformat(msg_text)
                logger.debug("Received 'last out' string: %s", time_outside)
                mtStopwatch.set_past_time(time_outside)
            else:
                logger.warning("Received unexpected topic '%s': %s", topic, msg_text)

        # Create a socket pool
        pool = socketpool.SocketPool(wifi.radio)

        # Set up a MiniMQTT Client
        mqtt_client = mqtt.MQTT(
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
            except mqtt.MMQTTException as mqtt_ex:
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
                    mtStopwatch.deinit_peripherals()
                continue

            logger.info("Sleeping lightly for %d minutes...", refresh_int_mins_val)
            time.sleep(refresh_int_mins_val * 60)
            logger.debug("Repeating main loop")

    except Exception as main_ex:  # pylint: disable=broad-except
        logger.error("Exception from main loop; retrying")
        logger.error("%s: %s", type(main_ex).__name__, main_ex.args)
        sys.print_exception(main_ex)  # pylint: disable=no-member
        if mtStopwatch:
            mtStopwatch.reset_system()
        continue
