# SPDX-FileCopyrightText: 2019 Dave Astels for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`adafruit_logging`
================================================================================

Logging module for CircuitPython


* Author(s): Dave Astels

Implementation Notes
--------------------

**Hardware:**


**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""
# pylint:disable=redefined-outer-name,consider-using-enumerate,no-self-use
# pylint:disable=invalid-name

import time

__version__ = "1.2.8"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_Logger.git"


LEVELS = [
    (00, "NOTSET"),
    (10, "DEBUG"),
    (20, "INFO"),
    (30, "WARNING"),
    (40, "ERROR"),
    (50, "CRITICAL"),
]

for value, name in LEVELS:
    globals()[name] = value


def level_for(value):
    """Convert a numberic level to the most appropriate name.

    :param value: a numeric level

    """
    for i in range(len(LEVELS)):
        if value == LEVELS[i][0]:
            return LEVELS[i][1]
        if value < LEVELS[i][0]:
            return LEVELS[i - 1][1]
    return LEVELS[0][1]


class LoggingHandler:
    """Abstract logging message handler."""

    def format(self, level, msg):
        """Generate a timestamped message.

        :param level: the logging level
        :param msg: the message to log

        """
        return "{0}: {1} - {2}".format(time.monotonic(), level_for(level), msg)

    def emit(self, level, msg):
        """Send a message where it should go.
        Place holder for subclass implementations.
        """
        raise NotImplementedError()


class PrintHandler(LoggingHandler):
    """Send logging messages to the console by using print."""

    def emit(self, level, msg):
        """Send a message to teh console.

        :param level: the logging level
        :param msg: the message to log

        """
        print(self.format(level, msg))


# The level module-global variables get created when loaded
# pylint:disable=undefined-variable

logger_cache = dict()
null_logger = None

# pylint:disable=global-statement
def getLogger(name):
    """Create or retrieve a logger by name.

    :param name: the name of the logger to create/retrieve None will cause the
                 NullLogger instance to be returned.

    """
    global null_logger
    if not name or name == "":
        if not null_logger:
            null_logger = NullLogger()
        return null_logger

    if name not in logger_cache:
        logger_cache[name] = Logger()
    return logger_cache[name]


# pylint:enable=global-statement


class Logger:
    """Provide a logging api."""

    def __init__(self):
        """Create an instance."""
        self._level = NOTSET
        self._handler = PrintHandler()

    def setLevel(self, value):
        """Set the logging cuttoff level.

        :param value: the lowest level to output

        """
        self._level = value

    def getEffectiveLevel(self):
        """Get the effective level for this logger.

        :return: the lowest level to output

        """
        return self._level

    def addHandler(self, hldr):
        """Sets the handler of this logger to the specified handler.
        *NOTE* this is slightly different from the CPython equivalent which adds
        the handler rather than replaceing it.

        :param hldr: the handler

        """
        self._handler = hldr

    def log(self, level, format_string, *args):
        """Log a message.

        :param level: the priority level at which to log
        :param format_string: the core message string with embedded formatting directives
        :param args: arguments to ``format_string.format()``, can be empty

        """
        if level >= self._level:
            self._handler.emit(level, format_string % args)

    def debug(self, format_string, *args):
        """Log a debug message.

        :param format_string: the core message string with embedded formatting directives
        :param args: arguments to ``format_string.format()``, can be empty

        """
        self.log(DEBUG, format_string, *args)

    def info(self, format_string, *args):
        """Log a info message.

        :param format_string: the core message string with embedded formatting directives
        :param args: arguments to ``format_string.format()``, can be empty

        """
        self.log(INFO, format_string, *args)

    def warning(self, format_string, *args):
        """Log a warning message.

        :param format_string: the core message string with embedded formatting directives
        :param args: arguments to ``format_string.format()``, can be empty

        """
        self.log(WARNING, format_string, *args)

    def error(self, format_string, *args):
        """Log a error message.

        :param format_string: the core message string with embedded formatting directives
        :param args: arguments to ``format_string.format()``, can be empty

        """
        self.log(ERROR, format_string, *args)

    def critical(self, format_string, *args):
        """Log a critical message.

        :param format_string: the core message string with embedded formatting directives
        :param args: arguments to ``format_string.format()``, can be empty

        """
        self.log(CRITICAL, format_string, *args)


class NullLogger:
    """Provide an empty logger.
    This can be used in place of a real logger to more efficiently disable logging."""

    def __init__(self):
        """Dummy implementation."""

    def setLevel(self, value):
        """Dummy implementation."""

    def getEffectiveLevel(self):
        """Dummy implementation."""
        return NOTSET

    def addHandler(self, hldr):
        """Dummy implementation."""

    def log(self, level, format_string, *args):
        """Dummy implementation."""

    def debug(self, format_string, *args):
        """Dummy implementation."""

    def info(self, format_string, *args):
        """Dummy implementation."""

    def warning(self, format_string, *args):
        """Dummy implementation."""

    def error(self, format_string, *args):
        """Dummy implementation."""

    def critical(self, format_string, *args):
        """Dummy implementation."""
