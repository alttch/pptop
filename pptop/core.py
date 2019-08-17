'''
Global shortcuts:

    Arrow keys  : Navigation
    Alt+arrows  : Sorting
    f, /        : Filter data
    Space       : Force data reload
    p           : Pause/resume current plugin
    Ctrl-i      : Re-inject current plugin
    Ctrl-l      : Send ready event
    `           : Python console mode (limited)
    Ctrl-c, F10 : Quit program

ppTOP v{version} (c) Altertech
The product is available under {license} license.

https://github.com/alttch/pptop
'''

__author__ = 'Altertech, https://www.altertech.com/'
__copyright__ = 'Copyright (C) 2019 Altertech'
__license__ = 'MIT'
__version__ = '0.2.7'

try:
    __doc__ = __doc__.format(version=__version__, license=__license__)
except:
    pass

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
import readline

import termcolor

try:
    yaml.warnings({'YAMLLoadWarning': False})
except:
    pass

from types import SimpleNamespace

from pptop.plugin import GenericPlugin, palette, glyph
from pptop.plugin import prompt, print_message
# DEBUG
from pptop.plugin import print_debug

from pptop.logger import config as log_config, log, log_traceback

from pptop.exceptions import CriticalException, ResizeException

logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('atasker/supervisor').setLevel(100)
logging.getLogger('atasker/workers').setLevel(100)

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

socket_buf = 8192


def get_plugins():
    return plugins


def init_curses(initial=False):
    stdscr = curses.initscr()
    if initial:
        if curses.has_colors():
            if config['display'].get('colors'):
                curses.start_color()
                curses.use_default_colors()
                for i in range(0, curses.COLORS):
                    curses.init_pair(i + 1, i, -1)
                init_color_palette()
        if config['display'].get('glyphs'):
            init_glyphs()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    return stdscr


def end_curses(stdscr):
    if stdscr:
        curses.nocbreak()
        stdscr.keypad(False)
        curses.echo()
        curses.endwin()


def get_config_dir():
    return _d.pptop_dir


def get_plugin(plugin_name):
    return plugins.get(plugin_name)


def get_child_info():
    return {'c': _d.child_cmd, 'a': _d.child_args} if _d.child else None


def apply_filter(stdscr, plugin):
    with scr_lock:
        plugin.filter = prompt(stdscr, ps='f: ', value=plugin.filter).lower()
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


def colored(text, color=None, on_color=None, attrs=None):
    if not config['display'].get('colors') or not sys.stdout.isatty():
        return str(text)
    else:
        return termcolor.colored(
            text, color=color, on_color=on_color, attrs=attrs)


def format_cmdline(p, injected):
    cmdline = ' '.join(p.cmdline())
    if not injected:
        cmdline = cmdline.split(' -m pptop.injection ')[-1].split(' ', 1)[0]
    return cmdline


def format_json(obj):
    import json
    return json.dumps(obj, indent=4, sort_keys=True)


def print_json(obj):
    j = format_json(obj)
    if config['display'].get('colors') and sys.stdout.isatty():
        from pygments import highlight, lexers, formatters
        j = highlight(j, lexers.JsonLexer(), formatters.TerminalFormatter())
    print(j)


def cli_mode():

    os.system('clear')
    print(
        colored(
            'Console mode, process {} connected'.format(_d.process.pid),
            color='green',
            attrs=['bold']))
    print(
        colored(
            format_cmdline(_d.process, _d.need_inject_server), color='yellow'))
    print(
        colored(
            'Enter any Python command, press Ctrl-D or type "exit" to quit'))
    print(colored('To toggle between JSON and normal mode, type ".j"'))
    print(colored('To execute multiple commands from file, type "< filename"'))
    print()
    readline.set_history_length(100)
    try:
        readline.read_history_file('{}/console.history'.format(_d.pptop_dir))
    except:
        pass
    try:
        while True:
            try:
                # TODO: tab autocomplete
                cmd = input('>>> ').strip()
                if cmd == '': continue
                elif cmd == 'exit':
                    raise EOFError
                elif cmd == '.j':
                    _d.console_json_mode = not _d.console_json_mode
                    print('JSON mode ' +
                          ('on' if _d.console_json_mode else 'off'))
                else:
                    if cmd.startswith('<'):
                        with open(os.path.expanduser(cmd[1:].strip())) as fh:
                            cmds = [x.strip() for x in fh.readlines()]
                    else:
                        cmds = [cmd]
                    for cmd in cmds:
                        r = command('.exec', cmd)
                        if r[0] == -1:
                            print(
                                colored(
                                    '{}: {}'.format(r[1], r[2]),
                                    color='red',
                                    attrs=['bold']))
                        else:
                            if r[1] is not None:
                                if _d.console_json_mode and \
                                        (isinstance(r[1], dict) or \
                                        isinstance(r[1], list)):
                                    print_json(r[1])
                                else:
                                    print(r[1])
            except EOFError:
                return
            except Exception as e:
                log_traceback()
                print(colored(str(e), color='red', attrs=['bold']))
    finally:
        try:
            readline.write_history_file('{}/console.history'.format(
                _d.pptop_dir))
        except:
            log_traceback()


