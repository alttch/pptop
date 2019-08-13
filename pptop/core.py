'''
Global shortcuts:

    Arrow keys  : Navigation
    f, /        : Filter data
    p           : Pause/resume current plugin
    Alt+arrows  : Sorting
    Space       : Instant data reload
    C-L         : Send ready event
    q, F10      : Quit program

ppTOP v{version} (c) Altertech
The product is available under {license} license.

https://github.com/alttch/pptop
'''

__author__ = "Altertech, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech"
__license__ = "MIT"
__version__ = "0.0.14"

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
import sys
import subprocess
import importlib
import signal
import uuid
import time
import pickle
import shutil
import argparse
import collections

try:
    yaml.warnings({'YAMLLoadWarning': False})
except:
    pass

from types import SimpleNamespace

from pptop import GenericPlugin
from pptop import CriticalException
from pptop import palette
from pptop import prompt
from pptop import print_message
# DEBUG
from pptop import print_debug

logging.getLogger('asyncio').setLevel(logging.CRITICAL)

dir_me = os.path.dirname(os.path.realpath(__file__))

config = {}
plugins = {}

plugins_autostart = []

bottom_bar_help = {10: 'Quit'}
plugin_shortcuts = {}

resize_lock = threading.Lock()
resize_event = threading.Event()

socket_timeout = 15

injection_timeout = 3

socket_buf = 1024


def get_plugins():
    return plugins


def get_config_dir():
    return _d.pptop_dir


def get_plugin(plugin_name):
    return plugins.get(plugin_name)


def apply_filter(stdscr, plugin):
    with scr_lock:
        plugin.filter = prompt(
            stdscr, prompt='f: ', value=plugin.filter).lower()
        plugin.trigger()


def val_to_boolean(s):
    if isinstance(s, bool): return s
    if s is None: return None
    val = str(s)
    if val.lower() in ['1', 'true', 'yes', 'on', 'y']: return True
    if val.lower() in ['0', 'false', 'no', 'off', 'n']: return False
    return None


def dict_merge(dct, merge_dct, add_keys=True):
    dct = dct.copy()
    if not add_keys:
        merge_dct = {
            k: merge_dct[k] for k in set(dct).intersection(set(merge_dct))
        }

    for k, v in merge_dct.items():
        if isinstance(dct.get(k), dict) and isinstance(v, collections.Mapping):
            dct[k] = dict_merge(dct[k], v, add_keys=add_keys)
        else:
            if v is None:
                if not k in dct:
                    dct[k] = None
            else:
                dct[k] = v

    return dct


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


def select_process(stdscr):

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


ifoctets_lock = threading.Lock()
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
        with ifoctets_lock:
            _d.ifoctets += len(data) + 8
            if _d.ifoctets > 1000000000:
                _d.ifoctets = d.ifoctets - 1000000000
        if data[0] != 0:
            raise RuntimeError('Injector command error')
        return pickle.loads(data[1:]) if len(data) > 1 else True


def get_process():
    return _d.process


def get_process_path():
    return _d.process_path


def bytes_to_iso(i):
    numbers = [(1000, 'k'), (1000000, 'M'), (1000000000, 'G'), (1000000000000,
                                                                'T')]
    if i < 1000:
        return '{} B'.format(i)
    for n in numbers:
        if i < n[0] * 1000:
            return '{:.1f} {}B'.format(i / n[0], n[1])
    return '{:.1f} PB'.format(i)


