Configuration
*************

Default configuration is automatically created as *~/.pptop/pptop.yml* at the
first launch. Alternative configuration can be specified with *"-f"* command
line key:

.. code:: shell

    pptp -f <CONFIG_FILE>

Configuration file is YAML file, which looks like:

.. literalinclude:: ../pptop/config/pptop.yml
    :language: yaml

Main configuration
==================

Section *console* configures default console options:

.. code:: yaml

    console:
      json-mode: true

As you see, JSON mode is on by default, to display list and dictionary objects
in a standard Python way by default, set it to *false*.

Next section is *display*

.. code:: yaml

    display:
      colors: true
      glyphs: true

and used to enable/disable colors and unicode glyphs. Both can be also disable
with command like options *-R* (disables colors and glyphs) and
*--disable-glyphs* (disable glyphs only). It's recommended to disable unicode
glyphs if you have an old terminal or working via old SSH client.

Plugins configuration
=====================

The next section is *plugins*, which configures plugins to load:

.. code:: yaml

    plugins:
      plugin_selector:
        default: true
        shortcut: KEY_F(2)
      script_runner:
        shortcut: KEY_F(3)
        interval: 5
        config:
          script_dir: ~/.pptop/scripts
      #.....

Each plugin can have the following options:

* **default** specifies that plugin is default. Console option equivalent: *-d*

* **shortcut** keyboard shortcut, used to launch plugin. Keys must be specified
  in `curses <https://docs.python.org/3/howto/curses.html>`_ format, except
  Ctrl+key combinations should be specified as CTRL_K (all uppercase), e.g.
  CTRL_M for Ctrl+m.

* **interval** plugin data reload interval in seconds, default is *1*.

* **autostart** if plugin supports collecting data in background, setting this
  option to *true* will ask ppTOP to automatically inject and launch the plugin
  at startup. Otherwise the plugin will be injected only.

* **filter** default plugin filter.

* **config** this section is passed to plugin as-is, so see the corresponding
  plugin help how to use it (launch the plugin, then press *F1*).

Any configuration option can be overriden from command line with *-o <PARAM>*,
which can be specified multiple times.

E.g. to include plugin, not listed in configuration, specify:

.. code:: shell
    
    pptop -o plugin_name

to set reload interval for any plugin, specify it as *plugin_name.interval*
e.g., lets set *threads* plugin to reload data every 0.5 seconds:

.. code:: shell
    
    pptop -o threads.interval=0.5

to set config option, specify it as *plugin_name.config.option*, e.g. let's set
alternative default list file for *vars* plugin:

.. code:: shell
    
    pptop -o vars.config.list=/path/to/mylist