class ProcesSelector(GenericPlugin):

    def load_data(self):
        self.data.clear()
        for p in psutil.process_iter():
            try:
                name = p.name()
                if name in ['python', 'python3'] and p.pid != os.getpid():
                    self.data.append({
                        'pid': p.pid,
                        'command line': ' '.join(p.cmdline())
                    })
            except:
                pass

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
                    raise ResizeException
                k = stdscr.getkey()
                if len(k) == 1:
                    if ord(k) == 6:
                        k = 'KEY_NPAGE'
                    elif ord(k) == 2:
                        k = 'KEY_PPAGE'
            except KeyboardInterrupt:
                return
            except (ResizeException, curses.error):
                log('resize event')
                with resize_lock:
                    resize_event.clear()
                    resize_handler(stdscr)
                    selector.resize()
                continue
            except Exception as e:
                log_traceback()
                raise
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
            log_traceback()
            raise
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
            log_traceback()
            raise CriticalException('Injector is gone')
        if not data:
            log('critical: no data from injector')
            raise CriticalException('Injector error')
        l = struct.unpack('I', data)[0]
        data = b''
        while len(data) != l:
            data += client.recv(socket_buf)
            if time.time() > time_start + socket_timeout:
                raise CriticalException('Socket timeout')
        if frame_id != _d.client_frame_id:
            log('critical: got wrong frame, channel is broken')
            raise CriticalException('Wrong frame')
        _d.last_frame_id += 1
        with ifoctets_lock:
            _d.ifoctets += len(data) + 8
            if _d.ifoctets > 1000000000:
                _d.ifoctets = d.ifoctets - 1000000000
        if data[0] != 0:
            log('injector command error, code: {}'.format(data[0]))
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
        with scr_lock:
            status = _d.status
            with p.oneshot():
                ct = p.cpu_times()
                stdscr.move(0, 0)
                stdscr.addstr('Process: ')
                cmdline = format_cmdline(p, _d.need_inject_server)
                stdscr.addstr(cmdline[:width - 25], palette.YELLOW)
                stdscr.addstr(' [')
                stdscr.addstr(
                    str(p.pid), palette.GREEN
                    if status == 1 else palette.GREY_BOLD)
                stdscr.addstr(']')
                if status == -1:
                    xst = 'WAIT'
                    xstc = palette.GREY_BOLD
                elif status == 0:
                    xst = 'DONE'
                    xstc = palette.GREY_BOLD
                elif status == -2:
                    xst = 'ERROR'
                    xstc = palette.ERROR
                else:
                    xst = None
                if xst:
                    stdscr.addstr(' ' + xst, xstc)
                stdscr.addstr('\nCPU: ')
                stdscr.addstr('{}%'.format(p.cpu_percent()), palette.BLUE_BOLD)
                stdscr.addstr(' user ')
                stdscr.addstr(str(ct.user), palette.BOLD)
                stdscr.addstr(' system ')
                stdscr.addstr(str(ct.system), palette.BOLD)
                stdscr.addstr(', threads: ')
                # always hide pptop thread
                stdscr.addstr(str(p.num_threads() - 1), palette.MAGENTA_BOLD)
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
                stdscr.addstr(' {} {}'.format(glyph.UPLOAD, ioc.read_count),
                              palette.GREEN)
                stdscr.addstr(' (')
                stdscr.addstr(bytes_to_iso(ioc.read_chars), palette.GREEN)
                stdscr.addstr(')')
                stdscr.addstr(' {} {}'.format(glyph.DOWNLOAD, ioc.write_count),
                              palette.BLUE)
                stdscr.addstr(' (')
                stdscr.addstr(bytes_to_iso(ioc.write_chars), palette.BLUE)
                stdscr.addstr(')')
            stdscr.clrtoeol()
            stdscr.refresh()
    except psutil.AccessDenied:
        log_traceback()
        return error('Access denied')
    except psutil.NoSuchProcess:
        log_traceback()
        return error('Process is gone')
    except CriticalException:
        log_traceback()
        return error('Process server is gone')
    except curses.error:
        log_traceback()
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
            stats = '{} {}/{} '.format(glyph.CONNECTION, _d.client_frame_id,
                                       _d.last_frame_id)
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


