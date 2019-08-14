from pptop import GenericPlugin, palette


class Plugin(GenericPlugin):
    '''
    vars plugin: variable/function watcher

    Shortcuts:

        INS  : insert new variable/function
        DEL  : delete variable/function
        d    : duplicate
        e    : edit

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
        self.inputs = {'i': None, 'e': None}

    def add_variable(self, var):
        try:
            self.injection_command(cmd='add', var=var)
        except:
            self.print_error('Unable to add variable')

    def handle_input(self, var, value, prev_value):
        if not value:
            return
        if value != prev_value:
            self.add_variable(value)
            self.trigger(force=True)
        if var == 'e' and value != prev_value:
            self.key_event = 'KEY_DC'

    def get_input(self, var):
        if var == 'e':
            el = self.get_selected_row()
            if el:
                return el.get('name')

    def handle_key_event(self, event, dtd):
        if event in ['KEY_BACKSPACE', 'KEY_DC']:
            el = self.get_selected_row()
            if el:
                try:
                    self.injection_command(cmd='del', var=el['name'])
                    self.delete_selected_row()
                except:
                    self.print_error('Unable to delete variable')
        elif event == 'd':
            el = self.get_selected_row()
            if el:
                self.add_variable(el['name'])
                self.trigger(force=True)

    def get_table_row_color(self, element=None, raw=None):
        if isinstance(element['value'],
                      str) and element['value'].startswith('!ERROR'):
            return palette.ERROR


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
