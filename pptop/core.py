'''
ppTOP v{version} (c) Altertech
The product is available under {license} license.

https://pptop.io/
'''

__author__ = 'Altertech, https://www.altertech.com/'
__copyright__ = 'Copyright (C) 2019 Altertech'
__license__ = 'MIT'
__version__ = '0.6.12'

try:
    __doc__ = __doc__.format(version=__version__, license=__license__)
except:
    pass

import sys
import curses
import neotasker
import socket
import struct
import yaml
import logging
import inspect
import threading
import psutil
import os
import getpass
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
import textwrap

import neotermcolor as termcolor

from collections import OrderedDict
from functools import partial

from pyaltt2.converters import merge_dict, val_to_boolean
from pyaltt2.json import jprint

try:
    yaml.warnings({'YAMLLoadWarning': False})
except:
    pass

os.unsetenv('LINES')
os.unsetenv('COLUMNS')

from types import SimpleNamespace

from pptop.plugin import GenericPlugin, process_path as plugin_process_path

from pptop.plugin import bytes_to_iso

from pptop.ui.console import init_curses, end_curses, cls
from pptop.ui.console import resize_term, resize_handler
from pptop.ui.console import prompt, print_message, scr, palette, glyph
from pptop.ui.console import hide_cursor, show_cursor

from pptop.logger import config as log_config, log, log_traceback, init_logging

from pptop.exceptions import CriticalException

logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('neotasker').setLevel(100)

dir_me = os.path.dirname(os.path.realpath(__file__))

config = {}

plugins = {}
events_by_key = {
    'f': 'filter',
    '/': 'filter',
    'I': 'interval',
    'ENTER': 'select',
    'CTRL_L': 'ready',
    'CTRL_I': 'reinject',
    '`': 'console',
    'CTRL_O': 'show-console',
    'KEY_BACKSPACE': 'delete',
    'KEY_DC': 'delete',
    'p': 'pause',
    'q': 'back',
    'ESC': 'back',
    'kRIT3': 'sort-col-next',
    'kLFT3': 'sort-col-prev',
    'kDN3': 'sort-normal',
    'kUP3': 'sort-reverse',
    'KEY_LEFT': 'left',
    'KEY_RIGHT': 'right',
    'KEY_UP': 'up',
    'KEY_DOWN': 'down',
    'kLFT5': 'hshift-left',
    'kRIT5': 'hshift-right',
    'KEY_PPAGE': 'page-up',
    'CTRL_B': 'page-up',
    'KEY_NPAGE': 'page-down',
    'CTRL_F': 'page-down',
    'KEY_HOME': 'home',
    'KEY_END': 'end',
    'KEY_F(10)': 'quit',
    ' ': 'reload',
    'CTRL_X': 'reset',
    'Z': 'cursor-toggle'
}

plugins_autostart = []

bottom_bar_help = {10: 'Quit'}
plugin_shortcuts = {}

plugin_lock = threading.Lock()

stdout_buf_lock = threading.Lock()

socket_timeout = 15

injection_timeout = 3

socket_buf = 8192


class ppLoghandler(logging.Handler):

    def emit(self, record):
        log(super().format(record))


def after_resize():
    _d.current_plugin['p'].resize()
    show_process_info.trigger_threadsafe(force=True)


def get_plugins():
    return plugins


def get_config_dir():
    return _d.pptop_dir


def get_plugin(plugin_name):
    return plugins.get(plugin_name)


def get_child_info():
    return {'c': _d.child_cmd, 'a': _d.child_args} if _d.child else None


def apply_filter(plugin):
    with scr.lock:
        plugin.filter = prompt(ps='f: ', value=plugin.filter).lower()
        plugin.trigger_threadsafe()


def apply_interval(plugin):
    with scr.lock:
        i = plugin.delay
        if int(i) == i:
            i = int(i)
        new_interval = prompt(ps='intreval: ', value=i)
        try:
            new_interval = float(new_interval)
            if new_interval <= 0:
                raise ValueError
        except:
            print_message('Invalid interval', color=palette.ERROR)
            return
    plugin.stop()
    plugin.start(_interval=new_interval)
    plugin.show()
    with scr.lock:
        print_message('Interval changed', color=palette.OK)
        return


def wait_key():
    result = None
    import termios
    fd = sys.stdin.fileno()

    oldterm = termios.tcgetattr(fd)
    newattr = termios.tcgetattr(fd)
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, newattr)

    try:
        result = sys.stdin.read(1)
    except IOError:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

    return result


