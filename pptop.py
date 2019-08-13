#!/usr/bin/env python3

from pptop import start
import curses
import os

try:
    start()
finally:
    # always end curses
    try:
        curses.endwin()
    except:
        pass
# force quick exit
os._exit(0)
