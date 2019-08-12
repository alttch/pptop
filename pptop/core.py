'''
Global shortcuts:

    Arrow keys  : Navigation
    f, /        : Filter data
    p           : Pause/resume current plugin
    Alt+arrows  : Sorting
    q, F10      : Quit program

ppTOP v{version} (c) Altertech
The product is available under {license} license.

https://github.com/alttch/pptop
'''

__author__ = "Altertech, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech"
__license__ = "MIT"
__version__ = "0.0.3"

__doc__ = __doc__.format(version=__version__, license=__license__)

import curses
import atasker
import logging
import socket
import struct
import yaml
import inspect
import threading
import psutil
import os
import subprocess
import importlib
import signal
import uuid
import time

try:
    import _pickle as pickle
except:
    import pickle

from types import SimpleNamespace

from pptop import GenericPlugin
from pptop import CriticalException
# DEBUG
from pptop import print_debug

logging.getLogger('asyncio').setLevel(logging.CRITICAL)

work_pid = None

config = {}
plugins = {}

bottom_bar_help = {10: 'Quit'}
plugin_shortcuts = {}

resize_lock = threading.Lock()
resize_event = threading.Event()

editor_active = threading.Event()

socket_timeout = 15

injection_timeout = 3

socket_buf = 1024


def enter_is_terminate(x):
    if x == 10:
        x = 7
    return x


def apply_filter(stdscr, plugin):
    height, width = stdscr.getmaxyx()
    with scr_lock:
        try:
            editor_active.set()
            stdscr.addstr(4, 1, 'f: ')
            editwin = curses.newwin(1, width - 3, 4, 4)
            from curses.textpad import Textbox
            curses.curs_set(2)
            editwin.addstr(0, 0, plugin.filter)
            box = Textbox(editwin)
            stdscr.refresh()
            box.edit(enter_is_terminate)
            plugin.filter = box.gather().strip().lower()
            curses.curs_set(0)
            stdscr.move(4, 0)
            stdscr.clrtoeol()
            stdscr.refresh()
            plugin.trigger()
        finally:
            editor_active.clear()


def select_process(stdscr):

    class ProcesSelector(GenericPlugin):

        def load_data(self):
            self.data.clear()
            for p in psutil.process_iter():
                name = p.name()
                if name in ['python', 'python3'] and p.pid != os.getpid():
                    self.data.append({
                        'pid': p.pid,
                        'command line': ' '.join(p.cmdline())
                    })

        def render(self, dtd):
            super().render(dtd)
            self.stdscr.move(self.stdscr.getmaxyx()[0] - 1, 0)
            self.stdscr.clrtoeol()

        async def run(self, *args, **kwargs):
            super().run(*args, **kwargs)

    with scr_lock:
        stdscr.clear()
        curses.curs_set(0)
    selector = ProcesSelector(interval=1)
    selector.events = 0
    selector.stdscr = stdscr
    selector.sorting_rev = False
    selector.selectable = True
    selector.scr_lock = scr_lock
    selector.finish_event = threading.Event()
    selector.key_event = None
    selector.lock = threading.Lock()
    selector.title = 'Select process'
    selector.start()
    selector.show()
    while True:
        try:
            try:
                if resize_event.is_set():
                    raise Exception('resize')
                k = stdscr.getkey()
                if len(k) == 1:
                    if ord(k) == 6:
                        k = 'KEY_NPAGE'
                    elif ord(k) == 2:
                        k = 'KEY_PPAGE'
            except KeyboardInterrupt:
                return
            except:
                with resize_lock:
                    if resize_event.is_set():
                        resize_event.clear()
                        resize_handler(stdscr)
                        selector.resize()
                continue
            if k in ['q', 'KEY_F(10)']:
                selector.stop(wait=False)
                return
            elif k in ('f', '/'):
                apply_filter(stdscr, selector)
            elif k == '\n':
                selector.stop(wait=False)
                if not selector.dtd:
                    return None
                return psutil.Process(selector.dtd[selector.cursor]['pid'])
            else:
                with scr_lock:
                    selector.key_event = k
                    selector.trigger()
        except:
            raise
            return

    return


