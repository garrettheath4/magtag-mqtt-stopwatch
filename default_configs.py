configs = {
    'timezone': "America/New_York",  # http://worldtimeapi.org/timezones
    'timezone_offset': -4,
    # MQTT port
    'port': 1883,
    'topic_past': 'dogs/last_time_out',
    # minutes between each screen refresh; optional
    'refresh_mins': 1,
    # front LEDs will turn ON if stopwatch is over this many minutes; optional (-1 to disable)
    'leds_on_mins_threshold': 150,
    # front LEDs will never turn on before this hour of the day (0 to 23, 24 to disable)
    'sleep_daily_before_hour': 8,
    'backlight_brightness': 0.1,
}