key_names = {
    'KEY_DOWN': 'Down',
    'KEY_UP': 'Up',
    'KEY_LEFT': 'Left',
    'KEY_RIGHT': 'Right',
    'KEY_HOME': 'Home',
    'KEY_END': 'End',
    'KEY_BACKSPACE': 'Backspace',
    'KEY_DC': 'Del',
    'KEY_IC': 'Ins',
    'KEY_NPAGE': 'PgDn',
    'KEY_PPAGE': 'PgUp',
    'CTRL_I': 'Tab',
    'CTRL_J': 'Enter',
    'kLFT5': 'C-Left',
    'kRIT5': 'C-Right',
    'kUP5': 'C-Up',
    'kDN5': 'C-Down',
    'kPRV5': 'C-PgUp',
    'kNXT5': 'C-PgDn',
    'kHOM5': 'C-Home',
    'kEND5': 'C-End',
    'kLFT3': 'C-Left',
    'kRIT3': 'C-Right',
    'kUP3': 'C-Up',
    'kDN3': 'C-Down',
    'kPRV3': 'C-PgUp',
    'kNXT3': 'C-PgDn',
    'kHOM3': 'C-Home',
    'kEND3': 'C-End',
}


def format_shortcut(k):
    k = str(k)
    sh = k
    try:
        if k in key_names:
            sh = key_names[k]
        elif k.startswith('KEY_F('):
            fnkey = int(sh[6:-1])
            if fnkey > 48:
                sh = 'M-F{}'.format(fnkey - 48)
            elif fnkey > 24:
                sh = 'C-F{}'.format(fnkey - 24)
            elif fnkey > 12:
                sh = 'Sh-F{}'.format(fnkey - 12)
            else:
                sh = 'F{}'.format(fnkey)
        elif k.startswith('CTRL_'):
            sh = 'C-{}'.format(k[5:].lower())
        else:
            if len(k) == 1:
                if k.isalpha() and k.lower() != k:
                    sh = 'Sh-{}'.format(k.lower())
                elif k == ' ':
                    sh = 'Space'
                else:
                    sh = k
            else:
                sh = k.capitalize()
    except:
        log_traceback()
    return sh


def format_key(k):
    if len(k) == 1:
        z = ord(k)
        if z == 10:
            k = 'ENTER'
        elif z == 27:
            k = 'ESC'
        elif z < 27:
            k = 'CTRL_' + chr(z + 64)
    log('key pressed: {}'.format(k if len(k) > 1 else ((
        'ord=' + str(ord(k))) if ord(k) < 32 else '"{}"'.format(k))))
    return k


def get_key_event(k):
    event = events_by_key.get(k, k)
    log('key event: {}'.format(event))
    return event


def colored(text, color=None, on_color=None, attrs=None):
    try:
        if not config['display'].get('colors'):
            return str(text)
        else:
            return termcolor.colored(str(text),
                                     color=color,
                                     on_color=on_color,
                                     attrs=attrs)
    except:
        return str(text)


err = partial(colored, color='red', attrs=['bold'])


def format_cmdline(p, injected):
    cmdline = ' '.join(p.cmdline())
    if not injected:
        cmdline = cmdline.split(' -m pptop.injection ')[-1].split(' ', 1)[0]
    return cmdline


def print_json(obj):
    jprint(obj, colored=config['display'].get('colors'))


