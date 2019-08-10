#!/usr/bin/env python3

from pptop import start
import curses

try:
    start()
finally:
    curses.endwin()
