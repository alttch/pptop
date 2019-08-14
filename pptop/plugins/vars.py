from pptop import GenericPlugin, palette

import os


class Plugin(GenericPlugin):
    '''
    vars plugin: variable/function watcher

    Shortcuts:

        i      : insert new variable/function
        DEL    : delete variable/function
        e      : edit
        Ctrl-d : duplicate
        Ctrl-x :  delete all variables

    Items should be entered as mod::object, e.g.

    my.module::my.variable

    To modify result, use standard Python code, e.g.

    my.module::my_function(1,2,3)['field'1] - valid result
    '''

    def on_load(self):
        self.title = 'Variable/function watcher'
        self.sorting_rev = False
        # self.background = True
        self.vars = {}
        default_config_file = '~/.pptop/vars.list'
        self.inputs = {
            'i': None,
            'e': None,
            'l': default_config_file,
            's': default_config_file
        }

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
                    self.trigger(force=True)
                    if var == 'e' and value != prev_value:
                        self.key_event = 'KEY_DC'
                    self.inputs[var] = None
        if var == 's':
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
                'l': 'load: ',
                's': 'save: ',
                }
        return ps.get(var)

    def handle_key_event(self, event, dtd):
        if event in ['KEY_BACKSPACE', 'KEY_DC']:
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
                self.trigger(force=True)
        elif event == 'CTRL_X':
            self.injection_command(cmd='clear')
            self.print_message('Variable list cleared', color=palette.WARNING)

    def get_table_row_color(self, element=None, raw=None):
        if isinstance(element['value'],
                      str) and element['value'].startswith('!ERROR'):
            return palette.ERROR

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection_load(**kwargs):
    g.vars = []


def injection(cmd=None, var=None):
    if cmd == 'add':
        var = var.replace('::', ':').strip()
        mod, var = var.split(':')
        g.vars.append((mod, var))
    elif cmd == 'del':
        var = var.replace('::', ':').strip()
        mod, var = var.split(':')
        g.vars.remove((mod, var))
    elif cmd == 'clear':
        g.vars.clear()
    else:
        import importlib
        result = []
        for v in g.vars:
            mod = v[0]
            var = v[1]
            r = {'name': '{}::{}'.format(mod, var)}
            try:
                ge = {}
                src = 'import {}; out={}.{}'.format(mod, mod, var)
                exec(src, ge)
                val = ge['out']
                # for v in var.split('.'):
                # val = getattr(val, v)
                r['value'] = val if isinstance(val, int) or \
                        isinstance(val, float) or \
                        isinstance(val, bool) else str(val)
            except Exception as e:
                r['value'] = '!ERROR: {}'.format(e)
            result.append(r)
        print(result)
        return result
