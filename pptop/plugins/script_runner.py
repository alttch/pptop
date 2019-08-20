from pptop.plugin import GenericPlugin, palette
from pptop.logger import log, log_traceback
from pptop.core import format_shortcut

import glob
import os

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    script_runner plugin: run a custom script

    Executes selected script from ~/.pptop/scripts (can be changed with
    config.script_dir option)

    To get result from the script, put it to variable "out", e.g.

        print('hello world!')
        out = 'printed'

    To set global hotkey for script, add the following to config (script path
    is relative to script_dir directory):

        config:
          # ...
          script-keys:
            tests/test1.py: 1
            tests/test2.py: 2
    '''
    default_interval = 30

    def on_load(self):
        self.title = 'Script runner'
        self.description = 'Run selected script from ~/.pptop/scripts'
        self.short_name = 'Script'
        self.sorting_rev = False
        self.selectable = True
        if 'script_dir' in self.config:
            self.script_dir = os.path.expanduser(self.config['script_dir'])
        else:
            self.script_dir = self.get_config_dir() + '/scripts'
        self.global_script_hotkeys = {}
        self.script_hotkey_help = {}
        script_keys = self.config.get('script-keys')
        if not script_keys:
            script_keys = {}
        for i, v in script_keys.items():
            for k in v if isinstance(v, list) else [v]:
                self.global_script_hotkeys[str(k)] = str(i)
                log('script hot key {} = {}'.format(k, i))
                if not os.path.isfile('{}/{}'.format(self.script_dir, i)):
                    log('WARNING: script {} doesn\'t exists'.format(i))
            self.script_hotkey_help[i] = ', '.join([
                format_shortcut(x) for x in v
            ]) if isinstance(v, list) else format_shortcut(v)

    def load_data(self):
        with self.data_lock:
            self.data.clear()
            try:
                for g in glob.glob(
                        self.script_dir + '/**/*.py', recursive=True):
                    d = OrderedDict()
                    script = g[len(self.script_dir) + 1:]
                    d['script'] = script
                    d['shortcut'] = self.script_hotkey_help.get(script, '')
                    self.data.append(d)
            except:
                log_traceback()

    def handle_key_global_event(self, event, key):
        if key in self.global_script_hotkeys:
            self.run_script(self.global_script_hotkeys[key], quiet=True)

    def handle_key_event(self, event, key, dtd):
        if event == 'select':
            d = self.get_selected_row()
            if d:
                script = d['script']
                self.run_script(script)

    def run_script(self, script, quiet=False):
        log('executing script {}'.format(script))
        self.inject()
        try:
            fname = '{}/{}'.format(self.script_dir, script)
            with open(fname) as fd:
                src = fd.read()
        except:
            log_traceback()
            if not quiet:
                self.print_message(
                    'Unable to load {}'.format(fname), color=palette.ERROR)
            return
        try:
            result = self.injection_command(src=src)
        except Exception as e:
            result = e
        if not isinstance(result, Exception):
            if result is None:
                msg = '{} executed'.format(script)
            else:
                msg = '{}: {}'.format(script, result)
            if not quiet: self.print_message(msg, color=palette.GREEN_BOLD)
        else:
            if not quiet:
                self.print_message(
                    '{}: {}'.format(script, result), color=palette.ERROR)

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def toggle_pause(self):
        pass

    def get_table_col_color(self, element, key, value):
        if key == 'shortcut':
            return palette.CYAN_BOLD


def injection(src, **kwargs):
    d = {}
    try:
        exec(src, d)
    except Exception as e:
        return e
    return d.get('out')
