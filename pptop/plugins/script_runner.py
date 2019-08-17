from pptop.plugin import GenericPlugin, palette

import glob
import os


class Plugin(GenericPlugin):
    '''
    script_runner plugin: run a custom script

    Executes selected script from ~/.pptop/scripts (can be changed with
    config.script_dir option)

    To get result from the script, put it to variable "out", e.g.

        print('hello world!')
        out = 'printed'
    '''

    def on_load(self):
        self.title = 'Script runner'
        self.description = 'Run selected script from ~/.pptop/scripts'
        self.short_name = 'Script'
        self.sorting_rev = False
        if 'script_dir' in self.config:
            self.script_dir = os.path.expanduser(self.config['script_dir'])
        else:
            self.script_dir = self.get_config_dir() + '/scripts'

    def load_data(self):
        with self.data_lock:
            self.data.clear()
            try:
                for g in glob.glob(
                        self.script_dir + '/**/*.py', recursive=True):
                    self.data.append({'script': g[len(self.script_dir) + 1:]})
            except:
                pass

    def handle_key_event(self, event, key, dtd):
        if event == 'select':
            d = self.get_selected_row()
            if d:
                script = d['script']
                try:
                    fname = self.script_dir + '/' + script
                    with open(fname) as fd:
                        src = fd.read()
                except:
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
                    self.print_message(msg, color=palette.GREEN_BOLD)
                else:
                    self.print_message(
                        '{}: {}'.format(script, result), color=palette.ERROR)

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def toggle_pause(self):
        pass


def injection(src, **kwargs):
    d = {}
    try:
        exec(src, d)
    except Exception as e:
        return e
    return d.get('out')