def cli_mode():

    def compl(text, state):
        if not text or text.find('.') == -1:
            return None
        o = text.rsplit('.', 1)[0]
        src = 'try: __result = dir({})\nexcept: pass'.format(o)
        result = command('.exec', src)
        if not result or result[0] or not result[1]: return None
        matches = [
            s for s in result[1] if ('{}.{}'.format(o, s)).startswith(text)
        ]
        try:
            return '{}.{}'.format(o, matches[state])
        except IndexError:
            return None

    log('cli mode started')
    if _d.cli_first_time:
        # os.system('clear')
        print(
            colored('Console mode, process {} connected'.format(_d.process.pid),
                    color='green',
                    attrs=['bold']))
        print(
            colored(format_cmdline(_d.process, _d.need_inject_server),
                    color='yellow'))
        print(
            colored(
                'Enter any Python command, press Ctrl-D or type "exit" to quit')
        )
        print(colored('To toggle between JSON and normal mode, type ".j"'))
        if _d.grab_stdout:
            print(colored('To toggle stdout/stderr output, type ".p"'))
        print(
            colored(
                'To execute multiple commands from file, type "< filename"'))
        print(
            colored(
                'To explore object, type "obj?" (transformed to "dir(obj)")'))
        if _d.protocol < 3:
            print(
                colored('For Python 2 use \'_print\' instead of \'print\'',
                        color='yellow',
                        attrs=['bold']))
        print()
        _d.cli_first_time = False
    readline.set_history_length(100)
    readline.set_completer_delims('')
    readline.set_completer(compl)
    readline.parse_and_bind('tab: complete')
    try:
        readline.read_history_file('{}/console.history'.format(_d.pptop_dir))
    except:
        pass
    try:
        while True:
            try:
                cmd = input('>>> ').strip()
                if cmd == '': continue
                elif cmd == 'exit':
                    raise EOFError
                elif _d.grab_stdout and cmd == '.p':
                    if print_stdout.is_active():
                        print_stdout.stop()
                    else:
                        print_stdout.start()
                elif cmd == '.j':
                    _d.console_json_mode = not _d.console_json_mode
                    print('JSON mode ' +
                          ('on' if _d.console_json_mode else 'off'))
                else:
                    if cmd.startswith('<'):
                        with open(os.path.expanduser(cmd[1:].strip())) as fh:
                            cmds = filter(None,
                                    [x.strip() for x in fh.readlines()])
                    elif cmd.endswith('?'):
                        cmds = ['dir({})'.format(cmd[:-1]).strip()]
                    else:
                        cmds = [cmd]
                    for cmd in cmds:
                        r = command('.exec', cmd)
                        if r[0] == -1:
                            print(err('{}: {}'.format(r[1], r[2])))
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
            except KeyboardInterrupt:
                print()
                continue
            except Exception as e:
                log_traceback()
                print(err(e))
    finally:
        log('cli mode completed')
        try:
            readline.write_history_file('{}/console.history'.format(
                _d.pptop_dir))
        except:
            log_traceback()


class ProcesSelector(GenericPlugin):

    def load_data(self):
        self.data.clear()
        px = ['python', 'python2', 'python3']
        user = getpass.getuser() if os.getuid() else 'root'
        for p in psutil.process_iter():
            try:
                with p.oneshot():
                    name = p.name().split('.', 1)[0]
                    fname = p.exe().rsplit('/', 1)[-1].split('.', 1)[0]
                    if (name in px or
                            fname in px) and p.pid != os.getpid() and (
                                user == 'root' or p.username() == user):
                        d = OrderedDict()
                        d['pid'] = p.pid
                        d['command line'] = ' '.join(p.cmdline())
                        self.data.append(d)
            except psutil.AccessDenied:
                pass
            except:
                log_traceback()

    def render(self, dtd):
        if not self.filter: self.print_message()
        super().render(dtd)
        scr.stdscr.move(scr.stdscr.getmaxyx()[0] - 1, 0)
        scr.stdscr.clrtoeol()

    def render_empty(self):
        if self.is_active():
            if self.filter == '':
                self.window.clrtobot()
                self.print_message('No Python processes found in system. ' +
                                   'Waiting... "q" to abort',
                                   color=palette.WARNING)
            else:
                super().render_empty()

    def get_table_col_color(self, element, key, value):
        if key == 'pid':
            return palette.GREEN

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def select_process():

    with scr.lock:
        cls()
        hide_cursor()
    selector = ProcesSelector(interval=1)
    selector.events = 0
    selector.name = 'process_selector'
    selector.sorting_rev = False
    selector.selectable = True
    selector.finish_event = threading.Event()
    selector.lock = threading.Lock()
    selector.title = 'Select process'
    selector.show()
    selector.start()
    _d.current_plugin = {'p': selector}
    while True:
        try:
            try:
                k = format_key(scr.stdscr.getkey())
                event = get_key_event(k)
            except KeyboardInterrupt:
                return
            except curses.error:
                resize_handler.trigger_threadsafe(force=True)
                continue
            if event == 'back':
                selector.stop(wait=False)
                return
            elif event == 'filter':
                apply_filter(selector)
            elif event == 'select':
                if not selector.dtd:
                    continue
                selector.stop(wait=False)
                return psutil.Process(selector.dtd[selector.cursor]['pid'])
            elif event == 'pause':
                with scr.lock:
                    selector.toggle_pause()
            else:
                with scr.lock:
                    selector.key_code = k
                    selector.key_event = event
                    selector.trigger_threadsafe()
        except:
            log_traceback()
            raise
    return


ifoctets_lock = threading.Lock()
client_lock = threading.Lock()

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

