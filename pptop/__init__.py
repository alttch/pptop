__author__ = "Altertech, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech"
__license__ = "MIT"
__version__ = "0.0.19"

import re
import curses
import tabulate
import sys
import os
import readline
import threading

from types import SimpleNamespace

from atasker import BackgroundIntervalWorker
from atasker import background_task

from pptop.logger import log, log_traceback

top_lines = 5

tabulate.PRESERVE_WHITESPACE = True

palette = SimpleNamespace(
    DEFAULT=curses.A_NORMAL,
    BOLD=curses.A_BOLD,
    REVERSE=curses.A_REVERSE,
    DEBUG=curses.A_NORMAL,
    WARNING=curses.A_BOLD,
    ERROR=curses.A_BOLD,
    CAPTION=curses.A_BOLD,
    HEADER=curses.A_REVERSE,
    CURSOR=curses.A_REVERSE,
    BAR=curses.A_REVERSE,
    BAR_OK=curses.A_REVERSE,
    BAR_WARNING=curses.A_REVERSE | curses.A_BOLD,
    BAR_ERROR=curses.A_REVERSE | curses.A_BOLD,
    GREY=curses.A_NORMAL,
    GREY_BOLD=curses.A_BOLD,
    GREEN=curses.A_NORMAL,
    GREEN_BOLD=curses.A_BOLD,
    OK=curses.A_BOLD,
    BLUE=curses.A_NORMAL,
    BLUE_BOLD=curses.A_BOLD,
    CYAN=curses.A_NORMAL,
    CYAN_BOLD=curses.A_BOLD,
    MAGENTA=curses.A_NORMAL,
    MAGENTA_BOLD=curses.A_BOLD,
    YELLOW=curses.A_NORMAL,
    YELLOW_BOLD=curses.A_BOLD,
    WHITE=curses.A_NORMAL,
    WHITE_BOLD=curses.A_BOLD,
    PROMPT=curses.A_BOLD)

glyph = SimpleNamespace(
    upload='<',
    download='>',
    arrow_up='|',
    arrow_down='|',
    selector='>',
)


class CriticalException(Exception):
    pass


