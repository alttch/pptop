Troubleshooting
***************

Can not inject or coredumped
============================

This happens. Injected plugins may access shared resources from own thread
without locking and if conflicts occur, this may cause crash of ppTOP or of
everything.

Actually, injecting code with *gdb* in Python program is not a reliable thing,
but as it works in 99% of cases, why don't use this feature for development or
testing? Just don't use ppTOP on production systems. Unless you have no choice.

Everything is slow
==================

* ppTOP is quickly-dirty written tool and can not display tables with a tens of
  thousands of lines. Just keep it short.

* There's the magic meter at the bottom-right corner of ppTOP UI:

  .. figure:: images/meter.png
    :scale: 100%

First 2 numbers are frames send/received. It sound be equal and run quickly.
The next number is the current bandwidth between ppTOP and injected process. If
it exceeds 2-3 MB per second, you should pause/stop plugin or reset it (press
*F1* to read plugin help for more info).

Other
=====

Note that data collection by background plugins is stopped, when user enters
console mode.
