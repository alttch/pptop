__author__ = "Altertech, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech"
__license__ = "MIT"
__version__ = "0.0.2"

import re
import _pickle as cPickle
import curses
import tabulate
import sys
import os
import readline
import threading

from atasker import BackgroundIntervalWorker

tabulate.PRESERVE_WHITESPACE = True

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
        self.title = self.name.capitalize()
        self.short_name = self.name[:6].capitalize()
        self.stdscr = None  # curses stdscr object
        self.data = []
        self.filter = ''
        self.sorting_col = None
        self.sorting_rev = True
        self.sorting_enabled = True
        self.cursor_enabled = True
        self.selectable = False
        self.window = None
        self.background = False
        self._visible = False
        self.append_data = False
        self.data_records_max = None
        self._paused = False
        self._error = False
        self._msg = ''

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
            if max_pos < height:
                self.shift = 0
                if self.cursor > max_pos:
                    self.cursor = max_pos - 1

    def print_title(self, status='', msg=''):
        '''
        Print section title
        '''
        title = self.title
        if self._error:
            color = curses.color_pair(2) | curses.A_BOLD
            title += ' [ERROR{}]'.format((
                ': ' + self._msg) if self._msg else '')
        elif self._paused:
            color = curses.color_pair(1) | curses.A_BOLD
            title += ' [PAUSED]'
        else:
            color = curses.color_pair(4) | curses.A_BOLD
        height, width = self.stdscr.getmaxyx()
        self.stdscr.addstr(3, 0, ' ' + title.ljust(width - 1), color)
        self.stdscr.move(4, 0)
        self.stdscr.clrtoeol()

    def print_empty_sep(self):
        '''
        Print empty separator instead of table header
        '''
        height, width = self.stdscr.getmaxyx()
        self.window.addstr(0, 0, ' ' * (width - 1),
                           curses.color_pair(3) | curses.A_REVERSE)

    def injection_command(self, **kwargs):
        '''
        Execute injected function with specified params

        Returns:
            injected function response
        Raises:
            RuntimeError: if command failed
        '''
        return self.command(self.name, params=kwargs)

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

    def load_data(self):
        '''
        Load data from connected process

        Default method sends command cmd=<plugin_name>

        Returns:
            if False is returned, the plugin is stopped
        '''
        try:
            result = self.process_data(self.injection_command())
            if result is False:
                return False
            if isinstance(result, list):
                d = result
            if self.append_data:
                self.data += d
            else:
                self.data = d
            if self.data_records_max and len(self.data) > self.data_records_max:
                self.data = self.data[len(self.data) - self.data_records_max:]
            self._error = False
            return True
        except Exception as e:
            raise
            self.data = []
            with self.scr_lock:
                self._error = True
                self._msg = 'frame error: {}'.format(e)
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
        return True

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
            self.stdscr.addstr(4, 1, 'f="')
            self.stdscr.addstr(self.filter,
                               curses.color_pair(5) | curses.A_BOLD)
            self.stdscr.addstr('"')
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
        self.window = curses.newwin(height - 6, width, 5, 0)

    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)
        self.on_start()

    def show(self):
        with self.scr_lock:
            self._visible = True
            self.init_render_window()
            self.print_title()
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

    def run(self, **kwargs):
        '''
        Primary plugin executor method
        '''
        if (not self.key_event or self.key_event == ' ') and not self._paused:
            if self.load_data() is False:
                return False
        with self.scr_lock:
            if self._visible:
                return self._display()

    def _display(self):
        self.print_title()
        self.stdscr.refresh()
        self.handle_sorting_event()
        dtd = list(self.filter_dtd(self.format_dtd(self.sort_dtd(self.data))))
        self.dtd = dtd
        self.handle_pager_event(dtd)
        if self.key_event and self.handle_key_event(self.key_event,
                                                    dtd) is False:
            return False
        if self.key_event:
            self.key_event = None
        if dtd:
            self.render(dtd)
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
        self.fancy_tabulate(
            dtd[self.shift:self.shift + height - 1],
            cursor=(self.cursor - self.shift) if self.cursor_enabled else None,
            hshift=self.hshift,
            sorting_col=self.sorting_col,
            sorting_rev=self.sorting_rev,
            print_selector=self.selectable)

    def fancy_tabulate(self,
                       table,
                       cursor=None,
                       hshift=0,
                       sorting_col=None,
                       sorting_rev=False,
                       print_selector=False):

        def format_str(s, width):
            return s[hshift:].ljust(width - 1)[:width - 1]

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
                    s = '↑'
                else:
                    s = '↓'
                if header.startswith(sorting_col + ' '):
                    header = header.replace(sorting_col + ' ', s + sorting_col,
                                            1)
                else:
                    header = header.replace(' ' + sorting_col, s + sorting_col)
            self.window.addstr(0, 0, format_str(header, width),
                               curses.color_pair(3) | curses.A_REVERSE)
            for i, t in enumerate(d[2:]):
                if print_selector:
                    t = ('→' if cursor == i else ' ') + t
                self.window.addstr(
                    1 + i, 0, format_str(t, width),
                    curses.color_pair(7) | curses.A_REVERSE
                    if cursor == i else curses.A_NORMAL)
        else:
            self.window.addstr(0, 0, ' ' * (width - 1),
                               curses.color_pair(3) | curses.A_REVERSE)


def format_mod_name(f, path):
    f = os.path.abspath(f)
    for p in path:
        if f.startswith(p):
            f = f[len(p) + 1:]
            break
    if f.endswith('.py'):
        f = f[:-3]
    mod = f.replace('/', '.')
    for i in range(len(mod)):
        if mod[i] != '.': break
    return mod[i:]


ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')


def ansi_to_plain(txt):
    return ansi_escape.sub('', txt)


def print_ansi_str(stdscr, txt):
    stdscr.addstr(ansi_to_plain(txt))
    stdscr.clrtoeol()


def print_debug(stdscr, msg):
    stdscr.addstr(4, 0, '"{}"'.format(msg))
    stdscr.clrtoeol()
    stdscr.refresh()


from pptop.core import start