scr_lock = threading.Lock()
client_lock = threading.Lock()

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)


def command(cmd, params=None):
    with client_lock:
        _d.client_frame_id += 1
        try:
            frame = cmd.encode()
            if params is not None:
                frame += b'\xff' + pickle.dumps(params)
            client.sendall(
                struct.pack('I', len(frame)) +
                struct.pack('I', _d.client_frame_id) + frame)
            time_start = time.time()
            data = client.recv(4)
            frame_id = struct.unpack('I', client.recv(4))[0]
        except:
            raise CriticalException('Injector is gone')
        if not data:
            raise CriticalException('Injector error')
        l = struct.unpack('I', data)[0]
        data = b''
        while len(data) != l:
            data += client.recv(socket_buf)
            if time.time() > time_start + socket_timeout:
                raise CriticalException('Socket timeout')
        if frame_id != _d.client_frame_id:
            raise CriticalException('Wrong frame')
        _d.last_frame_id += 1
        if data[0] != 0:
            raise RuntimeError('Injector command error')
        return pickle.loads(data[1:]) if len(data) > 1 else True


def get_process():
    return _d.process


def get_process_path():
    return _d.process_path


@atasker.background_worker(delay=1)
async def show_process_info(stdscr, p, **kwargs):

    def error(txt):
        stdscr.clear()
        stdscr.addstr(0, 0, str(txt), curses.color_pair(2) | curses.A_BOLD)
        stdscr.refresh()
        return False

    height, width = stdscr.getmaxyx()
    try:
        with scr_lock:
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
    except psutil.AccessDenied:
        return error('Access denied')
    except psutil.NoSuchProcess:
        return error('Process is gone')
    except RuntimeError:
        return error('Process server is gone')
    except curses.error:
        try:
            for i in range(2):
                stdscr.move(i, 0)
                stdscr.clrtoeol()
            stdscr.refresh()
        except:
            pass
    except Exception as e:
        return error(e)


@atasker.background_worker(delay=0.1)
def show_bottom_bar(stdscr, **kwargs):
    with scr_lock:
        height, width = stdscr.getmaxyx()
        stdscr.move(height - 1, 0)
        stdscr.addstr(' ' * (width - 1), curses.color_pair(7) | curses.A_REVERSE)
        stdscr.move(height - 1, 0)
        color = curses.color_pair(7) | curses.A_REVERSE
        for h in sorted(bottom_bar_help):
            stdscr.addstr('F{}'.format(h))
            stdscr.addstr(bottom_bar_help[h].ljust(6), color)
        stats = '⇄ {}/{} '.format(_d.client_frame_id, _d.last_frame_id)
        stdscr.addstr(height - 1, width - len(stats) - 1, stats, color)
        stdscr.refresh()
    return


_d = SimpleNamespace(
    current_plugin=None,
    process_path=[],
    default_plugin=None,
    process=None,
    stdscr=None,
    client_frame_id=0,
    last_frame_id=0)

_cursors = SimpleNamespace(
    files_cursor=0,
    files_shift=0,
    threads_cursor=0,
    threads_shift=0,
    profiler_cursor=0,
    profiler_shift=0)


def sigwinch_handler(signum=None, frame=None):
    with resize_lock:
        resize_event.set()


def resize_handler(stdscr):
    # shutil works in 100% cases
    import shutil
    width, height = shutil.get_terminal_size()
    with scr_lock:
        curses.resizeterm(height, width)
        stdscr.resize(height, width)
        stdscr.clear()
        stdscr.refresh()


