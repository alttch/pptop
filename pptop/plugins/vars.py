from pptop.plugin import GenericPlugin, palette

import os

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    vars plugin: variable/function watcher

    Shortcuts:

        i      : insert new variable/function
        e      : edit
        o      : load variable list from file
        s      : save variable list to file
        Ctrl-d : duplicate

    Items should be entered as mod::object, e.g.

    my.module::my.variable

    To modify result, use standard Python code, e.g.

    my.module::my_function(1,2,3)['field'] - valid result
    '''

    def on_load(self):
        self.title = 'Variable/function watcher'
        self.sorting_rev = False
        self.config_vars = []
        try:
            default_config_file = self.config['list']
            with open(os.path.expanduser(default_config_file)) as fh:
                self.config_vars = list(
                    filter(None, [x.strip() for x in fh.readlines()]))
        except:
            default_config_file = '~/.pptop/vars.list'
        self.inputs = {
            'i': None,
            'e': None,
            'o': default_config_file,
            's': default_config_file
        }

    def process_data(self, data):
        result = []
        for d in data:
            v = OrderedDict()
            v['name'] = d['name']
            v['value'] = d['value']
            result.append(v)
        return result

    def get_injection_load_params(self):
        return {'v': self.config_vars}

    def add_variable(self, var):
        try:
            self.injection_command(cmd='add', var=var)
            return True
        except:
            self.print_error('Unable to add variable')
            return False

    def handle_input(self, var, value, prev_value):
        if not value:
            return
        if var in ['i', 'e']:
            if value != prev_value or var == 'i':
                if self.add_variable(value):
                    self.trigger_threadsafe(force=True)
                    if var == 'e' and value != prev_value:
                        self.key_event = 'delete'
                    self.inputs[var] = None
        elif var == 'o':
            try:
                with open(os.path.expanduser(value)) as fh:
                    var_list = list(
                        filter(None, [x.strip() for x in fh.readlines()]))
                    try:
                        self.injection_command(cmd='replace', var=var_list)
                    except:
                        self.print_error('Unable to replace var list')
            except Exception as e:
                self.print_error(e)
        elif var == 's':
            try:
                var_list = []
                for v in self.data:
                    var_list.append(v['name'])
                with open(os.path.expanduser(value), 'w') as fh:
                    for v in sorted(var_list):
                        fh.write(v + '\n')
            except Exception as e:
                self.print_error(e)

    def get_input(self, var):
        if var == 'e':
            el = self.get_selected_row()
            if el:
                return el.get('name')
            else:
                raise ValueError
        else:
            return super().get_input(var)

    def get_input_prompt(self, var):
        ps = {
            'i': 'add: ',
            'e': 'e: ',
            'o': 'load: ',
            's': 'save: ',
        }
        return ps.get(var)

    def handle_key_event(self, event, key, dtd):
        if event == 'delete':
            el = self.get_selected_row()
            if el:
                try:
                    self.injection_command(cmd='del', var=el['name'])
                    self.delete_selected_row()
                except:
                    self.print_error('Unable to delete variable')
        elif event == 'CTRL_D':
            el = self.get_selected_row()
            if el:
                self.add_variable(el['name'])
                self.trigger_threadsafe(force=True)
        elif event == 'reset':
            self.injection_command(cmd='clear')
            self.print_message('Variable list cleared', color=palette.WARNING)

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def get_table_col_color(self, element, key, value):
        if isinstance(element['value'],
                      str) and element['value'].startswith('!ERROR'):
            return palette.RED
        elif key == 'name':
            return palette.BOLD
        elif key == 'value':
            return palette.YELLOW


def injection_load(v=None, **kwargs):
    g.vars = []
    if v:
        for var in v:
            try:
                if var[var.find(':') + 1] == ':':
                    var = var.replace('::', ':', 1).strip()
            except:
                pass
            mod, var = var.split(':', 1)
            g.vars.append((mod, var))


def injection(cmd=None, var=None):

    def parse_var(var):
        try:
            if var[var.find(':') + 1] == ':':
                var = var.replace('::', ':', 1).strip()
        except:
            pass
        mod, var = var.split(':', 1)
        return mod, var

    if cmd == 'add':
        g.vars.append(parse_var(var))
    elif cmd == 'del':
        g.vars.remove(parse_var(var))
    elif cmd == 'clear':
        g.vars = []
    elif cmd == 'replace':
        g.vars = []
        for v in var:
            g.vars.append(parse_var(v))
    else:
        import importlib
        from pptop.injection import safe_serialize
        result = []
        for v in g.vars:
            mod = v[0]
            var = v[1]
            r = {'name': '{}::{}'.format(mod, var)}
            try:
                ge = {'__pptop_sserl': safe_serialize}
                src = 'import {}; out=__pptop_sserl({}.{})'.format(
                    mod, mod, var)
                exec(src, ge)
                val = ge['out']
                r['value'] = ge['out']
            except:
                import sys
                e = sys.exc_info()
                r['value'] = '!ERROR {}: {}'.format(e[0].__name__, str(e[1]))
            result.append(r)
        return result
