.PHONY: all prod dev clean FORCE

TARGET = /Volumes/CIRCUITPY
PROD_LIB = adafruit-circuitpython-bundle-7.x-mpy-20211217/lib
DEV_LIB = adafruit-circuitpython-bundle-py-20211217/lib

MODULE_DIRS = adafruit_bitmap_font adafruit_display_text adafruit_io adafruit_logging adafruit_magtag adafruit_minimqtt adafruit_portalbase
MODULE_FILES = adafruit_datetime adafruit_fakerequests adafruit_requests neopixel simpleio

src/code.py: FORCE default_configs.py
	rsync -avh src/code.py "$(TARGET)/code.py"

default_configs.py: FORCE
	rsync -avh default_configs.py "$(TARGET)/default_configs.py"

prod: src/code.py default_configs.py
	for dir in $(MODULE_DIRS); do \
		rsync -avh "$(PROD_LIB)/$$dir" "$(TARGET)/lib/" ; \
	done
	for file in $(MODULE_FILES); do \
		rsync -avh "$(PROD_LIB)/$$file.mpy" "$(TARGET)/lib/" ; \
	done

dev: src/code.py default_configs.py
	for dir in $(MODULE_DIRS); do \
		rsync -avh "$(DEV_LIB)/$$dir" "$(TARGET)/lib/" ; \
	done
	for file in $(MODULE_FILES); do \
		rsync -avh "$(DEV_LIB)/$$file.py" "$(TARGET)/lib/" ; \
	done

all: prod

clean:
	rm -rf "$(TARGET)"/lib/*
