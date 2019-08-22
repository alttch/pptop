from pptop.plugin import GenericPlugin, palette

import os

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    atasker plugin: monitor atasker supervisor (alpha)

    config.task_supervisor: task supervisor object (default:
    atasker::task_supervisor)

    requires: Python 3.5+

    Shortcuts:

        a      : async loops
        (TODO)
        w      : schedulers(workers)
        t      : thread pool stats
        m      : multiprocessing pool stats

    https://github.com/alttch/atasker
    '''

    def on_load(self):
        self.title = 'atasker monitor'
        self.short_name = 'ATaskr'
        self.sorting_rev = False

    def load_remote_data(self):
        return self.injection_command(cmd='loops')

    def process_data(self, data):
        result = []
        for d in data:
            v = OrderedDict()
            v['loop'] = d[0]
            v['state'] = d[1]
            v['worker'] = d[5]
            v['coro'] = d[2]
            v['cmd'] = d[4]
            v['file'] = d[3]
            result.append(v)
        return result

    def get_injection_load_params(self):
        return {'task_supervisor': self.config.get('task_supervisor')}

    def get_table_col_color(self, element, key, value):
        if element['state'] == '!ERROR':
            return palette.ERROR
        elif element['state'] == 'FINISHED':
            return palette.OK
        elif element['state'] == 'CANCELLED':
            return palette.DEBUG
        elif key == 'loop':
            return palette.YELLOW
        elif key == 'worker':
            return palette.CYAN
        elif key == 'coro':
            return palette.BOLD
        elif key == 'cmd':
            return palette.YELLOW
        elif key == 'state' and value == 'PENDING':
            return palette.BLUE

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection_load(task_supervisor=None, **kwargs):
    g.task_supervisor = None
    if task_supervisor:
        try:
            if task_supervisor[task_supervisor.find(':') + 1] == ':':
                task_supervisor = task_supervisor.replace('::', ':', 1).strip()
        except:
            pass
        mod, s = task_supervisor.split(':', 1)
        gl = {}
        exec('import {mod}; out={mod}.{sv}'.format(mod=mod, sv=s), gl)
        g.task_supervisor = gl['out']
    else:
        from atasker import task_supervisor
        g.task_supervisor = task_supervisor


def injection(cmd=None):
    if cmd == 'loops':
        import linecache
        import asyncio
        result = []
        loops = {('__supervisor__', g.task_supervisor.event_loop)}
        for i, v in g.task_supervisor.get_info(-1).aloops.items():
            l = v.get_loop()
            if l:
                loops.add((i, l))
        for loop_name, loop in loops:
            try:
                for l in asyncio.Task.all_tasks(loop=loop):
                    coro = ''
                    fname = ''
                    isl = str(l).split()
                    # will parse Task repr until official interface for frames
                    # appear
                    for i, z in enumerate(isl):
                        if z.startswith('coro='):
                            coro = z.split('=', 1)[-1].strip()
                            if coro.startswith('<'): coro = coro[1:]
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
                    try:
                        try:
                            w = l._coro.cr_frame.f_locals['scheduler']
                        except:
                            w = l._coro.cr_frame.f_locals['self']
                        if not w._is_worker:
                            raise ValueError
                        n = w.name
                        worker = n[19:] if n.startswith(
                            '_background_worker_') else n
                    except:
                        worker = ''
                    result.append(
                        (loop_name, l._state, coro, fname, cmd, worker))
            except:
                import sys
                e = sys.exc_info()
                coro = '{}: {}'.format(e[0].__name__, str(e[1]))
                result.append((loop_name, '!ERROR', coro, '', '', ''))
        return result
