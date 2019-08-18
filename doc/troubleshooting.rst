Troubleshooting
***************

Can not inject or coredumped
============================

* Try again.

* This happens. Injected plugins may access shared resources from own thread
  without locking and if conflicts occur, this may cause crash of ppTOP or of
  everything.

* Injecting code with *gdb* in Python program is not a reliable thing, but as
  it works in 99% of cases, why don't use this feature for development or
  testing? Just don't use ppTOP on production systems. Unless you have no
  choice.

* Read about :doc:`process injection<process_injection>` and try different
  types.

Everything is slow
==================

* ppTOP is quickly-dirty written tool and can not display tables with tens of
  thousands lines. Just keep it short.

* There's the magic meter at the bottom-right corner of ppTOP UI:

  .. figure:: images/meter.png
    :scale: 100%

First 2 numbers are frames sent/received. It should be equal and run quickly.
The next number is current bandwidth between ppTOP and injected process. If it
exceeds 2-3 MB per second, you should pause/stop plugin or reset it (press *F1*
to read plugin help for more info).

Plugin doesn't work in launch mode
==================================

Some plugins, e.g. log viewer, inject themselves to system objects. After the
launch, program can create new objects (e.g. own logger) and log there. Press
Ctrl+I to re-inject plugin after the main code is started.

Console UI is broken
====================

Try disabling unicode glyphs (*"pptop --disable-glyphs"*) or run ppTOP in raw
mode (no colors, no glyphs, *"pptop -R"*)

Doesn't work properly under tmux
================================

Sometimes this happens with cursed-based UIs. Try

.. code:: shell

    env TERM=xterm pptop

I see a lot of "pickle" calls
=============================

Make sure cPickle is installed for the Python which runs injected process.
Python 3 has cPickle integrated by default. ppTOP injection looks for cPickle
module in all variations and only then falls back to usual "pickle".

Other
=====

Note that data collection by background plugins is stopped, when user enters
console mode.
