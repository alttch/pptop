#!/usr/bin/env python3

__author__ = "Altertech Group, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech Group"
__license__ = "MIT"
__version__ = "0.0.1"

import psutil
import os
import re
import time
import tabulate
import curses
import atasker
import threading
import logging
import socket
import struct
import pickle
import pyinstrument

from types import SimpleNamespace

logging.getLogger('asyncio').setLevel(logging.CRITICAL)

ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')

work_pid = None

profiler = pyinstrument.Profiler()


def select_process(stdscr):
    processes = []
    for p in psutil.process_iter():
        name = p.name()
        if name in ['python', 'python3'] and p.pid != os.getpid():
            processes.append(p)
    if not processes:
        raise Exception('No processed found')
    stdscr.clear()
    curses.curs_set(0)
    if curses.can_change_color():
        curses.init_color(0, 0, 0, 0)
    height, width = stdscr.getmaxyx()
    stdscr.addstr(0, 0, 'Select process', curses.color_pair(4) | curses.A_BOLD)
    stdscr.addstr(1, 0, '-' * width, curses.color_pair(9))
    index = 0
    while True:
        i = 0
        for p in processes:
            try:
                line = '{} {:<7} {}'.format('>' if index == i else ' ', p.pid,
                                            ' '.join(p.cmdline()))
                stdscr.addstr(
                    i + 3, 0, '{}'.format(line[:width]), curses.A_REVERSE
                    if i == index else curses.A_NORMAL)
                i += 1
            except:
                break

        stdscr.refresh()
        try:
            k = stdscr.getkey()
            if k == 'KEY_DOWN':
                index += 1
                if index > len(processes) - 1: index = 0
            elif k == 'KEY_UP':
                index -= 1
                if index < 0: index = len(processes) - 1
            elif k == 'q':
                return
            elif k == '\n':
                return processes[index]
        except:
            return


scr_lock = threading.Lock()
client_lock = threading.Lock()

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)


def client_command(cmd):
    with client_lock:
        try:
            client.sendall(struct.pack('I', len(cmd)) + cmd.encode())
            data = client.recv(4)
        except:
            raise RuntimeError('Injector is gone')
        if not data:
            raise RuntimeError('Injector error')
        l = struct.unpack('I', data)
        data = client.recv(l[0])
        if data[0] != 0:
            raise RuntimeError('Injector command error')
        return data[1:]


