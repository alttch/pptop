from pptop.plugin import GenericPlugin, palette

import os
import time

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    atasker plugin: monitor atasker supervisor

    config.task_supervisor: task supervisor object (default:
    atasker::task_supervisor)

    requires: Python 3.5+

    Shortcuts:

        a      : async loops
        w      : schedulers(workers)
        t      : tasks

    https://github.com/alttch/atasker
    '''

    def on_load(self):
        self.orig_title = 'atasker monitor'
        self.short_name = 'ATaskr'
        self.sorting_rev = False
        self.background_loader = True
        self.need_status_line = True
        self.mode = 'loops'
        self.supervisor_status = None
        self.mode_shortcuts = {
            'a': 'loops',
            'w': 'workers',
            't': 'tasks',
        }
        self.mode_sorting = {}
        self.set_title()
        self.task_priorities = {
            0: 'CRITICAL',
            50: 'HIGH',
            100: 'NORMAL',
            200: 'LOW'
        }
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

    def render_status_line(self):
        s = self.supervisor_status
        if s:
            if s['active']:
                self.status_line.addstr('ON ', palette.OK)
            else:
                self.status_line.addstr('OFF', palette.GREY_BOLD)
            self.status_line.addstr(' T: ')
            self.status_line.addstr(str(s['thread_tasks_count']),
                                    palette.MAGENTA)
            self.status_line.addstr(' ({}/+{}/+{})'.format(
                s['thread_pool_size'], s['thread_reserve_normal'],
                s['thread_reserve_high']))
            if 'mp_pool_size' in s:
                self.status_line.addstr(', MP: ')
                self.status_line.addstr(str(s['mp_tasks_count']),
                                        palette.BLUE_BOLD)
                self.status_line.addstr(' ({}/+{}/+{})'.format(
                    s['mp_pool_size'], s['mp_reserve_normal'],
                    s['mp_reserve_high']))

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
                v['priority'] = d[6]
                v['int'] = d[3]
                v['inf'] = d[4] if d[4] else ''
                v['executor'] = d[8]
                if d[7] is False:
                    v['aloop'] = '__supervisor__'
                elif d[7]:
                    v['aloop'] = d[7]
                else:
                    v['aloop'] = ''
                v['daemon'] = 'daemon' if d[5] and d[8] == 1 else ''
            elif self.mode == 'tasks':
                v['id'] = d[0]
                v['type'] = d[6]
                v['priority'] = d[1]
                v['status'] = d[2]
                v['worker'] = d[7] if d[7] else ''
                v['wclass'] = d[8] if d[8] else ''
                v['queued'] = d[4] if d[4] else 0
                v['started'] = d[5] if d[5] else 0
                v['qtime'] = (time.time() -
                              v['queued']) if not d[5] else (d[5] - d[4])
                v['task'] = d[3]
            result.append(v)
        return result

    def format_dtd(self, dtd):
        for d in dtd:
            if self.mode == 'loops':
                yield d
            elif self.mode == 'workers':
                z = d.copy()
                z['priority'] = self.task_priorities.get(z['priority'])
                z['executor'] = self.task_types.get(z['executor'])
                if z.get('int') == 0:
                    z['int'] = ''
                else:
                    z['int'] = str(z.get('int'))
                yield z
            elif self.mode == 'tasks':
                from datetime import datetime
                z = d.copy()
                z['type'] = self.task_types.get(z['type'])
                z['priority'] = self.task_priorities.get(z['priority'])
                z['status'] = self.task_status.get(z['status'])
                z['queued'] = None if not z[
                    'queued'] else datetime.fromtimestamp(
                        z['queued']).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                z['started'] = None if not z[
                    'started'] else datetime.fromtimestamp(
                        z['started']).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                z['qtime'] = '{:.3f}'.format(z['qtime'])
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
            elif key == 'executor':
                if value == 'CORO':
                    return palette.GREEN
                elif value == 'THREAD':
                    return palette.MAGENTA
                elif value == 'MP':
                    return palette.BLUE_BOLD
            elif key == 'aloop':
                return palette.YELLOW if \
                        value != '__supervisor__' else palette.RED_BOLD
        elif self.mode == 'tasks':
            if element['status'] == 'QUEUED':
                return palette.GREY_BOLD
            elif element['status'] == 'CANCELED':
                return palette.GREY
            elif key == 'id':
                return palette.YELLOW
            elif key == 'type':
                if value == 'CORO':
                    return palette.GREEN
                elif value == 'THREAD':
                    return palette.MAGENTA
                elif value == 'MP':
                    return palette.BLUE_BOLD
            elif key == 'priority':
                if value == 'CRITICAL':
                    return palette.RED_BOLD
                elif value == 'HIGH':
                    return palette.YELLOW
                elif value == 'LOW':
                    return palette.GREY_BOLD
                else:
                    return
            elif key == 'status':
                return palette.OK
            elif key == 'worker':
                return palette.CYAN
            elif key == 'wclass':
                return palette.BOLD
            elif key == 'queued':
                return palette.GREY_BOLD
            elif key == 'started':
                return palette.GREEN
            elif key == 'qtime':
                return palette.GREY_BOLD

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
    result = []
    if cmd == 'loops':
        import linecache
        import asyncio
        loops = {('__supervisor__', g.task_supervisor.event_loop)}
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
                        n = w.name
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
        for worker in g.task_supervisor.get_schedulers():
            try:
                name = worker.name[19:] if worker.name.startswith(
                    '_background_worker_') else worker.name
            except:
                name = ''
            try:
                wc = '{}{}'.format(
                    (worker.__module__ +
                     '.') if worker.__module__ != 'atasker.workers' else '',
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
                if worker.delay_before:
                    iflags += ',B=' + str(worker.delay_before)
            except:
                interval = 0
                iflags = None
            try:
                daemon = worker.daemon
            except:
                daemon = False
            try:
                priority = worker.priority
            except:
                priority = None
            try:
                if asyncio.iscoroutinefunction(worker.run):
                    etype = 0
                elif worker._run_in_mp:
                    etype = 2
                else:
                    etype = 1
            except:
                etype = None
            try:
                if not worker.executor_loop:
                    aloop = False
                elif worker.aloop:
                    aloop = worker.aloop.name
                else:
                    aloop = '<' + worker.executor_loop.__class__.__name__ + '>'
            except:
                aloop = None
            result.append((name, wc, active, interval, iflags, daemon, priority,
                           aloop, etype))
    elif cmd == 'tasks':
        for task_id, task in g.task_supervisor.get_tasks().items():
            if task.worker:
                wc = '{}{}'.format(
                    (task.worker.__module__ + '.')
                    if task.worker.__module__ != 'atasker.workers' else '',
                    task.worker.__class__.__name__)
                wname = task.worker.name[19:] if task.worker.name.startswith(
                    '_background_worker_') else task.worker.name
            else:
                wc = None
                wname = None
            try:
                target = str(task.target)
            except:
                target = str(task.task)
            result.append(
                (task_id, task.priority, task.status, target, task.time_queued,
                 task.time_started, task.tt, wname, wc))
    return g.task_supervisor.get_info(
        tt=False, aloops=False, schedulers=False,
        async_job_schedulers=False).__dict__, result