def inject_client(pid):
    cmds = [
        '(PyGILState_STATE)PyGILState_Ensure()',
        ('(int)PyRun_SimpleString("import sys;sys.path.append(\\"{path}\\");' +
         'import pptop.injection;pptop.injection.start({mypid})")').format(
             path=os.path.abspath(os.path.dirname(__file__) + '/..'),
             mypid=os.getpid()), '(void)PyGILState_Release($1)'
    ]
    gdb_cmd = 'gdb -p {pid} --batch {cmds}'.format(
        pid=pid,
        cmds=' '.join(["--eval-command='call {}'".format(c) for c in cmds]))
    p = subprocess.Popen(
        gdb_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode:
        raise RuntimeError(err)


def run(stdscr):

    def switch_plugin(new_plugin, stdscr):
        if _d.current_plugin:
            if _d.current_plugin is new_plugin:
                return
            if not _d.current_plugin['p'].background:
                _d.current_plugin['p'].stop(wait=False)
            else:
                _d.current_plugin['p'].hide()
        p = new_plugin['p']
        p.stdscr = stdscr
        p._previous_plugin = _d.current_plugin
        p.key_event = None
        if not new_plugin['inj']:
            command('inject', new_plugin['i'])
            new_plugin['inj'] = True
        if not p.is_active(): p.start()
        p.show()
        _d.current_plugin = new_plugin

    signal.signal(signal.SIGWINCH, sigwinch_handler)
    _d.stdscr = stdscr

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

    client.settimeout(socket_timeout)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, socket_buf)
    client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, socket_buf)
    inject_client(p.pid)
    sock_path = '/tmp/.pptop.{}'.format(os.getpid())
    for i in range(injection_timeout * 10):
        if os.path.exists(sock_path):
            break
        time.sleep(0.1)
    try:
        client.connect(sock_path)
    except:
        raise RuntimeError('Unable to connect to process')

    _d.process_path.clear()
    for i in command('path'):
        _d.process_path.append(os.path.abspath(i))

    height, width = stdscr.getmaxyx()
    stdscr.clear()
    stdscr.refresh()
    curses.curs_set(0)
    switch_plugin(_d.default_plugin, stdscr)
    atasker.background_task(show_process_info.start)(stdscr=stdscr, p=p)
    atasker.background_task(show_bottom_bar.start)(stdscr=stdscr)
    while True:
        try:
            try:
                if resize_event.is_set():
                    raise Exception('resize')
                k = stdscr.getkey()
                if len(k) == 1:
                    if ord(k) == 6:
                        k = 'KEY_NPAGE'
                    elif ord(k) == 2:
                        k = 'KEY_PPAGE'
            except KeyboardInterrupt:
                return
            except:
                with resize_lock:
                    if resize_event.is_set():
                        resize_event.clear()
                        resize_handler(stdscr)
                        _d.current_plugin['p'].resize()
                        show_process_info.trigger()
                continue
            if not show_process_info.is_active():
                return
            elif k in plugin_shortcuts:
                switch_plugin(plugin_shortcuts[k], stdscr)
            elif k in ['q', 'KEY_F(10)']:
                _d.current_plugin['p'].stop(wait=False)
                show_process_info.stop(wait=False)
                show_bottom_bar.stop(wait=False)
                return
            elif k in ('f', '/'):
                apply_filter(stdscr, _d.current_plugin['p'])
            elif k == 'p':
                _d.current_plugin['p'].toggle_pause()
            else:
                with scr_lock:
                    _d.current_plugin['p'].key_event = k
                    _d.current_plugin['p'].trigger()
        except:
            return


def start():
    config.clear()
    with open('pptop.yml') as fh:
        config.update(yaml.load(fh.read()))

    with open('/proc/sys/kernel/yama/ptrace_scope') as fd:
        yps = int(fd.read().strip())

    if yps:
        raise Exception(
            'yama ptrace scope is on. ' +
            'disable with "sudo sysctl -w kernel.yama.ptrace_scope=0"')

    plugins.clear()
    for i, v in config.get('plugins', {}).items():
        try:
            mod = importlib.import_module('pptop.plugins.' + i)
        except ModuleNotFoundError:
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
        for p, v in plugins.items():
            v['p'].on_unload()
    except Exception as e:
        raise
        print(e)
    finally:
        try:
            command('bye')
        except:
            pass
        try:
            client.close()
        except:
            pass
    atasker.task_supervisor.stop(wait=False)