# don't make this async, it should always work in own thread
@atasker.background_worker(daemon=True)
def update_status(**kwargs):
    try:
        _d.status = command('.status')
    except:
        log_traceback()
        status = -2
    finally:
        time.sleep(1)


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
    gdb=None,
    work_pid=None,
    need_inject_server=True,
    inject_method=None,  # None (auto), 'native', 'loadcffi', 'unsafe'
    inject_lib=None,
    child=None,
    child_cmd=None,
    child_args='',
    status=None,
    console_json_mode=True,
    exec_code=None,
    output_as_json=False)

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


def find_lib(name):
    '''
    Find first library matching pattern
    '''
    import glob
    for d in sys.path:
        lib = glob.glob('{}/{}'.format(d, name))
        if lib:
            return lib[0]


def init_inject():
    if _d.inject_method is None or _d.inject_method == 'auto':
        _d.inject_method = 'native'
        _d.inject_lib = find_lib('__pptop_injector.*.so')
        if not _d.inject_lib:
            _d.inject_method = 'loadcffi'
            _d.inject_lib = find_lib('_cffi_backend.*.so')
            if not _d.inject_lib:
                _d.inject_method = 'unsafe'
    else:
        if _d.inject_method == 'native':
            _d.inject_lib = find_lib('__pptop_injector.*.so')
            if not _d.inject_lib:
                raise RuntimeError(
                    '__pptop_injector shared library not found.' +
                    ' reinstall package or select different inject method')
        elif _d.inject_method == 'loadcffi':
            _d.inject_lib = find_lib('_cffi_backend.*.so')
            if not _d.inject_lib:
                raise RuntimeError(
                    '_cffi_backend shared library not found.' +
                    ' install "cffi" package or select different inject method')
        else:
            _d.inject_method = 'unsafe'


