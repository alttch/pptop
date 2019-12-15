from pptop.plugin import GenericPlugin, palette

import os
import time

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    neotasker plugin: monitor neotasker supervisor

    config.task_supervisor: task supervisor object (default:
    neotasker::task_supervisor)

    requires: Python 3.5+

    Shortcuts:

        a      : async loops
        w      : schedulers(workers)

    https://github.com/alttch/neotasker
    '''

    def on_load(self):
        self.orig_title = 'neotasker monitor'
        self.short_name = 'NTaskr'
        self.sorting_rev = False
        self.background_loader = True
        self.mode = 'loops'
        self.supervisor_status = None
        self.mode_shortcuts = {'a': 'loops', 'w': 'workers'}
        self.mode_sorting = {}
        self.set_title()
        self.task_types = {
            0: 'CORO',
            1: 'THREAD',
            2: 'MP',
        }
        self.task_status = {
            0: 'QUEUED',
            100: 'STARTED',
            2: 'DELAYED',
            -1: 'CANCELED'
        }

    def set_title(self):
        self.title = '{} ({})'.format(self.orig_title,
                                      self.mode.replace('_', ' '))

    def load_remote_data(self):
        self.set_title()
        return self.injection_command(cmd=self.mode)

    def handle_key_event(self, event, key, dtd):
        if event in self.mode_shortcuts:
            self.mode_sorting[self.mode] = (self.sorting_col, self.sorting_rev)
            self.save_cursor(self.mode)
            self.mode = self.mode_shortcuts[event]
            self.restore_cursor(self.mode)
            self.sorting_col, self.sorting_rev = self.mode_sorting.get(
                self.mode, (None, False))
            self.resume()
            self.trigger_threadsafe(force=True)

    def handle_pager_event(self, dtd):
        if self.key_event not in self.mode_shortcuts:
            super().handle_pager_event(dtd)

    def process_data(self, data):
        result = []
        self.supervisor_status = data[0]
        for d in data[1]:
            v = OrderedDict()
            if self.mode == 'loops':
                v['loop'] = d[0]
                v['state'] = d[1]
                v['worker'] = d[5]
                v['coro'] = d[2]
                v['cmd'] = d[4]
                v['file'] = d[3]
            elif self.mode == 'workers':
                v['name'] = d[0]
                v['class'] = d[1] if d[1] else ''
                if d[2] is True:
                    v['state'] = 'active'
                elif d[2] is False:
                    v['state'] = 'stopped'
                else:
                    v['state'] = ''
                v['int'] = d[3]
                v['inf'] = d[4] if d[4] else ''
                if d[5]:
                    v['aloop'] = d[5]
                else:
                    v['aloop'] = ''
                v['ttype'] = d[6]
            result.append(v)
        return result

    def format_dtd(self, dtd):
        for d in dtd:
            if self.mode == 'loops':
                yield d
            elif self.mode == 'workers':
                z = d.copy()
                z['ttype'] = self.task_types.get(z['ttype'])
                if z.get('int') == 0:
                    z['int'] = ''
                else:
                    z['int'] = str(z.get('int'))
                yield z

    def get_injection_load_params(self):
        return {'task_supervisor': self.config.get('task_supervisor')}

    def get_table_col_color(self, element, key, value):
        if self.mode == 'loops':
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
        elif self.mode == 'workers':
            if element['state'] != 'active':
                return palette.GREY_BOLD
            if key == 'name':
                return palette.CYAN
            elif key == 'class':
                return palette.BOLD
            elif key == 'state':
                return palette.BLUE
            elif key == 'int':
                return palette.CYAN
            elif key == 'inf':
                return palette.BOLD
            elif key == 'daemon':
                return
            elif key == 'priority':
                if value == 'CRITICAL':
                    return palette.RED_BOLD
                elif value == 'HIGH':
                    return palette.YELLOW
                elif value == 'LOW':
                    return palette.GREY_BOLD
                else:
                    return
            elif key == 'ttype':
                if value == 'CORO':
                    return palette.GREEN
                elif value == 'THREAD':
                    return palette.MAGENTA
                elif value == 'MP':
                    return palette.BLUE_BOLD
            elif key == 'aloop':
                return palette.YELLOW if \
                        value != '__supervisor__' else palette.RED_BOLD

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
        from neotasker import task_supervisor
        g.task_supervisor = task_supervisor


def injection(cmd=None):
    result = []
    if cmd == 'loops':
        import linecache
        import asyncio
        loops = set()
        for i, v in g.task_supervisor.get_aloops().items():
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
                            pfx = '__'
                        except:
                            w = l._coro.cr_frame.f_locals['self']
                            pfx = ''
                        if not w._is_worker:
                            raise ValueError
                        n = w._name
                        worker = pfx + (n[19:] if n.startswith(
                            '_background_worker_') else n)
                    except:
                        worker = ''
                    result.append(
                        (loop_name, l._state, coro, fname, cmd, worker))
            except:
                import sys
                e = sys.exc_info()
                coro = '{}: {}'.format(e[0].__name__, str(e[1]))
                result.append((loop_name, '!ERROR', coro, '', '', ''))
    elif cmd == 'workers':
        import asyncio
        for worker_name, worker in g.task_supervisor.get_schedulers().items():
            try:
                name = worker_name[19:] if worker_name.startswith(
                    '_background_worker_') else worker_name
            except:
                name = ''
            try:
                wc = '{}{}'.format(
                    (worker.__module__ +
                     '.') if worker.__module__ != 'neotaskr.workers' else '',
                    worker.__class__.__name__)
            except:
                wc = None
            try:
                active = worker.is_active()
            except:
                active = None
            try:
                interval = worker.delay
                if worker.keep_interval:
                    iflags = 'I'
                else:
                    iflags = 'D'
            except:
                interval = 0
                iflags = None
            try:
                etype = 0 if worker._target_is_async else 1
            except:
                etype = None
            try:
                if not worker.worker_loop:
                    aloop = False
                elif worker.aloop:
                    aloop = worker.aloop.name
                else:
                    aloop = '<' + worker.worker_loop.__class__.__name__ + '>'
            except:
                aloop = None
            result.append((name, wc, active, interval, iflags, aloop, etype))
    return g.task_supervisor.get_info(
        aloops=False, schedulers=False,
        async_job_schedulers=False).__dict__, result
