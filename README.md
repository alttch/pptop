# ppTOP

<img src="https://github.com/alttch/pptop/blob/master/doc/images/pptop.png?raw=true" align="right" width="200" /> ppTOP is open, extensible Python injector/profiler/analyzer.

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

* Python: 3.5+ is required, as ppTOP uses asyncio
* Injection into running processes requires *gdb* (present in almost
  all Linux distributions)
* Only Linux systems are currently supported

## Features

ppTOP can be injected into any running Python process

[![asciicast](https://asciinema.org/a/262581.svg)](https://asciinema.org/a/262581)

or you can load Python program manually and profile its launch

[![asciicast](https://asciinema.org/a/262585.svg)](https://asciinema.org/a/262585)

To launch a program, press *Ctrl+L* or specify *-w sec* param in command line
args to launch it automatically after the specified delay.

Data from connected process is collected in real-time and displayed in
table-based console UI, which can be easily extended with custom plugins.

All data tables can be scrolled, filtered, new data collection can be paused.
In case of problems, any plugin can be re-injected at any time.

## Usage

To start ppTOP, type

```shell
    pptop
```

and then select Python process you want to inject to from the list. A process
should have an access to *pptop.injection* module, so either use the same
Python as ppTOP does, or **pptop** package must be installed manually into
corresponding virtual environment.

Alternatively, you can start it with

```shell
    pptop <PID>
    # or
    pptop <PID-FILE>
```

and specify the process from the command line.

If you want to analyze program startup, just type

```shell
    pptop /path/to/program.py
```

The program will be loaded in waiting state, press *Ctrl+L* when you are ready.

## Configuration

Plugins and keyboard shortcuts are configured by default in
*~/.pptop/pptop.yml* file (created automatically at first launch).

## Standard plugins

* **env** view process OS environment variables
* **log** inject into all Python loggers and collect log messages
* **open_files** view process open files
* **script_runner** launch a custom scripts inside process
* **threads** view process threads
* **vars** variable/function watcher
* **yappi** [yappi](https://github.com/sumerc/yappi) profiler plugin

Most of plugins contain 2 parts of code: one collects data inside profiling
process, other display it in ppTOP UI. For the profiling process all plug-ins
are invisible, safe and unloadable (at least they try their best :)

## Console mode

With "`" button, remote Python console can be opened. It has no full
functionality like a standard Python console, but supports all frequently used
features, like importing modules, defining functions and variables,
executing functions and loops etc.

[![asciicast](https://asciinema.org/a/262587.svg)](https://asciinema.org/a/262587)

Console has own remote *globals*, which are preserved until ppTOP quit and
injected server is terminated.

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