def inject_server(gdb, pid):
    cmds = []
    libpath = os.path.abspath(os.path.dirname(__file__) + '/..')
    if _d.inject_method in ['native', 'loadcffi']:
        cmds.append('call (void)__libc_dlopen_mode("{}", 2)'.format(
            _d.inject_lib))
    if _d.inject_method == 'native':
        cmds.append('call (int)__pptop_start_injection("{}",{},"{}")'.format(
            libpath, os.getpid(), log_config.fname if log_config.fname else ''))
    else:
        cmds += [
            'call (PyGILState_STATE)PyGILState_Ensure()',
            ('call (int)PyRun_SimpleString("' +
             'import sys;sys.path.insert(0,\\"{path}\\");' +
             'import pptop.injection;pptop.injection.start({mypid}{lg})")'
            ).format(
                path=libpath,
                mypid=os.getpid(),
                lg='' if not log_config.fname else ',lg=\\"{}\\"'.format(
                    log_config.fname)), ' call (void)PyGILState_Release($1)'
        ]
    args = [gdb, '-p', str(pid), '--batch'
           ] + ['--eval-command={}'.format(c) for c in cmds]
    log(args)
    p = subprocess.Popen(
        args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    log(out)
    log(err)
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
    palette.PROMPT = curses.color_pair(3) | curses.A_BOLD


def init_glyphs():
    glyph.UPLOAD = '⇈'
    glyph.DOWNLOAD = '⇊'
    glyph.ARROW_UP = '↑'
    glyph.ARROW_DOWN = '↓'
    glyph.SELECTOR = '→'
    glyph.CONNECTION = '⇄'


def switch_plugin(stdscr, new_plugin):
    if _d.current_plugin:
        if _d.current_plugin is new_plugin:
            return
        if not _d.current_plugin['p'].background:
            _d.current_plugin['p'].stop(wait=False)
        else:
            _d.current_plugin['p'].hide()
    p = new_plugin['p']
    with scr_lock:
        p.stdscr = stdscr
    p._previous_plugin = _d.current_plugin
    p.key_event = None
    if new_plugin['inj'] is False:
        new_plugin['inj'] = True
        command('.inject', new_plugin['i'])
    if not p.is_active(): p.start()
    p.show()
    _d.current_plugin = new_plugin


def run():

    @atasker.background_task
    def autostart_plugins(stdscr):
        for plugin in plugins_autostart:
            if plugin['p'] is not _d.current_plugin.get('p'):
                log('autostarting {}'.format(plugin['m']))
                if not plugin['inj']:
                    plugin['inj'] = True
                    command('.inject', plugin['i'])
                p = plugin['p']
                if p.background:
                    p.key_event = None
                    p.stdscr = stdscr
                    p.start()

    stdscr = None

    try:

        if not _d.work_pid:
            stdscr = init_curses(initial=True)
            p = select_process(stdscr)
        else:
            p = psutil.Process(_d.work_pid)

        if not p: return

        _d.process = p

        client.settimeout(socket_timeout)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, socket_buf)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, socket_buf)
        if _d.need_inject_server:
            if not _d.gdb:
                _d.gdb = shutil.which('gdb')
                if not _d.gdb:
                    raise RuntimeError(
                        'gdb not found in path, please specify manually')
            inject_server(_d.gdb, p.pid)
            log('server injected')
        sock_path = '/tmp/.pptop.{}'.format(os.getpid())
        for i in range(injection_timeout * 10):
            if os.path.exists(sock_path):
                break
            time.sleep(0.1)
        try:
            client.connect(sock_path)
        except:
            log_traceback()
            raise RuntimeError('Unable to connect to process')

        log('connected')

        if _d.exec_code:
            end_curses(stdscr)
            result = command('.x', _d.exec_code)
            if stdscr:
                os.system('clear')
            if result[0] == 0:
                if _d.output_as_json:
                    print_json(result[1])
                else:
                    print(result[1] if result[1] else '')
            else:
                print(
                    colored(
                        '{}: {}'.format(result[1], result[2]),
                        color='red',
                        attrs=['bold']))
            return

        if not stdscr:
            stdscr = init_curses(initial=True)

        signal.signal(signal.SIGWINCH, sigwinch_handler)
        _d.stdscr = stdscr

        calc_bw.start()
        update_status.start()

        _d.process_path.clear()
        ppath = []
        for i in command('.path'):
            ppath.append(os.path.abspath(i))
        _d.process_path.extend(sorted(ppath, reverse=True))
        log('process path: {}'.format(_d.process_path))

        height, width = stdscr.getmaxyx()
        stdscr.clear()
        stdscr.refresh()
        curses.curs_set(0)
        switch_plugin(stdscr, _d.default_plugin)
        atasker.background_task(show_process_info.start)(stdscr=stdscr, p=p)
        atasker.background_task(show_bottom_bar.start)(stdscr=stdscr)
        autostart_plugins(stdscr)
        log('main loop started')
        while True:
            try:
                try:
                    if resize_event.is_set():
                        raise ResizeException
                    k = stdscr.getkey()
                    if len(k) == 1:
                        z = ord(k)
                        if z == 6:
                            k = 'KEY_NPAGE'
                        elif z == 2:
                            k = 'KEY_PPAGE'
                        elif z == 10:
                            k = 'ENTER'
                        elif z < 27:
                            k = 'CTRL_' + chr(z + 64)
                    log('key pressed: {}'.format(
                        k if len(k) > 1 else ((
                            'ord=' +
                            str(ord(k))) if ord(k) < 32 else '"{}"'.format(k))))
                except KeyboardInterrupt:
                    return
                except (ResizeException, curses.error):
                    log('resize event')
                    with resize_lock:
                        resize_event.clear()
                        resize_handler(stdscr)
                        _d.current_plugin['p'].resize()
                        show_process_info.trigger()
                    continue
                except Exception as e:
                    log_traceback()
                    raise
                if not show_process_info.is_active():
                    return
                elif k in plugin_shortcuts:
                    switch_plugin(stdscr, plugin_shortcuts[k])
                elif k == 'CTRL_L':
                    try:
                        result = command('.ready')
                    except:
                        result = None
                    with scr_lock:
                        if result:
                            print_message(
                                stdscr, 'Ready event sent', color=palette.OK)
                        else:
                            print_message(
                                stdscr, 'Command failed', color=palette.ERROR)
                elif k == 'CTRL_I' and _d.current_plugin['inj'] is not None:
                    try:
                        result = command('.inject', _d.current_plugin['i'])
                    except:
                        result = None
                    with scr_lock:
                        if result:
                            print_message(
                                stdscr, 'Plugin re-injected', color=palette.OK)
                        else:
                            print_message(
                                stdscr,
                                'Plugin re-injection failed',
                                color=palette.ERROR)
                elif k in ['KEY_F(10)']:
                    _d.current_plugin['p'].stop(wait=False)
                    show_process_info.stop(wait=False)
                    show_bottom_bar.stop(wait=False)
                    return
                elif k == '`':
                    with scr_lock:
                        end_curses(stdscr)
                        cli_mode()
                        stdscr = init_curses()
                        _d.current_plugin['p'].stdscr = stdscr
                        _d.current_plugin['p'].init_render_window()
                elif k in ('f', '/'):
                    apply_filter(stdscr, _d.current_plugin['p'])
                elif k == 'p':
                    _d.current_plugin['p'].toggle_pause()
                elif k in _d.current_plugin['p'].inputs:
                    with scr_lock:
                        try:
                            prev_value = _d.current_plugin['p'].get_input(k)
                        except ValueError:
                            continue
                        value = prompt(
                            stdscr,
                            ps=_d.current_plugin['p'].get_input_prompt(k),
                            value=prev_value if prev_value is not None else '')
                        _d.current_plugin['p'].inputs[k] = value
                        try:
                            _d.current_plugin['p'].handle_input(
                                k, value, prev_value)
                        except:
                            pass
                else:
                    with scr_lock:
                        _d.current_plugin['p'].key_event = k
                        _d.current_plugin['p'].trigger()
            except:
                log_traceback()
                return
    except:
        log_traceback()
        raise
    finally:
        end_curses(stdscr)


