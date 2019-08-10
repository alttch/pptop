__author__ = "Altertech Group, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech Group"
__license__ = "MIT"
__version__ = "0.0.1"

import curses
import atasker
import logging
import socket
import struct
import pickle
import yaml
import inspect
import threading
import psutil
import os
import importlib

from types import SimpleNamespace

logging.getLogger('asyncio').setLevel(logging.CRITICAL)

work_pid = None

config = {}
plugins = {}

bottom_bar_help = {10: 'Quit'}
plugin_shortcuts = {}


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


def command(cmd, data=None):
    with client_lock:
        try:
            frame = cmd.encode()
            if data is not None:
                frame += b'\xff' + pickle.dumps(data)
            client.sendall(struct.pack('I', len(frame)) + frame)
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


def get_process():
    return _d.process


def get_process_path():
    return _d.process_path


@atasker.background_worker(delay=1)
def show_process_info(stdscr, p, **kwargs):

    def error(txt):
        stdscr.clear()
        stdscr.addstr(0, 0, str(txt), curses.color_pair(2) | curses.A_BOLD)
        stdscr.refresh()
        return False

    height, width = stdscr.getmaxyx()
    with scr_lock:
        try:
            result = command('test')
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
            print_bottom_bar(stdscr)
            stdscr.refresh()
        except psutil.AccessDenied:
            return error('Access denied')
        except psutil.NoSuchProcess:
            return error('Process is gone')
        except RuntimeError:
            return error('Process server is gone')
        except Exception as e:
            return error(e)


def print_bottom_bar(stdscr):
    height, width = stdscr.getmaxyx()
    stdscr.move(height - 1, 0)
    stdscr.addstr(' ' * (width - 1), curses.color_pair(7) | curses.A_REVERSE)
    stdscr.move(height - 1, 0)
    for h in sorted(bottom_bar_help):
        stdscr.addstr('F{}'.format(h))
        stdscr.addstr(bottom_bar_help[h].ljust(6),
                      curses.color_pair(7) | curses.A_REVERSE)
    return


_d = SimpleNamespace(
    current_plugin=None, process_path=[], default_plugin=None, process=None)

_cursors = SimpleNamespace(
    files_cursor=0,
    files_shift=0,
    threads_cursor=0,
    threads_shift=0,
    profiler_cursor=0,
    profiler_shift=0)


def run(stdscr):

    def switch_plugin(new_plugin, stdscr):
        if _d.current_plugin:
            if _d.current_plugin is new_plugin:
                return
            _d.current_plugin['p'].stop(wait=False)
        p = new_plugin['p']
        p.stdscr = stdscr
        p.key_event = None
        if not new_plugin['inj']:
            command('inject', new_plugin['i'])
            new_plugin['inj'] = True
        p.start()
        _d.current_plugin = new_plugin

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

    _d.process = p

    client.settimeout(5)
    try:
        client.connect('/tmp/.pptop_777')
    except:
        raise RuntimeError('Unable to connect to process')

    _d.process_path = pickle.loads(command('path'))

    try:
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        stdscr.refresh()
        curses.curs_set(0)
        switch_plugin(_d.default_plugin, stdscr)
        atasker.background_task(show_process_info.start)(stdscr=stdscr, p=p)
        while True:
            try:
                k = stdscr.getkey()
                if not show_process_info.is_active():
                    return
                elif k in plugin_shortcuts:
                    switch_plugin(plugin_shortcuts[k], stdscr)
                elif k in ['q', 'KEY_F(10)']:
                    return
                else:
                    with scr_lock:
                        _d.current_plugin['p'].key_event = k
                        _d.current_plugin['p'].trigger()
            except:
                return
    finally:
        try:
            command('bye')
        except:
            pass
        try:
            client.close()
        except:
            pass


def start():
    config.clear()
    with open('pptop.yml') as fh:
        config.update(yaml.load(fh.read()))

    plugins.clear()
    for i, v in config.get('plugins', {}).items():
        try:
            mod = importlib.import_module('pptop.plugins.' + i)
        except:
            mod = importlib.import_module('pptopcontrib.' + i)
        plugin = {'m': mod}
        plugins[i] = plugin
        p = mod.Plugin(interval=v.get('interval', 1))
        p.command = command
        p.scr_lock = scr_lock
        p.get_process = get_process
        p.get_process_path = get_process_path
        plugin['p'] = p
        injection = {'id': i}
        need_inject = False
        try:
            injection['l'] = inspect.getsource(mod.injection_load)
            need_inject = True
        except:
            pass
        try:
            injection['i'] = inspect.getsource(mod.injection)
            need_inject = True
        except:
            pass
        try:
            injection['u'] = inspect.getsource(mod.injection_unload)
            need_inject = True
        except:
            pass
        if need_inject:
            plugin['inj'] = False
            plugin['i'] = injection
        else:
            plugin['inj'] = True
        if not _d.default_plugin or v.get('default'):
            _d.default_plugin = plugin
        p.on_load()
        if 'shortcut' in v:
            sh = v['shortcut']
            plugin_shortcuts[sh] = plugin
            if sh.startswith('KEY_F('):
                try:
                    bottom_bar_help[int(sh[6:-1])] = p.short_name
                except:
                    raise
                    pass
    atasker.task_supervisor.start()
    try:
        curses.wrapper(run)
    except Exception as e:
        raise
        print(e)
    for p, v in plugins.items():
        v['p'].on_unload()
    atasker.task_supervisor.stop(wait=False)
