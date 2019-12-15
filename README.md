# ppTOP

Project home: https://pptop.io/

<img src="https://github.com/alttch/pptop/blob/master/media/logo.png?raw=true" align="right" width="200" /> ppTOP is open, extensible Python injector/profiler/analyzer.

The main idea is to inject a custom code inside Python process (already running
or going to be launched) and analyze its behavior with no any code
modifications.

<img src="https://img.shields.io/pypi/v/pptop.svg" /> <img src="https://img.shields.io/badge/license-MIT-green" /> <img src="https://img.shields.io/badge/python-3.5%20%7C%203.6%20%7C%203.7-blue.svg" /> <img src="https://img.shields.io/badge/-beta-orange.svg" />

Say no to "prints" and garbage in debug logs - now you have ppTOP. A modern MRI
scanner for Python.

## Installation

```
  pip3 install pptop
```

* Python: 3.5+ is required, as ppTOP uses asyncio
* Can be injected into any Python version (tested: 2.7+)
* Injection into running processes requires *gdb* (present in almost
  all Linux distributions)
* Only Linux systems are currently supported

<img src="https://github.com/alttch/pptop/blob/master/media/demo.gif?raw=true" width="750" />

## Features

ppTOP can be injected into any running Python process

[![asciicast](https://asciinema.org/a/265309.svg)](https://asciinema.org/a/265309)

or you can load Python program manually and profile its launch

[![asciicast](https://asciinema.org/a/265310.svg)](https://asciinema.org/a/265310)

To launch a program, press *Ctrl+L* or specify *-w sec* param in command line
args to start it automatically after the specified delay.

Data from connected process is collected in real-time and displayed in
table-based console UI, which can be easily extended with custom plugins.

All data tables can be scrolled, filtered, new data collection can be paused.
In case of problems, any plugin can be re-injected at any time.

## Usage

To start ppTOP, type

```shell
    pptop
```

and then select Python process you want to inject to from the list.

Alternatively, you can start it with

```shell
    pptop PID
    # or
    pptop PID-FILE
```

and specify the process from the command line.

If you want to analyze program startup, just type

```shell
    pptop /path/to/program.py
```

The program will be loaded in waiting state, press *Ctrl+L* when you are ready.

To get a help for the current plugin, press *F1* to display module
documentation.

## Configuration

Plugins and keyboard shortcuts are configured by default in
*~/.pptop/pptop.yml* file (created automatically at first launch).

## Standard plugins

* **asyncio** asyncio loop monitor
* **atasker** [atasker](https://github.com/alttch/atasker) monitor
* **env** view process OS environment variables
* **log** inject into all Python loggers and collect log messages
* **malloc** trace object memory allocations
* **neotasker** [neotasker](https://github.com/alttch/neotasker) monitor
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

[![asciicast](https://asciinema.org/a/265307.svg)](https://asciinema.org/a/265307)

Console has own remote *globals*, which are preserved until ppTOP quit and
injected server is terminated.

## Grab stdout/stderr

If launched with "-g" option, ppTOP will grab stdout/stderr of injected process
and print it to local console. You can view local console without entering
console mode, by pressing *Ctrl+O*.

## Documentation

Configuration, troubleshooting, advanced usage, plugin development:
https://pptop.io/doc/

## TODO

* [ ] More plugins
* [ ] Advanced filtering
* [ ] Data snapshots
* [ ] Step-by-step debugger
* [ ] JSON API, web interface
* [ ] Charts

Enjoy! :)

p.s. Code in **master** can be completely broken, install with *pip* only.