frame_counter_reset = 1000


def command(cmd, params=None):
    with client_lock:
        _d.client_frame_id += 1
        if _d.client_frame_id >= frame_counter_reset:
            _d.client_frame_id = 1
            _d.last_frame_id = 0
        try:
            frame = cmd.encode()
            if params is not None:
                frame += b'\xff' + pickle.dumps(params, protocol=_d.protocol)
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
                _d.ifoctets = _d.ifoctets - 1000000000
        if data[0] != 0:
            log('injector command error, code: {}'.format(data[0]))
            raise RuntimeError('Injector command error')
        return pickle.loads(data[1:]) if len(data) > 1 else True


def get_process():
    return _d.process


def get_process_path():
    return _d.process_path


_info_col_width = {0: 15, 1: 20, 2: 14, 3: 10}
_info_col_pos = {0: 0}

# _vblks='▁▂▃▅▆▇'


def recalc_info_col_pos():
    pos = 0
    for i in _info_col_width:
        if i:
            pos += _info_col_width[i - 1] + 2  #(
            # 5 if config['display'].get('glyphs') and i == 1 else 2)
            _info_col_pos[i] = pos


@neotasker.background_worker(delay=1)
async def show_process_info(p, **kwargs):

    def error(txt):
        cls()
        scr.stdscr.addstr(0, 0, str(txt), palette.ERROR)
        scr.stdscr.refresh()
        return False

    def draw_val(row,
                 col,
                 label='',
                 value=None,
                 color=palette.DEFAULT,
                 spacer=True):
        width = _info_col_width[col]
        pos = _info_col_pos[col]
        val = str(value) if value is not None else ''
        scr.infowin.move(row + 1, pos)
        if label:
            scr.infowin.addstr(label)
            if spacer:
                scr.infowin.addstr(
                    ('.' if config['display']['colors'] else ' ') *
                    (width - len(label) - len(val)), palette.DARKGREY)
                scr.infowin.move(row + 1, pos + width - len(val))
            else:
                scr.infowin.addstr(' ')
        scr.infowin.addstr(val, color)

    try:
        width = scr.infowin.getmaxyx()[1]
        status = _d.status
        scr.infowin.clear()
        with p.oneshot():
            ct = p.cpu_times()
            memf = p.memory_full_info()
            mem = p.memory_info()
            ioc = p.io_counters()
            scr.infowin.move(0, 0)
            scr.infowin.addstr('Process: ')
            cmdline = format_cmdline(p, _d.need_inject_server)
            scr.infowin.addstr(cmdline[:width - 25], palette.YELLOW)
            scr.infowin.addstr(' [')
            scr.infowin.addstr(
                str(p.pid), palette.GREEN if status == 1 else palette.GREY_BOLD)
            scr.infowin.addstr(']')
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
                scr.infowin.addstr(' ' + xst, xstc)

            cpup = p.cpu_percent()

            draw_val(0, 0, 'CPU', '{}%'.format(cpup), palette.BLUE_BOLD)
            draw_val(1, 0, 'user', ct.user, palette.BOLD)
            draw_val(2, 0, 'system', ct.system, palette.BOLD)
            # always hide pptop thread
            draw_val(3, 0, 'threads', p.num_threads() - 1, palette.MAGENTA)

            # if config['display'].get('glyphs'):
            # gauge = _vblks[-1] * int(cpup // 25)
            # i = int(cpup % 25 / 25 * len(_vblks))
            # if i:
            # gauge += _vblks[i - 1]
            # x = _info_col_width[0] + 1
            # for i, g in enumerate(gauge):
            # scr.stdscr.addstr(4 - i, x, g * 2,
            # (palette.GREEN, palette.YELLOW,
            # palette.RED, palette.RED)[i])

            draw_val(0, 1, 'Memory uss', bytes_to_iso(memf.uss), palette.BOLD)
            draw_val(1, 1, 'pss', bytes_to_iso(memf.pss), palette.BOLD)
            draw_val(2, 1, 'swap', bytes_to_iso(memf.swap),
                     palette.GREY if memf.swap < 1000000 else palette.YELLOW)

            draw_val(0, 2, 'shd', bytes_to_iso(mem.shared), palette.BOLD)
            draw_val(1, 2, 'txt', bytes_to_iso(mem.text), palette.BOLD)
            draw_val(2, 2, 'dat', bytes_to_iso(mem.data), palette.BOLD)

            draw_val(0,
                     3,
                     'Files:',
                     len(p.open_files()),
                     palette.CYAN,
                     spacer=False)

            draw_val(1,
                     3,
                     value='{} {} ({})'.format(glyph.UPLOAD, ioc.read_count,
                                               bytes_to_iso(ioc.read_chars)),
                     color=palette.GREEN)
            draw_val(2,
                     3,
                     value='{} {} ({})'.format(glyph.DOWNLOAD, ioc.write_count,
                                               bytes_to_iso(ioc.write_chars)),
                     color=palette.BLUE)
        with scr.lock:
            scr.infowin.refresh()
            scr.stdscr.refresh()
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
                scr.stdscr.move(i, 0)
                scr.stdscr.clrtoeol()
            scr.stdscr.refresh()
        except:
            pass
    except Exception as e:
        return error(e)