@atasker.background_worker(delay=1, daemon=True)
async def show_process_info(stdscr, p, **kwargs):

    def error(txt):
        stdscr.clear()
        stdscr.addstr(0, 0, str(txt), palette.ERROR)
        stdscr.refresh()
        return False

    height, width = stdscr.getmaxyx()
    try:
        result = command('test')
        with scr_lock:
            with p.oneshot():
                ct = p.cpu_times()
                stdscr.move(0, 0)
                stdscr.addstr('Process: ')
                cmdline = ' '.join(p.cmdline())[:width - 20]
                stdscr.addstr(cmdline, palette.YELLOW)
                stdscr.addstr(' [')
                stdscr.addstr(str(p.pid), palette.GREEN)
                stdscr.addstr(']')
                stdscr.addstr('\nCPU: ')
                stdscr.addstr('{}%'.format(p.cpu_percent()), palette.BLUE_BOLD)
                stdscr.addstr(' user ')
                stdscr.addstr(str(ct.user), palette.BOLD)
                stdscr.addstr(' system ')
                stdscr.addstr(str(ct.system), palette.BOLD)
                stdscr.addstr(', threads: ')
                stdscr.addstr(str(p.num_threads()), palette.MAGENTA_BOLD)
                stdscr.addstr('\nMemory')
                memf = p.memory_full_info()
                for k in ['uss', 'pss', 'swp']:
                    stdscr.addstr(' {}: '.format(k))
                    stdscr.addstr(
                        bytes_to_iso(
                            getattr(memf, 'swap'
                                    if k == 'swp' else k)), palette.BLUE_BOLD)
                mem = p.memory_info()
                for k in ['shared', 'text', 'data']:
                    stdscr.addstr(' {}: '.format(k[0]))
                    stdscr.addstr(bytes_to_iso(getattr(mem, k)), palette.CYAN)
                stdscr.addstr('\nFiles: ')
                stdscr.addstr(str(len(p.open_files())), palette.BLUE_BOLD)
                ioc = p.io_counters()
                stdscr.addstr(' ⇈ {}'.format(ioc.read_count), palette.GREEN)
                stdscr.addstr(' (')
                stdscr.addstr(bytes_to_iso(ioc.read_chars), palette.GREEN)
                stdscr.addstr(')')
                stdscr.addstr(' ⇊ {}'.format(ioc.write_count), palette.BLUE)
                stdscr.addstr(' (')
                stdscr.addstr(bytes_to_iso(ioc.write_chars), palette.BLUE)
                stdscr.addstr(')')
            stdscr.clrtoeol()
            stdscr.refresh()
    except psutil.AccessDenied:
        return error('Access denied')
    except psutil.NoSuchProcess:
        return error('Process is gone')
    except CriticalException:
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


@atasker.background_worker(delay=0.1, daemon=True)
async def show_bottom_bar(stdscr, **kwargs):
    try:
        with scr_lock:
            height, width = stdscr.getmaxyx()
            stdscr.move(height - 1, 0)
            stdscr.addstr(' ' * (width - 1), palette.BAR)
            stdscr.move(height - 1, 0)
            color = palette.BAR
            for h in sorted(bottom_bar_help):
                stdscr.addstr('F{}'.format(h))
                stdscr.addstr(bottom_bar_help[h].ljust(6), color)
            stats = '⇄ {}/{} '.format(_d.client_frame_id, _d.last_frame_id)
            with ifoctets_lock:
                bw = _d.ifbw
            if bw < 1000:
                bws = '{} Bs'.format(bw)
            elif bw < 1000000:
                bws = '{:.0f} kBs'.format(bw / 1000)
            else:
                bws = '{:.0f} MBs'.format(bw / 1000000)
            bws = bws.rjust(7)
            if bw > 2000000:
                bwc = palette.BAR_ERROR
            elif bw > 500000:
                bwc = palette.BAR_WARNING
            else:
                bwc = palette.BAR_OK
            stdscr.addstr(height - 1, width - len(stats) - len(bws) - 1, stats,
                          color)
            stdscr.addstr(bws, bwc)
            stdscr.refresh()
    except:
        pass


@atasker.background_worker(interval=1, daemon=True)
async def calc_bw(**kwargs):
    with ifoctets_lock:
        if _d.ifoctets >= _d.ifoctets_prev:
            _d.ifbw = _d.ifoctets - _d.ifoctets_prev
        else:
            _d.ifbw = 1000000000 - d_.ifoctets_prev + _d.ifoctets
        _d.ifoctets_prev = _d.ifoctets


