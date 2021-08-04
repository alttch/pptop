from pptop.plugin import GenericPlugin, palette

import os

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    asyncio plugin: asyncio loop monitor

    requires: Python 3.5+

    Shortcuts:

        i      : insert new loop
        o      : load loop list from file
        s      : save loop list to file

    Loops should be entered as mod::object, e.g.

    my.module::my_loop
    '''

    def on_load(self):
        self.title = 'asyncio loop monitor'
        self.short_name = 'AIO'
        self.sorting_rev = False
        self.config_loops = []
        self.background_loader = True
        try:
            default_config_file = self.config['list']
            with open(os.path.expanduser(default_config_file)) as fh:
                self.config_loops = list(
                    filter(None, [x.strip() for x in fh.readlines()]))
        except:
            default_config_file = '~/.pptop/asyncio_loops.list'
        self.inputs = {
            'i': None,
            'o': default_config_file,
            's': default_config_file
        }

    def process_data(self, data):
        result = []
        for d in data:
            v = OrderedDict()
            v['loop'] = d[0]
            v['state'] = d[1]
            v['coro'] = d[2]
            v['cmd'] = d[4]
            v['file'] = d[3]
            result.append(v)
        return result

    def get_injection_load_params(self):
        return {'l': self.config_loops}

    def add_loop(self, var):
        try:
            self.injection_command(cmd='add', loop=var)
            return True
        except:
            self.print_error('Unable to add loop')
            return False

    def handle_input(self, var, value, prev_value):
        if not value:
            return
        if var == 'i':
            if self.add_loop(value):
                self.trigger_threadsafe(force=True)
                self.inputs[var] = None
        elif var == 'o':
            try:
                with open(os.path.expanduser(value)) as fh:
                    loop_list = list(
                        filter(None, [x.strip() for x in fh.readlines()]))
                    try:
                        self.injection_command(cmd='replace', loop=loop_list)
                    except:
                        self.print_error('Unable to replace loop list')
            except Exception as e:
                self.print_error(e)
        elif var == 's':
            try:
                loop_list = set()
                for v in self.data:
                    loop_list.add(v['loop'])
                with open(os.path.expanduser(value), 'w') as fh:
                    for v in sorted(loop_list):
                        fh.write(v + '\n')
            except Exception as e:
                self.print_error(e)

    def get_input_prompt(self, var):
        ps = {
            'i': 'add: ',
            'o': 'load: ',
            's': 'save: ',
        }
        return ps.get(var)

    def handle_key_event(self, event, key, dtd):
        if event == 'delete':
            el = self.get_selected_row()
            if el:
                try:
                    self.injection_command(cmd='del', loop=el['loop'])
                    self.delete_selected_row()
                except:
                    self.print_error('Unable to delete loop')
        elif event == 'reset':
            self.injection_command(cmd='clear')
            self.print_message('Loop list cleared', color=palette.WARNING)

    def get_table_col_color(self, element, key, value):
        if element['state'] == '!ERROR':
            return palette.ERROR
        elif element['state'] == 'FINISHED':
            return palette.OK
        elif element['state'] == 'CANCELLED':
            return palette.DEBUG
        elif key == 'loop':
            return palette.YELLOW
        elif key == 'coro':
            return palette.BOLD
        elif key == 'cmd':
            return palette.YELLOW
        elif key == 'state' and value == 'PENDING':
            return palette.BLUE

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection_load(l=None, **kwargs):
    g.loops = []
    if l:
        for loop in l:
            try:
                if loop[loop.find(':') + 1] == ':':
                    loop = loop.replace('::', ':', 1).strip()
            except:
                pass
            mod, loop = loop.split(':', 1)
            g.loops.append((mod, loop))


def injection(cmd=None, loop=None):

    def parse_loop(loop):
        try:
            if loop[loop.find(':') + 1] == ':':
                loop = loop.replace('::', ':', 1).strip()
        except:
            pass
        mod, loop = loop.split(':', 1)
        return mod, loop

    if cmd == 'add':
        g.loops.append(parse_loop(loop))
    elif cmd == 'del':
        g.loops.remove(parse_loop(loop))
    elif cmd == 'clear':
        g.loops = []
    elif cmd == 'replace':
        g.loops = []
        for v in loop:
            g.loops.append(parse_loop(v))
    else:
        import linecache
        result = []
        for v in g.loops:
            mod = v[0]
            loop = v[1]
            loop_name = '{}::{}'.format(mod, loop)
            try:
                import asyncio
                if hasattr(asyncio, 'all_tasks'):
                    fn = 'asyncio.all_tasks'
                else:
                    fn = 'asyncio.Task.all_tasks'
                ge = {}
                src = ('import {mod}; import asyncio;' +
                       'out=list({fn}(loop={mod}.{loop}))').format(fn=fn,
                                                                   mod=mod,
                                                                   loop=loop)
                exec(src, ge)
                for l in ge['out']:
                    coro = ''
                    fname = ''
                    isl = str(l).split()
                    # will parse Task repr until official interface for frames
                    # appear
                    for i, z in enumerate(isl):
                        if z.startswith('coro='):
                            coro = z.split('=', 1)[-1].strip()
                            if coro.startswith('<'):
                                coro = coro[1:]
                        elif z == 'at' and isl[
                                i - 1] == 'running' and i + 1 < len(isl):
                            fname = isl[i + 1].strip()
                            while fname.endswith('>'):
                                fname = fname[:-1]
                    try:
                        f, ln = fname.split(':')
                        cmd = linecache.getline(f, int(ln)).strip()
                    except:
                        cmd = ''
                    result.append((loop_name, l._state, coro, fname, cmd))
            except:
                import sys
                e = sys.exc_info()
                coro = '{}: {}'.format(e[0].__name__, str(e[1]))
                result.append((loop_name, '!ERROR', coro, '', ''))
        return result