class GenericPlugin(BackgroundIntervalWorker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor = 0
        self.shift = 0
        self.hshift = 0
        mod = sys.modules[self.__module__]
        self.name = mod.__name__.rsplit('.', 1)[-1]
        if self.name.startswith('pptopcontrib-'):
            self.name = self.name[13:]
        self.title = self.name.capitalize().replace('_', ' ')
        self.short_name = self.name[:6].capitalize()
        self.stdscr = None  # curses stdscr object
        self.data = []
        self.config = {}
        self.filter = ''
        self.description = ''
        self.sorting_col = None
        self.sorting_rev = True
        self.sorting_enabled = True
        self.cursor_enabled = True
        self.selectable = False
        self.window = None
        self.background = False
        self.background_loader = False
        self._visible = False
        self.append_data = False
        self.data_records_max = None
        self._paused = False
        self._error = False
        self.msg = ''
        self._loader_active = False
        self.data_lock = threading.Lock()
        # key - hot key, value - input value
        self.inputs = {}
        self.input_prompts = {}

    def on_load(self):
        '''
        Executed on plugin load (on pptop startup)
        '''
        pass

    def on_unload(self):
        '''
        Executed on plugin unload (on pptop shutdown)
        '''
        pass

    def get_process(self):
        '''
        Get connected process

        Returns:
            psutil.Process object
        '''
        return None

    def get_process_path(self):
        '''
        Get sys.path of connected process

        Useful e.g. to format module names

        Returns:
            sys.path object
        '''
        return None

    def command(cmd, params=None):
        '''
        Execute command on connected process

        Args:
            cmd: command to execute
            params: command params (optional, free format dict)
        '''
        return None

    def handle_sorting_event(self):
        if self.sorting_enabled:
            if self.key_event in ['kLFT3', 'kRIT3']:
                if self.data:
                    cols = list(self.data[0])
                    if not self.sorting_col:
                        self.sorting_col = cols[0]
                    try:
                        pos = cols.index(self.sorting_col)
                        pos += 1 if self.key_event == 'kRIT3' else -1
                        if pos > len(cols) - 1:
                            pos = 0
                        elif pos < 0:
                            pos = len(cols) - 1
                        self.sorting_col = cols[pos]
                    except:
                        pass
            elif self.key_event == 'kDN3':
                self.sorting_rev = False
            elif self.key_event == 'kUP3':
                self.sorting_rev = True

    def handle_pager_event(self, dtd):
        '''
        Pager event handler
        '''
        height, width = self.window.getmaxyx()
        max_pos = len(dtd) - 1
        if max_pos < 0: max_pos = 0
        if self.key_event:
            if self.key_event == 'KEY_LEFT':
                self.hshift -= 1
                if self.hshift < 0:
                    self.hshift = 0
            elif self.key_event == 'kLFT5':
                self.hshift -= 20
                if self.hshift < 0:
                    self.hshift = 0
            elif self.key_event == 'KEY_RIGHT':
                self.hshift += 1
            elif self.key_event == 'kRIT5':
                self.hshift += 20
            if self.key_event == 'KEY_DOWN':
                if self.cursor_enabled:
                    self.cursor += 1
                    if self.cursor > max_pos:
                        self.cursor = max_pos
                    if self.cursor - self.shift >= height - 1:
                        self.shift += 1
                else:
                    self.cursor += 1
                    self.shift += 1
            elif self.key_event == 'KEY_UP':
                if self.cursor_enabled:
                    self.cursor -= 1
                else:
                    self.cursor -= 1
                    self.shift -= 1
            elif self.key_event == 'KEY_NPAGE':
                self.cursor += height - 1
                self.shift += height - 1
            elif self.key_event == 'KEY_PPAGE':
                self.cursor -= height + 1
                self.shift -= height + 1
            elif self.key_event == 'KEY_HOME':
                self.hshift = 0
                self.cursor = 0
                self.shift = 0
            elif self.key_event == 'KEY_END':
                self.cursor = max_pos
                self.shift = max_pos - height + 2
            if self.cursor < 0:
                self.shift -= 1
                self.cursor = 0
            if self.cursor - self.shift < 0:
                self.cursor = self.shift - 1
                if self.cursor < 0: self.cursor = 0
                self.shift -= 1
            if self.shift < 0:
                self.shift = 0
        if max_pos == 0:
            self.cursor = 0
            self.shift = 0
        else:
            if self.cursor > max_pos:
                self.cursor = max_pos
                self.shift = max_pos - height + 2
                if self.shift < 0:
                    self.shift = 0
            if max_pos < height - 1:
                self.shift = 0
                if self.cursor > max_pos:
                    self.cursor = max_pos - 1

    def print_title(self):
        '''
        Print section title
        '''
        title = self.title
        if self._error:
            color = palette.ERROR
            title += ' [ERROR{}]'.format((': ' + self.msg) if self.msg else '')
        elif self._paused:
            color = palette.GREY
            title += ' [PAUSED]'
        elif not self.is_active():
            color = palette.GREY
            title += ' [STOPPED]'
        else:
            color = palette.CAPTION
        height, width = self.stdscr.getmaxyx()
        self.stdscr.addstr(top_lines, 0, title, color)
        self.stdscr.clrtoeol()

    def print_empty_sep(self):
        '''
        Print empty separator instead of table header
        '''
        height, width = self.window.getmaxyx()
        self.window.addstr(0, 0, ' ' * (width - 1), palette.HEADER)

    def injection_command(self, **kwargs):
        '''
        Execute injected function with specified params

        Returns:
            injected function response
        Raises:
            RuntimeError: if command failed
        '''
        return self.command(self.name, params=kwargs)

    def get_injection_load_params(self):
        return {}

    def toggle_pause(self):
        self.resume() if self._paused else self.pause()

    def pause(self):
        with self.scr_lock:
            self._paused = True
            self.print_title()

    def resume(self):
        with self.scr_lock:
            self._paused = False
            self.print_title()

    def _load_data(self):
        try:
            return self.load_data()
        finally:
            self._loader_active = False

    def load_data(self):
        '''
        Load data from connected process

        Default method sends command cmd=<plugin_name>

        Returns:
            if False is returned, the plugin is stopped (doesn't works if
            self.background_loader=True)
        '''
        try:
            result = self.injection_command()
            processed = self.process_data(result)
            if isinstance(processed, list):
                result = processed
            if result is False or processed is False:
                return False
            if isinstance(result, list):
                d = result
            else:
                d = []
            with self.data_lock:
                if self.append_data:
                    self.data += d
                else:
                    self.data = d
                if self.data_records_max and len(
                        self.data) > self.data_records_max:
                    self.data = self.data[len(self.data) -
                                          self.data_records_max:]
            self._error = False
            self._display_ui()
            return True
        except Exception as e:
            log_traceback()
            self.data = []
            with self.scr_lock:
                self._error = True
                self.msg = 'frame error: {}'.format(e)
                if self._visible:
                    self.print_title()

    def process_data(self, data):
        '''
        Format loaded data into table

        Function should either process data list in-place or return new data
        list

        Returns:
            if False is returned, the plugin is stopped
        '''
        pass

    def sort_dtd(self, dtd):
        '''
        Sort data to display

        Returns:
            method should return generator
        '''
        if dtd:
            if not self.sorting_enabled:
                for d in dtd:
                    yield d
            else:
                if not self.sorting_col:
                    self.sorting_col = list(dtd[0])[0]
                for d in sorted(
                        dtd,
                        key=lambda k: k[self.sorting_col],
                        reverse=self.sorting_rev):
                    yield d

    def format_dtd(self, dtd):
        '''
        Format data to display

        Format data before filter is applied and data is rendered, e.g.
        convert timestamps to date/time, numbers to strings

        Returns:
            method should return generator
        '''
        for d in dtd:
            yield d

    def filter_dtd(self, dtd):
        '''
        Apply filter to data to display

        Returns:
            method should return generator
        '''
        if not self.filter:
            for d in dtd:
                yield d
        else:
            self.stdscr.addstr(top_lines + 1, 0, ' f="')
            self.stdscr.addstr(self.filter, palette.BLUE_BOLD)
            self.stdscr.addstr('"')
            self.stdscr.clrtoeol()
            self.stdscr.refresh()
            for d in dtd:
                for k, v in d.items():
                    if str(v).lower().find(self.filter) > -1:
                        yield d
                        break

    def init_render_window(self):
        '''
        Init plugin working window
        '''
        height, width = self.stdscr.getmaxyx()
        self.window = curses.newwin(height - top_lines - 3, width,
                                    top_lines + 2, 0)

    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)
        self.on_start()

    def show(self):
        with self.scr_lock:
            self._visible = True
            self.init_render_window()
            self.print_title()
            self.print_message()
            if self.is_active(): self._display()

    def hide(self):
        with self.scr_lock:
            if self.window:
                self.window.move(0, 0)
                self.window.clrtoeol()
                self._visible = False
                self.stdscr.refresh()

    def stop(self, *args, **kwargs):
        super().stop(*args, **kwargs)
        self.hide()
        self.on_stop()

    def on_start(self):
        '''
        Called after plugin startup
        '''
        pass

    def on_stop(self):
        '''
        Called after plugin shutdown
        '''
        pass

    def resize(self):
        '''
        Automatically called on screen resize
        '''
        with self.scr_lock:
            self.init_render_window()
            self.print_title()
            self.key_event = 'KEY_RESIZE'
            self._display()

    def handle_key_event(self, event, dtd):
        '''
        Handle custom key event

        Args:
            event: curses getkey() event
            dtd: data to be displayed (list)

        Returns:
            can return False to stop plugin
        '''
        return True

    def get_input(self, var):
        return self.inputs.get(var)

    def get_input_prompt(self, var):
        return

    def handle_input(self, var, value, prev_value):
        return

    def print_ok(self, msg=''):
        self.print_message(msg=msg, color=palette.OK)

    def print_error(self, msg=''):
        self.print_message(msg=msg, color=palette.ERROR)

    def print_message(self, msg='', color=None):
        return print_message(self.stdscr, msg=msg, color=color)

    def run(self, **kwargs):
        '''
        Primary plugin executor method
        '''
        try:
            if (not self.key_event or self.key_event == ' '
               ) and not self._paused and not self._loader_active:
                self._loader_active = True
                if self.background_loader:
                    background_task(self._load_data)()
                    return
                else:
                    if self._load_data() is False:
                        return False
            return self._display_ui()
        except Exception as e:
            log_traceback()
            if self._visible:
                with self.scr_lock:
                    self._error = True
                    self.msg = str(e)
                    self.print_title()
            return False

    def get_selected_row(self):
        try:
            return self.dtd[self.cursor]
        except:
            return None

    def delete_selected_row(self):
        self.dtd.remove(self.dtd[self.cursor])

    def _display_ui(self):
        with self.start_stop_lock:
            if self.is_active():
                with self.scr_lock:
                    if self._visible:
                        return self._display()

    def _display(self):
        self.print_title()
        self.stdscr.refresh()
        self.handle_sorting_event()
        with self.data_lock:
            dtd = list(
                self.filter_dtd(
                    dtd=self.format_dtd(dtd=self.sort_dtd(dtd=self.data))))
        self.dtd = dtd
        if self.key_event:
            if not self.filter: self.print_message()
            if self.handle_key_event(event=self.key_event, dtd=dtd) is False:
                return False
        self.handle_pager_event(dtd=dtd)
        if self.key_event:
            self.key_event = None
        if dtd:
            self.render(dtd=dtd)
        else:
            self.print_empty_sep()
            self.window.clrtobot()
        self.window.refresh()
        self.stdscr.refresh()
        return True

    def render(self, dtd):
        '''
        Renders plugin display
        '''
        height, width = self.window.getmaxyx()
        self.tabulate(
            dtd[self.shift:self.shift + height - 1],
            cursor=(self.cursor - self.shift) if self.cursor_enabled else None,
            hshift=self.hshift,
            sorting_col=self.sorting_col,
            sorting_rev=self.sorting_rev,
            print_selector=self.selectable)

    def tabulate(self,
                 table,
                 cursor=None,
                 hshift=0,
                 sorting_col=None,
                 sorting_rev=False,
                 print_selector=False):

        def format_row(element=None, raw=None, max_width=0, hshift=0):
            return self.format_table_row(
                element=element,
                raw=raw)[hshift:].ljust(max_width - 1)[:max_width - 1]

        self.window.move(0, 0)
        self.window.clrtobot()
        height, width = self.window.getmaxyx()
        if table:
            d = tabulate.tabulate(table, headers='keys').split('\n')
            header = d[0]
            if print_selector:
                header = ' ' + header
            if sorting_col:
                if sorting_rev:
                    s = glyph.arrow_up
                else:
                    s = glyph.arrow_down
                if header.startswith(sorting_col + ' '):
                    header = header.replace(sorting_col + ' ', s + sorting_col,
                                            1)
                else:
                    header = header.replace(' ' + sorting_col, s + sorting_col)
            self.window.addstr(
                0, 0, format_row(raw=header, max_width=width, hshift=hshift),
                palette.HEADER)
            for i, (t, r) in enumerate(zip(d[2:], table)):
                if print_selector:
                    t = (glyph.selector if cursor == i else ' ') + t
                self.window.addstr(
                    1 + i, 0,
                    format_row(
                        element=r, raw=t, max_width=width,
                        hshift=hshift), palette.CURSOR if cursor == i else
                    (self.get_table_row_color(r, t) or palette.DEFAULT))
        else:
            self.print_empty_sep()

    def get_table_row_color(self, element=None, raw=None):
        pass

    def format_table_row(self, element=None, raw=None):
        return raw