_d = SimpleNamespace(
    current_plugin=None,
    process_path=[],
    default_plugin=None,
    process=None,
    stdscr=None,
    client_frame_id=0,
    last_frame_id=0,
    ifoctets=0,
    ifoctets_prev=0,
    ifbw=0,
    pptop_dir=None,
    work_pid=None)

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


def init_color_palette():
    palette.DEBUG = curses.color_pair(1) | curses.A_BOLD
    palette.WARNING = curses.color_pair(4) | curses.A_BOLD
    palette.ERROR = curses.color_pair(2) | curses.A_BOLD
    palette.HEADER = curses.color_pair(3) | curses.A_REVERSE
    palette.CURSOR = curses.color_pair(7) | curses.A_REVERSE
    palette.BAR = curses.color_pair(7) | curses.A_REVERSE
    palette.BAR_OK = curses.color_pair(3) | curses.A_REVERSE
    palette.BAR_WARNING = curses.color_pair(4) | curses.A_REVERSE
    palette.BAR_ERROR = curses.color_pair(2) | curses.A_REVERSE
    palette.GREY = curses.color_pair(1)
    palette.GREY_BOLD = curses.color_pair(1) | curses.A_BOLD
    palette.GREEN = curses.color_pair(3)
    palette.GREEN_BOLD = curses.color_pair(3) | curses.A_BOLD
    palette.OK = curses.color_pair(3) | curses.A_BOLD
    palette.BLUE = curses.color_pair(5)
    palette.BLUE_BOLD = curses.color_pair(5) | curses.A_BOLD
    palette.CYAN = curses.color_pair(7)
    palette.CYAN_BOLD = curses.color_pair(7) | curses.A_BOLD
    palette.MAGENTA = curses.color_pair(6)
    palette.MAGENTA_BOLD = curses.color_pair(6) | curses.A_BOLD
    palette.YELLOW = curses.color_pair(4)
    palette.YELLOW_BOLD = curses.color_pair(4) | curses.A_BOLD
    palette.WHITE_BOLD = curses.color_pair(8) | curses.A_BOLD


def switch_plugin(stdscr, new_plugin):
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
        new_plugin['inj'] = True
        command('inject', new_plugin['i'])
    if not p.is_active(): p.start()
    p.show()
    _d.current_plugin = new_plugin