@atasker.background_worker(delay=1)
def show_process_info(stdscr, p, **kwargs):
    height, width = stdscr.getmaxyx()
    with scr_lock:
        try:
            result = client_command('test')
            ct = p.cpu_times()
            stdscr.move(0, 0)
            stdscr.addstr('Process: ')
            cmdline = ' '.join(p.cmdline())[:width - 20]
            stdscr.addstr(cmdline, curses.color_pair(4))
            stdscr.addstr(' [')
            stdscr.addstr(str(p.pid), curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(']')
            stdscr.addstr('\nCPU: ')
            stdscr.addstr('{}%'.format(p.cpu_percent()),
                          curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(', user: ')
            stdscr.addstr(str(ct.user), curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(', system: ')
            stdscr.addstr(str(ct.system), curses.color_pair(5) | curses.A_BOLD)
            stdscr.addstr(', threads: ')
            stdscr.addstr(
                str(p.num_threads()),
                curses.color_pair(3) | curses.A_BOLD)
            stdscr.addstr(', files: ')
            stdscr.addstr(
                str(len(p.open_files())),
                curses.color_pair(3) | curses.A_BOLD)
            stdscr.clrtoeol()
            stdscr.refresh()
        except psutil.NoSuchProcess:
            stdscr.clear()
            stdscr.addstr(0, 0, 'Process is gone', curses.color_pair(2))
            stdscr.refresh()
            return False
        except RuntimeError:
            stdscr.clear()
            stdscr.addstr(0, 0, 'Process server is gone', curses.color_pair(2))
            stdscr.refresh()
            return False


def print_section_title(stdscr, title):
    height, width = stdscr.getmaxyx()
    stdscr.addstr(3, 0, ' ' + title.ljust(width - 1),
                  curses.color_pair(4) | curses.A_BOLD)


def fancy_tabulate(stdscr, table, cursor=None):
    height, width = stdscr.getmaxyx()
    if table:
        d = tabulate.tabulate(table, headers='keys').split('\n')
        stdscr.addstr(4, 0, d[0].ljust(width)[:width - 1],
                      curses.color_pair(3) | curses.A_REVERSE)
        for i, t in enumerate(d[2:]):
            stdscr.addstr(
                5 + i, 0,
                t.ljust(width)[:width - 1],
                curses.color_pair(7) | curses.A_REVERSE
                if cursor == i else curses.A_NORMAL)
    else:
        stdscr.addstr(4, 0, ' ' * (width - 1),
                      curses.color_pair(3) | curses.A_REVERSE)
    stdscr.clrtobot()


def print_bottom_bar(stdscr):
    hlp = {'F5': 'Prof', 'F6': 'Files', 'F7': 'Thrds', 'F10': 'Quit'}
    height, width = stdscr.getmaxyx()
    stdscr.move(height - 1, 0)
    stdscr.addstr(' ' * (width - 1), curses.color_pair(7) | curses.A_REVERSE)
    stdscr.move(height - 1, 0)
    for h, t in hlp.items():
        stdscr.addstr(h)
        stdscr.addstr(t.ljust(6), curses.color_pair(7) | curses.A_REVERSE)
    return


reserved_lines = 6


def handle_pager_event(stdscr, cursor_id, max_pos):
    height, width = stdscr.getmaxyx()
    crs = getattr(_cursors, cursor_id + '_cursor')
    shf = getattr(_cursors, cursor_id + '_shift')
    if _d.key_event:
        if _d.key_event == 'KEY_DOWN':
            crs += 1
            if crs > max_pos:
                crs = max_pos
            if crs - shf >= height - reserved_lines:
                shf += 1
        elif _d.key_event == 'KEY_UP':
            crs -= 1
        elif _d.key_event == 'KEY_NPAGE':
            crs += height - reserved_lines
            shf += height - reserved_lines
        elif _d.key_event == 'KEY_PPAGE':
            crs -= height - reserved_lines
            shf -= height - reserved_lines
        elif _d.key_event == 'KEY_HOME':
            crs = 0
            shf = 0
        elif _d.key_event == 'KEY_END':
            crs = max_pos
            shf = max_pos - height + reserved_lines + 1
        if crs < 0:
            shf -= 1
            crs = 0
        if crs - shf < 0:
            crs = shf - 1
            shf -= 1
        if shf < 0:
            shf = 0
    if max_pos <= height - reserved_lines + 1:
        shf = 0
    if crs > max_pos:
        crs = max_pos
        shf = max_pos - height + reserved_lines + 1
        if shf < 0:
            shf = 0
    setattr(_cursors, cursor_id + '_cursor', crs)
    setattr(_cursors, cursor_id + '_shift', shf)


def ansi_to_plain(txt):
    return ansi_escape.sub('', txt)


def print_ansi_str(stdscr, txt):
    stdscr.addstr(ansi_to_plain(txt))
    stdscr.clrtoeol()


def print_empty_sep(stdscr):
    height, width = stdscr.getmaxyx()
    stdscr.addstr(4, 0, ' ' * (width - 1),
                  curses.color_pair(3) | curses.A_REVERSE)


def format_mod_name(f, path):
    for p in path:
        if f.startswith(p):
            f = f[len(p) + 1:]
            break
    if f.endswith('.py'):
        f = f[:-3]
    return f.replace('/', '.')


@atasker.background_worker(delay=1)
def show_function_profiler(stdscr, p, **kwargs):
    height, width = stdscr.getmaxyx()
    try:
        data = pickle.loads(client_command('profiler'))
    except:
        return False
    sess = []
    for s in data:
        sess.append({
            'function':
            '{}.{}'.format(format_mod_name(s[1], _d.client_path), s[0]),
            'ncall':
            s[3],
            'nacall':
            s[4],
            'ttot':
            s[6],
            'tsub':
            s[7],
            'tavg':
            s[11],
            'file':
            '{}:{}'.format(s[1], s[2]),
            'bultin':
            s[5]
        })
    sess = sorted(sess, key=lambda k: k['ttot'], reverse=True)
    ks = ['ttot', 'tsub', 'tavg']
    for s in sess:
        for k in ks:
            s[k] = '{:.3f}'.format(s[k])
    with scr_lock:
        print_section_title(stdscr, 'Function profiler')
        handle_pager_event(stdscr, 'profiler', len(sess) - 1)
        if _d.key_event:
            _d.key_event = None
        fancy_tabulate(
            stdscr,
            sess[_cursors.profiler_shift:_cursors.profiler_shift + height -
                 reserved_lines],
            cursor=_cursors.profiler_cursor - _cursors.profiler_shift)
        print_bottom_bar(stdscr)
        stdscr.refresh()


@atasker.background_worker(delay=1)
def show_open_files(stdscr, p, **kwargs):
    try:
        height, width = stdscr.getmaxyx()
        files = []
        for f in p.open_files():
            files.append({
                'path': f.path,
                'fd': f.fd,
                'pos.': f.position,
                'mode': f.mode
            })
        files = sorted(files, key=lambda k: k['path'])
        with scr_lock:
            print_section_title(stdscr, 'Open files')
            handle_pager_event(stdscr, 'files', len(files) - 1)
            if _d.key_event:
                _d.key_event = None
            fancy_tabulate(
                stdscr,
                files[_cursors.files_shift:_cursors.files_shift + height -
                      reserved_lines],
                cursor=_cursors.files_cursor - _cursors.files_shift)
            print_bottom_bar(stdscr)
            stdscr.refresh()
    except:
        return False


@atasker.background_worker(delay=1)
def show_threads(stdscr, p, **kwargs):
    height, width = stdscr.getmaxyx()
    try:
        threads = pickle.loads(client_command('threads'))
    except:
        return False
    threads = sorted(threads, key=lambda k: k['ttot'], reverse=True)
    for t in threads:
        t['ttot'] = '{:.3f}'.format(t['ttot'])
    with scr_lock:
        print_section_title(stdscr, 'Threads')
        handle_pager_event(stdscr, 'threads', len(threads) - 1)
        if _d.key_event:
            _d.key_event = None
        fancy_tabulate(
            stdscr,
            threads[_cursors.threads_shift:_cursors.threads_shift + height -
                    reserved_lines],
            cursor=_cursors.threads_cursor - _cursors.threads_shift)
        print_bottom_bar(stdscr)
        stdscr.refresh()


_d = SimpleNamespace(current_worker=None, key_event=None, client_path=[])

_cursors = SimpleNamespace(
    files_cursor=0,
    files_shift=0,
    threads_cursor=0,
    threads_shift=0,
    profiler_cursor=0,
    profiler_shift=0)

default_page = show_function_profiler


def pptop(stdscr):

    def switch_worker(new_worker):
        if _d.current_worker:
            _d.current_worker.stop()
        _d.current_worker = new_worker
        _d.current_worker.start(stdscr, p)

    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
    for i in range(0, curses.COLORS):
        curses.init_pair(i + 1, i, -1)
    if not work_pid:
        p = select_process(stdscr)
    else:
        p = psutil.Process(work_pid)
    if not p: return

    client.settimeout(5)
    try:
        client.connect('/tmp/.pptop_777')
    except:
        raise RuntimeError('Unable to connect to process')

    _d.client_path = pickle.loads(client_command('path'))

    try:
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        curses.curs_set(0)
        switch_worker(default_page)
        atasker.background_task(show_process_info.start)(stdscr=stdscr, p=p)
        worker_shortcuts = {
            'KEY_F(5)': show_function_profiler,
            'KEY_F(6)': show_open_files,
            'KEY_F(7)': show_threads
        }
        while True:
            try:
                k = stdscr.getkey()
                if not show_process_info.is_active() or k in ['q', 'KEY_F(10)']:
                    return
                elif k in worker_shortcuts:
                    switch_worker(worker_shortcuts[k])
                else:
                    with scr_lock:
                        _d.key_event = k
                        _d.current_worker.trigger()
            except:
                return
    finally:
        try:
            client_command('bye')
        except:
            pass
        try:
            client.close()
        except:
            pass


def main():
    atasker.task_supervisor.start()
    # work_pid = 114958
    try:
        curses.wrapper(pptop)
    except Exception as e:
        print(e)
    atasker.task_supervisor.stop(wait=False)


if __name__ == '__main__':
    main()
