# ppTOP

ppTOP is open, extensible Python injector/profiler/analyzer.

The main idea is to inject a custom code inside Python process (already running
or going to be launched) and analyze its behavior with no any code
modifications.

<img src="https://img.shields.io/pypi/v/pptop.svg" /> <img src="https://img.shields.io/badge/license-MIT-green" /> <img src="https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7-blue.svg" /> <img src="https://img.shields.io/badge/-alpha-red.svg" />

Say no to "prints" and garbage in debug logs - now you have ppTOP. A modern MRI
scanner for Python.

## Installation

```
  pip3 install pptop
```

* Python: 3.5+ is required, as ppTOP uses asyncore
* Install *gdb*
* Only Linux systems are currently supported

## Features

ppTOP can be injected into any running Python process

[![asciicast](https://asciinema.org/a/262581.svg)](https://asciinema.org/a/262581)

or you can load Python program manually and profile its launch

[![asciicast](https://asciinema.org/a/262585.svg)](https://asciinema.org/a/262585)

Data from connected process is collected in real-time and displayed in
table-based console UI, which can be easily extended with custom plugins.

All data tables can be scrolled, filtered, new data collection ca be paused. In
case of problems, any plugin can be re-injected at any time.

## Standard plugins

* **env** view process OS environment variables
* **log** inject into all Python loggers and collect log messages
* **open_files** view process open files
* **script_runner** launch a custom scripts inside process
* **threads** view process threads
* **vars** variable/function watcher
* **yappi** [yappi](https://github.com/sumerc/yappi) profiler/plugin

Most of plugins contain 2 parts of code: one collects data inside profiling
process, other display it in ppTOP UI. For the profiling process all plug-ins
are invisible, safe and unloadable (at least they try their best :)

## Console mode

With "`" button, remote Python console can be opened. It has no full
functionality like a standard Python console, but it supports all frequently
used features, like importing modules, defining functions and variables,
executing functions and loops.

[![asciicast](https://asciinema.org/a/262587.svg)](https://asciinema.org/a/262587)

## Plugin docs

Plugins for ppTOP are very easily to write, it takes only about 100-150 lines
of code, as Core API provides all basic functionality: loading data, processing
data, sorting data etc.

Plugin development guide is coming very soon.

## TODO

* [ ] More plugins
* [ ] Advanced filtering
* [ ] Data snapshots
* [ ] Step-by-step debugger
* [ ] JSON API, web interface
* [ ] Charts

Enjoy! :)

p.s. Code in **master** can be completely broken, install with *pip* only.