def start():

    def format_plugin_option(dct, o, v):
        if o.find('.') != -1:
            x, y = o.split('.', 1)
            dct[x] = {}
            format_plugin_option(dct[x], y, v)
        else:
            dct[o] = v

    _me = 'ppTOP version %s' % __version__

    ap = argparse.ArgumentParser(description=_me)
    ap.add_argument(
        '-V', '--version', help='Print version and exit', action='store_true')
    ap.add_argument(
        '-R',
        '--raw',
        help='Raw mode (disable colors and unicode glyphs)',
        action='store_true')
    ap.add_argument(
        '--disable-glyphs', help='disable unicode glyphs', action='store_true')
    ap.add_argument(
        'file', nargs='?', help='File, PID file or PID', metavar='FILE/PID')
    ap.add_argument('-a', '--args', metavar='ARGS', help='Child args (quoted)')
    ap.add_argument(
        '--python', metavar='FILE', help='Python interpreter to launch file')
    ap.add_argument('--gdb', metavar='FILE', help='Path to gdb')
    ap.add_argument(
        '--inject-method',
        choices=['auto', 'native', 'loadcffi', 'unsafe'],
        help='Inject method')
    ap.add_argument(
        '-w',
        '--wait',
        metavar='SEC',
        type=float,
        help='If file is specified, wait seconds to start main code')
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
    ap.add_argument('--log', metavar='FILE', help='Send debug log to file')
    ap.add_argument(
        '-x',
        '--exec',
        help='Exec code from the specified file and exit ' + \
                ' (code may put result to "out" var)',
        metavar='FILE',
        dest='_exec')
    ap.add_argument(
        '-J', '--json', help='Output exec result as JSON', action='store_true')

    try:
        import argcomplete
        argcomplete.autocomplete(ap)
    except:
        pass

    a = ap.parse_args()

    if a.log:
        log_config.fname = a.log
        log_config.name = 'client:{}'.format(os.getpid())

    if a.version:
        print(_me)
        exit()

    if a.gdb:
        _d.gdb = a.gdb

    log('initializing')

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
                _d.child_cmd = os.path.abspath(a.file)

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
        log('no user config, setting default')
        try:
            os.mkdir(_d.pptop_dir)
        except:
            pass
        if not os.path.isdir(_d.pptop_dir + '/scripts'):
            shutil.copytree(dir_me + '/config/scripts',
                            _d.pptop_dir + '/scripts')
        shutil.copy(dir_me + '/config/pptop.yml', _d.pptop_dir + '/pptop.yml')
        if not os.path.isdir(_d.pptop_dir + '/lib'):
            os.mkdir(_d.pptop_dir + '/lib')
    with open(config_file) as fh:
        config.update(yaml.load(fh.read()))

    console = config.get('console')
    if console is None: console = {}

    _d.console_json_mode = console.get('json-mode')

    _d.inject_method = a.inject_method if a.inject_method else config.get(
        'inject-method')

    if config.get('display') is None:
        config['display'] = {}

    if a.raw:
        config['display']['colors'] = False

    if a.raw or a.disable_glyphs:
        config['display']['glyphs'] = False

    if a._exec:
        with open(a._exec) as fd:
            _d.exec_code = fd.read()
        _d.output_as_json = a.json

    else:
        plugin_options = {}

        for x in a.plugin_options or []:
            try:
                o, v = x.split('=', 1)
            except:
                o = x
                v = None
            format_plugin_option(plugin_options, o, v)

        if plugin_options:
            config.update(dict_merge(config, {'plugins': plugin_options}))

        log('loading plugins')

        plugins.clear()
        for i, v in config.get('plugins', {}).items():
            log('+ plugin ' + i)
            if v is None: v = {}
            try:
                mod = importlib.import_module('pptop.plugins.' + i)
                mod.__version__ = 'built-in'
            except ModuleNotFoundError:
                mod = importlib.import_module('pptopcontrib-' + i)
                try:
                    mod.__version__
                except:
                    raise RuntimeError(
                        'Please specify __version__ in plugin file')
            plugin = {'m': mod}
            plugins[i] = plugin
            p = mod.Plugin(interval=float(v.get('interval', 1)))
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
                plugin['inj'] = None
            if not _d.default_plugin or val_to_boolean(
                    v.get('default')) or i == a.plugin:
                _d.default_plugin = plugin
            p_cfg = v.get('config')
            p.config = {} if p_cfg is None else p_cfg
            p.on_load()
            if 'l' in injection:
                injection['lkw'] = p.get_injection_load_params()
            if 'shortcut' in v:
                sh = v['shortcut']
                plugin['shortcut'] = sh
                plugin_shortcuts[sh] = plugin
                if sh.startswith('KEY_F('):
                    try:
                        f = int(sh[6:-1])
                        if f <= 10:
                            bottom_bar_help[f] = p.short_name
                    except:
                        pass
            else:
                plugin['shortcut'] = ''
            if 'filter' in v:
                p.filter = str(v['filter'])
            if v.get('autostart'):
                plugins_autostart.append(plugin)
    atasker.task_supervisor.set_thread_pool(
        pool_size=100, reserve_normal=100, reserve_high=50)
    atasker.task_supervisor.start()
    try:
        if a.file and not _d.work_pid:
            # launch file
            _d.need_inject_server = False
            if a.python:
                python_path = a.python
            else:
                python_path = shutil.which('python3')
                if not python_path:
                    raise RuntimeError(
                        'python3 not found in path, please specify manually')
            args = (python_path, '-m', 'pptop.injection', a.file,
                    str(os.getpid()))
            if a.wait is not None:
                args += ('-w', str(a.wait))
            if a.args:
                args += ('-a', a.args)
            if log_config.fname:
                args += ('--log', log_config.fname)
            log('starting child process')
            _d.child = subprocess.Popen(
                args,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
            _d.work_pid = _d.child.pid
        else:
            # check yama ptrace scope
            try:
                with open('/proc/sys/kernel/yama/ptrace_scope') as fd:
                    yps = int(fd.read().strip())
            except:
                yps = None
            if yps:
                raise RuntimeError(
                    'yama ptrace scope is on. ' +
                    'disable with "sudo sysctl -w kernel.yama.ptrace_scope=0"')
            init_inject()
            log('inject method: {}'.format(_d.inject_method))
            log('inject library: {}'.format(_d.inject_lib))
        run()
        for p, v in plugins.items():
            v['p'].on_unload()
    except Exception as e:
        log_traceback()
        raise
    finally:
        try:
            client.close()
        except:
            pass
        atasker.task_supervisor.stop(wait=False)
    return 0
