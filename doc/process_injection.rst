Process injection
*****************

ppTOP works in 2 modes: first is launching new Python program, ppTOP just reads
its code, inserts *pptop.inection* module before, which wait for ready event
(Ctrl+L) or for specified number of seconds ("-w" command line option).

The second mode is injecting into running Python process. When I created ppTOP,
I was inspired by `pyrasite <https://github.com/lmacken/pyrasite>`_ which is
pretty cool but unfortunately outdated, plus I wanted completely console UI.

ppTOP has 3 different but similar :) inject methods: *native*, *loadcffi*,
*unsafe*. You may also specify *auto* method and ppTOP will try all 3, starting
from native. Inject method can be specified in
:doc:`configuration<configuration>` (default is *native*) or set with
"--inject-method" command line option.

All methods require *gdb* and of course an access to the process, so you must
be root or launch ppTOP under the same user. Only connections to Python 3
processes are supported.

native
======

When working in native method, ppTOP injects a small C library, which does the
rest. Officially supported and best method, usually works, if no - report an
issue.

loadcffi
========

Calling *PyRun_SimpleString* Python method directly with *gdb* is very unstable
and usually process get segmentation fault. Of course, ppTOP locks GIL before,
but usually it doesn't help. However, I've found that when certain libraries
are loaded, it works fine.

So, before starting main injection code, ppTOP injects *_cffi_backend* shared
library into process. Good news - if your program use `requests
<https://2.python-requests.org/>`_, CFFI backend library is probably already
loaded and you may even try using *unsafe* method for this process.

If you want to try this method, *cffi* must be installed. If not - install it
with shell command:

.. code:: shell

    pip3 install cffi

unsafe
======

Lock GIL and call *PyRun_SimpleString* without any preparations and helpers.
Run and pray.