def run(stdscr):

    @atasker.background_task
    def autostart_plugins(stdscr):
        for plugin in plugins_autostart:
            if plugin['p'] is not _d.current_plugin.get('p'):
                if not plugin['inj']:
                    plugin['inj'] = True
                    command('inject', plugin['i'])
                p = plugin['p']
                p.key_event = None
                p.stdscr = stdscr
                p.start()

    signal.signal(signal.SIGWINCH, sigwinch_handler)
    _d.stdscr = stdscr

    if curses.has_colors():
        curses.start_color()
        curses.use_default_colors()
        for i in range(0, curses.COLORS):
            curses.init_pair(i + 1, i, -1)
        init_color_palette()
    if not _d.work_pid:
        p = select_process(stdscr)
    else:
        p = psutil.Process(_d.work_pid)
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

    calc_bw.start()

    _d.process_path.clear()
    for i in command('path'):
        _d.process_path.append(os.path.abspath(i))

    height, width = stdscr.getmaxyx()
    stdscr.clear()
    stdscr.refresh()
    curses.curs_set(0)
    switch_plugin(stdscr, _d.default_plugin)
    atasker.background_task(show_process_info.start)(stdscr=stdscr, p=p)
    atasker.background_task(show_bottom_bar.start)(stdscr=stdscr)
    autostart_plugins(stdscr)
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
                    elif ord(k) == 12:
                        k = 'CTRL_L'
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
                switch_plugin(stdscr, plugin_shortcuts[k])
            elif k == 'CTRL_L':
                try:
                    result = command('ready')
                except:
                    result = None
                with scr_lock:
                    if result:
                        print_message(
                            stdscr, 'Ready event sent', color=palette.OK)
                    else:
                        print_message(
                            stdscr, 'Command failed', color=palette.ERROR)
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
    _me = 'ppTOP version %s' % __version__

    ap = argparse.ArgumentParser(description=_me)
    ap.add_argument(
        '-V',
        '--version',
        help='Print version and exit',
        action='store_true',
        dest='_ver')
    ap.add_argument(
        'file', nargs='?', help='file, pid file or pid', metavar='FILE/PID')
    ap.add_argument(
        '-f',
        '--config-file',
        help='Alternative config file (default: ~/.pptop/pptop.yml)',
        metavar='CONFIG',
        dest='config')
    ap.add_argument(
        '-d',
        '--default',
        help='Default plugin to launch',
        metavar='PLUGIN',
        dest='plugin')
    ap.add_argument(
        '-o',
        '--plugin-option',
        help='Override plugin config option, e.g. threads.filter=mythread',
        metavar='NAME=VALUE',
        action='append',
        dest='plugin_options')

    try:
        import argcomplete
        argcomplete.autocomplete(ap)
    except:
        pass

    a = ap.parse_args()

    if a._ver:
        print(_me)
        exit()

    try:
        with open('/proc/sys/kernel/yama/ptrace_scope') as fd:
            yps = int(fd.read().strip())
    except:
        yps = None

    if yps:
        raise Exception(
            'yama ptrace scope is on. ' +
            'disable with "sudo sysctl -w kernel.yama.ptrace_scope=0"')

    plugin_options = {}

    for x in a.plugin_options or []:
        try:
            o, v = x.split('=', 1)
        except:
            o = x
            v = None
        d = plugin_options
        pl = o.split('.')
        for z in pl[:-1]:
            plugin_options[z] = {}
            d = plugin_options[z]
        d[pl[-1]] = v

    if a.file:
        try:
            # pid?
            _d.work_pid = int(a.file)
        except:
            # probably pid file
            try:
                with open(a.file) as fh:
                    _d.work_pid = int(fh.read(128))
            except:
                # okay, program to launch
                pass

    _d.pptop_dir = os.path.expanduser('~/.pptop')

    if a.config:
        config_file = a.config
        use_default_config = False
    else:
        config_file = _d.pptop_dir + '/pptop.yml'
        use_default_config = True

    sys.path.append(_d.pptop_dir + '/lib')
    config.clear()
    if use_default_config and not os.path.isfile(config_file):
        try:
            os.mkdir(_d.pptop_dir)
        except:
            pass
        if not os.path.isdir(_d.pptop_dir + '/scripts'):
            shutil.copytree(dir_me + '/config/scripts',
                            _d.pptop_dir + '/scripts')
        shutil.copy(dir_me + '/config/pptop.yml', _d.pptop_dir + '/pptop.yml')
    with open(config_file) as fh:
        config.update(yaml.load(fh.read()))

    if plugin_options:
        config.update(dict_merge(config, {'plugins': plugin_options}))

    plugins.clear()
    for i, v in config.get('plugins', {}).items():
        if v is None: v = {}
        try:
            mod = importlib.import_module('pptop.plugins.' + i)
        except ModuleNotFoundError:
            mod = importlib.import_module('pptopcontrib.' + i)
        plugin = {'m': mod}
        plugins[i] = plugin
        p = mod.Plugin(interval=int(v.get('interval', 1)))
        p.command = command
        p.get_plugins = get_plugins
        p.get_plugin = get_plugin
        p.get_config_dir = get_config_dir
        p.switch_plugin = switch_plugin
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
        if not _d.default_plugin or val_to_boolean(
                v.get('default')) or i == a.plugin:
            _d.default_plugin = plugin
        p.on_load()
        if 'shortcut' in v:
            sh = v['shortcut']
            plugin['shortcut'] = sh
            plugin_shortcuts[sh] = plugin
            if sh.startswith('KEY_F('):
                try:
                    f = int(sh[6:-1])
                    if f <= 12:
                        bottom_bar_help[f] = p.short_name
                except:
                    pass
        else:
            plugin['shortcut'] = ''
        if 'filter' in v:
            p.filter = str(v['filter'])
        if v.get('autostart'):
            plugins_autostart.append(plugin)
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
            client.close()
        except:
            pass
    atasker.task_supervisor.stop(wait=False)