@neotasker.background_worker(delay=0.1)
async def show_bottom_bar(**kwargs):
    try:
        with scr.lock:
            height, width = scr.stdscr.getmaxyx()
            scr.stdscr.move(height - 1, 0)
            scr.stdscr.addstr(' ' * (width - 1), palette.BAR)
            scr.stdscr.move(height - 1, 0)
            color = palette.BAR
            for h in sorted(bottom_bar_help):
                scr.stdscr.addstr('F{}'.format(h))
                scr.stdscr.addstr(bottom_bar_help[h].ljust(6), color)
            try:
                with plugin_lock:
                    i = _d.current_plugin['p'].delay
                if int(i) == i:
                    i = int(i)
                i = 'I:' + str(i)
            except:
                i = ''
            stats = '{} P:{} {} {:03d}/{:03d} '.format(i, _d.protocol,
                                                       glyph.CONNECTION,
                                                       _d.client_frame_id,
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
            scr.stdscr.addstr(height - 1, width - len(stats) - len(bws) - 1,
                              stats, color)
            scr.stdscr.addstr(bws, bwc)
            scr.stdscr.refresh()
    except:
        pass


# don't make this async, it should always work in own thread
@neotasker.background_worker
def update_status(**kwargs):
    try:
        _d.status = command('.status')
    except:
        log_traceback()
        status = -2
    finally:
        time.sleep(1)


@neotasker.background_worker
def grab_stdout(**kwargs):
    try:
        result = command('.gs')
        with stdout_buf_lock:
            _d.stdout_buf += result
    except:
        log_traceback()
    finally:
        time.sleep(0.5)


@neotasker.background_worker
def print_stdout(**kwargs):
    with stdout_buf_lock:
        if _d.stdout_buf != '':
            print(_d.stdout_buf, end='')
            _d.stdout_buf = ''
    time.sleep(0.1)


@neotasker.background_worker(interval=1)
async def calc_bw(**kwargs):
    with ifoctets_lock:
        if _d.ifoctets >= _d.ifoctets_prev:
            _d.ifbw = _d.ifoctets - _d.ifoctets_prev
        else:
            _d.ifbw = 1000000000 - _d.ifoctets_prev + _d.ifoctets
        _d.ifoctets_prev = _d.ifoctets


_d = SimpleNamespace(
    cli_first_time=True,
    grab_stdout=False,
    stdout_buf='',
    current_plugin=None,
    process_path=[],
    default_plugin=None,
    process=None,
    protocol=None,
    force_protocol=None,
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


def sigwinch_handler(signum=None, frame=None):
    resize_handler.trigger_threadsafe(force=True)


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


def inject_server(gdb, p):
    cmds = []
    pid = p.pid
    libpath = os.path.abspath(os.path.dirname(__file__) + '/..')
    if _d.inject_method in ['native', 'loadcffi']:
        cmds.append('call (void)dlopen("{}", 2)'.format(_d.inject_lib))
    if _d.inject_method == 'native':
        cmds.append('call (int)__pptop_start_injection("{}",{},{},"{}")'.format(
            libpath, os.getpid(), _d.protocol,
            log_config.fname if log_config.fname else ''))
    else:
        cmds += [
            'call (PyGILState_STATE)PyGILState_Ensure()',
            ('call (int)PyRun_SimpleString("' +
             'import sys\\nif \\"{path}\\" not in sys.path: ' +
             'sys.path.insert(0,\\"{path}\\")\\n' +
             'import pptop.injection;pptop.injection.start(' +
             '{mypid},{protocol}{lg})")').format(
                 path=libpath,
                 mypid=os.getpid(),
                 lg='' if not log_config.fname else ',lg=\\"{}\\"'.format(
                     log_config.fname),
                 protocol=_d.protocol), ' call (void)PyGILState_Release($1)'
        ]
    args = [gdb, '-p', str(pid), '--batch'
           ] + ['--eval-command={}'.format(c) for c in cmds]
    log(args)
    p = subprocess.Popen(args,
                         shell=False,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    log(out)
    log(err)
    if p.returncode:
        raise RuntimeError(err)


def inject_plugin(plugin):
    if plugin['p'].injected is False:
        log('injecting plugin {}'.format(plugin['p'].name))
        plugin['p'].injected = True
        try:
            command('.inject', plugin['i'])
            return True
        except:
            print_message('Plugin injection failed', color=palette.ERROR)
            return False


def switch_plugin(new_plugin):
    if _d.current_plugin:
        if _d.current_plugin is new_plugin:
            return
        if not _d.current_plugin['p'].background:
            _d.current_plugin['p'].stop(wait=False)
        else:
            _d.current_plugin['p'].hide()
    p = new_plugin['p']
    p._previous_plugin = _d.current_plugin
    p.key_event = None
    p.key_code = None
    inject_plugin(new_plugin)
    if not p.is_active(): p.start()
    p.show()
    with plugin_lock:
        _d.current_plugin = new_plugin


def run():

    def autostart_plugins():
        for plugin in plugins_autostart:
            if plugin['p'] is not _d.current_plugin.get('p'):
                log('autostarting {}'.format(plugin['m']))
                inject_plugin(plugin)
                p = plugin['p']
                if p.background:
                    p.start()

    try:

        if not _d.work_pid:
            init_curses(initial=True,
                        after_resize=after_resize,
                        colors=config['display'].get('colors'),
                        glyphs=config['display'].get('glyphs'))
            p = select_process()
        else:
            p = psutil.Process(_d.work_pid)

        if not p: return

        _d.process = p

        client.settimeout(socket_timeout)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, socket_buf)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, socket_buf)
        if _d.need_inject_server:
            inject_server(_d.gdb, p)
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

        frame = b''
        with client_lock:
            time_start = time.time()
            while len(frame) < 1:
                data = client.recv(1)
                if data:
                    frame += data
                    if time.time() > time_start + socket_timeout:
                        raise CriticalException('Socket timeout')

        server_protocol = struct.unpack('b', frame)[0]

        if server_protocol < _d.protocol:
            if _d.force_protocol:
                raise RuntimeError(
                    'Process doesn\'t support protocol {}'.format(_d.protocol))
            else:
                _d.protocol = server_protocol
                log('Falling back to protocol {}'.format(_d.protocol))

        if _d.exec_code:
            end_curses()
            result = command('.x', _d.exec_code)
            if result[0] == 0:
                if _d.output_as_json:
                    print_json(result[1])
                else:
                    print(result[1] if result[1] else '')
            else:
                print(err('{}: {}'.format(result[1], result[2])))
            return

        init_curses(initial=True,
                    after_resize=after_resize,
                    colors=config['display'].get('colors'),
                    glyphs=config['display'].get('glyphs'))

        signal.signal(signal.SIGWINCH, sigwinch_handler)

        calc_bw.start()
        update_status.start()
        if _d.grab_stdout:
            grab_stdout.start()

        _d.process_path.clear()
        plugin_process_path.clear()
        if _d.grab_stdout:
            try:
                command('.gs')
            except:
                raise RuntimeError('Unable to set stdout grabber')
        ppath = []
        for i in command('.path'):
            ppath.append(os.path.abspath(i))
        _d.process_path.extend(sorted(ppath, reverse=True))
        plugin_process_path.extend(_d.process_path)
        log('process path: {}'.format(_d.process_path))
        switch_plugin(_d.default_plugin)
        recalc_info_col_pos()
        show_process_info.start(p=p)
        show_bottom_bar.start()
        neotasker.spawn(autostart_plugins)
        log('main loop started')
        while True:
            try:
                try:
                    k = format_key(scr.stdscr.getkey())
                    event = get_key_event(k)
                except KeyboardInterrupt:
                    return
                except curses.error:
                    resize_handler.trigger_threadsafe(force=True)
                    continue
                if show_process_info.is_stopped():
                    return
                elif k in plugin_shortcuts:
                    switch_plugin(plugin_shortcuts[k])
                elif event == 'ready':
                    try:
                        result = command('.ready')
                    except:
                        result = None
                    with scr.lock:
                        if result:
                            print_message('Ready event sent', color=palette.OK)
                        else:
                            print_message('Command failed', color=palette.ERROR)
                elif event == 'reinject' and \
                        _d.current_plugin['p'].injected is not None:
                    try:
                        result = command('.inject', _d.current_plugin['i'])
                    except:
                        result = None
                    with scr.lock:
                        if result:
                            print_message('Plugin re-injected',
                                          color=palette.OK)
                        else:
                            print_message('Plugin re-injection failed',
                                          color=palette.ERROR)
                elif event == 'quit':
                    _d.current_plugin['p'].stop(wait=False)
                    show_process_info.stop(wait=False)
                    show_bottom_bar.stop(wait=False)
                    return
                elif event == 'console':
                    with scr.lock:
                        end_curses()
                        if _d.grab_stdout: print_stdout.start()
                        cli_mode()
                        if _d.grab_stdout: print_stdout.stop()
                        init_curses(after_resize=after_resize)
                        resize_term()
                elif event == 'show-console':
                    with scr.lock:
                        end_curses()
                        hide_cursor()
                        if _d.grab_stdout: print_stdout.start()
                        try:
                            wait_key()
                        except KeyboardInterrupt:
                            pass
                        if _d.grab_stdout: print_stdout.stop()
                        init_curses(after_resize=after_resize)
                        resize_term()
                elif event == 'filter':
                    apply_filter(_d.current_plugin['p'])
                elif event == 'interval':
                    apply_interval(_d.current_plugin['p'])
                elif event == 'pause':
                    with scr.lock:
                        _d.current_plugin['p'].toggle_pause()
                elif event in _d.current_plugin['p'].inputs:
                    with scr.lock:
                        try:
                            prev_value = _d.current_plugin['p'].get_input(event)
                        except ValueError:
                            continue
                        value = prompt(
                            ps=_d.current_plugin['p'].get_input_prompt(event),
                            value=prev_value if prev_value is not None else '')
                        _d.current_plugin['p'].inputs[event] = value
                        try:
                            _d.current_plugin['p'].handle_input(
                                event, value, prev_value)
                        except:
                            pass
                else:
                    for i, plugin in plugins.items():
                        try:
                            plugin['p'].handle_key_global_event(event, k)
                        except:
                            log_traceback()
                    with scr.lock:
                        _d.current_plugin['p'].key_code = k
                        _d.current_plugin['p'].key_event = event
                        _d.current_plugin['p'].trigger_threadsafe()
            except:
                log_traceback()
                return
    except:
        log_traceback()
        raise
    finally:
        end_curses()


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
    ap.add_argument('-V',
                    '--version',
                    help='Print version and exit',
                    action='store_true')
    ap.add_argument('-R',
                    '--raw',
                    help='Raw mode (disable colors and unicode glyphs)',
                    action='store_true')
    ap.add_argument('--disable-glyphs',
                    help='disable unicode glyphs',
                    action='store_true')
    ap.add_argument('file',
                    nargs='?',
                    help='File, PID file or PID',
                    metavar='FILE/PID')
    ap.add_argument('-a', '--args', metavar='ARGS', help='Child args (quoted)')
    ap.add_argument('--python',
                    metavar='FILE',
                    help='Python interpreter to launch file')
    ap.add_argument('--gdb', metavar='FILE', help='Path to gdb')
    ap.add_argument('-p',
                    '--protocol',
                    metavar='VER',
                    type=int,
                    help=textwrap.dedent('''Pickle protocol, default is highest.
                4: Python 3.4+,
                3: Python 3.0+,
                2: Python 2.3+,
                1: vintage'''))
    ap.add_argument('--inject-method',
                    choices=['auto', 'native', 'loadcffi', 'unsafe'],
                    help='Inject method')
    ap.add_argument('-g',
                    '--grab-stdout',
                    help='Grab stdout/stderr of injected process',
                    action='store_true')
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
    ap.add_argument('-d',
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
        help='Exec code from a file ("-" for stdin) and exit '
            ' (the code can put result to "out" var)',
        metavar='FILE',
        dest='_exec')
    ap.add_argument('-J',
                    '--json',
                    help='Output exec result as JSON',
                    action='store_true')

    try:
        import argcomplete
        argcomplete.autocomplete(ap)
    except:
        pass

    a = ap.parse_args()

    if a.log:
        log_config.fname = a.log
        log_config.name = 'client:{}'.format(os.getpid())
        logging.getLogger('asyncio').setLevel(logging.DEBUG)
        logging.getLogger('neotasker').setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
        le = logging.getLogger()
        le.addHandler(ppLoghandler())
        list(map(le.removeHandler, le.handlers))
        neotasker.set_debug(True)
        init_logging()

    if a.version:
        print(_me)
        exit()

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

    if a.grab_stdout:
        _d.grab_stdout = True

    if a.raw or a.disable_glyphs:
        config['display']['glyphs'] = False

    if a._exec:
        if a._exec == '-':
            _d.exec_code = sys.stdin.read()
        else:
            with open(a._exec) as fd:
                _d.exec_code = fd.read()
        _d.output_as_json = a.json

    else:
        ebk = {}
        global_keys = config.get('keys')
        if global_keys:
            for event, keys in global_keys.items():
                for k, v in events_by_key.copy().items():
                    if event == v:
                        del events_by_key[k]
                if keys is not None:
                    for k in keys if isinstance(keys, list) else [keys]:
                        ebk[str(k)] = str(event)

        events_by_key.update(ebk)
        plugin_options = {}

        for x in a.plugin_options or []:
            try:
                o, v = x.split('=', 1)
            except:
                o = x
                v = None
            format_plugin_option(plugin_options, o, v)

        if plugin_options:
            config.update(merge_dict(config, {'plugins': plugin_options}))

        log('loading plugins')

        try:
            plugins.clear()
            for i, v in config.get('plugins', {}).items():
                try:
                    log('+ plugin ' + i)
                    if v is None: v = {}
                    try:
                        mod = importlib.import_module('pptop.plugins.' + i)
                        mod.__version__ = 'built-in'
                    except ModuleNotFoundError:
                        mod = importlib.import_module('pptopcontrib.' + i)
                        try:
                            mod.__version__
                        except:
                            raise RuntimeError(
                                'Please specify __version__ in plugin file')
                    plugin = {'m': mod}
                    plugins[i] = plugin
                    p = mod.Plugin(interval=float(
                        v.get('interval', mod.Plugin.default_interval)))
                    p.command = command
                    p.get_plugins = get_plugins
                    p.get_plugin = get_plugin
                    p.get_config_dir = get_config_dir
                    p.switch_plugin = switch_plugin
                    p.get_process = get_process
                    p.get_process_path = get_process_path
                    p.global_config = config
                    plugin['p'] = p
                    plugin['id'] = i
                    p._inject = partial(inject_plugin, plugin=plugin)
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
                        p.injected = False
                        plugin['i'] = injection
                    else:
                        p.injected = None
                    if not _d.default_plugin or val_to_boolean(
                            v.get('default')) or i == a.plugin:
                        _d.default_plugin = plugin
                    p_cfg = v.get('config')
                    p.config = {} if p_cfg is None else p_cfg
                    p.on_load()
                    p._on_load()
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
                    if 'cursor' in v:
                        p._cursor_enabled_by_user = val_to_boolean(v['cursor'])
                    if val_to_boolean(v.get('autostart')):
                        plugins_autostart.append(plugin)
                except Exception as e:
                    raise RuntimeError('plugin {}: {}'.format(i, e))
        except:
            log_traceback()
            raise
    neotasker.task_supervisor.start()
    neotasker.task_supervisor.create_aloop('pptop', default=True, daemon=True)
    neotasker.task_supervisor.create_aloop('service', daemon=True)
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
            if a.protocol is not None:
                args += ('-p', str(a.protocol))
            if a.args:
                args += ('-a', a.args)
            if log_config.fname:
                args += ('--log', log_config.fname)
            log('starting child process')
            _d.child = subprocess.Popen(args,
                                        shell=False,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            _d.work_pid = _d.child.pid
            _d.protocol = pickle.HIGHEST_PROTOCOL
        else:
            if a.gdb:
                _d.gdb = a.gdb
            else:
                _d.gdb = shutil.which('gdb')
            if not _d.gdb or not os.path.isfile(_d.gdb):
                raise RuntimeError('gdb not found')
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
            if a.protocol is not None:
                if a.protocol > pickle.HIGHEST_PROTOCOL or a.protocol < 1:
                    raise ValueError('Protocol {} is not supported'.format(
                        a.protocol))
                _d.protocol = a.protocol
                _d.force_protocol = a.protocol
            else:
                _d.protocol = pickle.HIGHEST_PROTOCOL
            log('Pickle protocol: {}'.format(_d.protocol))
        run()
        log('terminating')
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
        neotasker.task_supervisor.stop(wait=False, cancel_tasks=True)
    return 0