def format_mod_name(f, path):
    f = os.path.abspath(f)
    child = get_child_info()
    if child and f == child['c']:
        return '__main__'
    for p in path:
        if f.startswith(p):
            f = f[len(p) + 1:]
            break
    if f.endswith('.py'):
        f = f[:-3]
    mod = f.replace('/', '.')
    i = 0
    for i in range(len(mod)):
        if mod[i] != '.': break
    return mod[i:]


def prompt(stdscr, ps=None, value=''):
    if ps is None:
        ps = ': '
    height, width = stdscr.getmaxyx()
    stdscr.addstr(top_lines + 1, 0, ' ' + ps, palette.PROMPT)
    editwin = curses.newwin(1, width - len(ps) - 1, top_lines + 1, len(ps) + 1)
    from curses.textpad import Textbox
    curses.curs_set(2)
    editwin.addstr(0, 0, value)
    box = Textbox(editwin, insert_mode=True)
    stdscr.refresh()
    box.edit(enter_is_terminate)
    result = box.gather().rstrip()
    curses.curs_set(0)
    stdscr.move(top_lines + 1, 0)
    stdscr.clrtoeol()
    stdscr.refresh()
    return result


ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')


def ansi_to_plain(txt):
    return ansi_escape.sub('', txt)


def print_ansi_str(stdscr, txt):
    stdscr.addstr(ansi_to_plain(txt))
    stdscr.clrtoeol()


def print_debug(stdscr, msg):
    stdscr.addstr(top_lines + 1, 0, '"{}"'.format(msg))
    stdscr.clrtoeol()
    stdscr.refresh()


def enter_is_terminate(x):
    if x == 10:
        x = 7
    return x


def print_message(stdscr, msg='', color=None):
    if stdscr:
        height, width = stdscr.getmaxyx()
        stdscr.addstr(top_lines + 1, 0,
                      str(msg)[:width - 1], color if color else palette.DEFAULT)
        stdscr.clrtoeol()
        stdscr.refresh()


from pptop.core import start, get_child_info
