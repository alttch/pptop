import re
import pickle
import curses
import tabulate
import sys

from atasker import BackgroundIntervalWorker


class GenericPlugin(BackgroundIntervalWorker):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor = 0
        self.shift = 0
        self.hshift = 0
        mod = sys.modules[self.__module__]
        self.name = mod.__name__.rsplit('.', 1)[-1]
        self.title = None
        self.short_name = None
        self.stdscr = None  # ncurses stdscr object
        self.data = []

    def on_load(self):
        pass

    def on_unload(self):
        pass

    def handle_pager_event(self, window):
        height, width = window.getmaxyx()
        max_pos = len(self.data) - 1
        if self.key_event:
            if self.key_event == 'KEY_DOWN':
                self.cursor += 1
                if self.cursor > max_pos:
                    self.cursor = max_pos
                if self.cursor - self.shift >= height - 1:
                    self.shift += 1
            elif self.key_event == 'KEY_UP':
                self.cursor -= 1
            elif self.key_event == 'KEY_LEFT':
                self.hshift -= 1
                if self.hshift < 0:
                    self.hshift = 0
            elif self.key_event == 'KEY_RIGHT':
                self.hshift += 1
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

    def print_section_title(self):
        height, width = self.stdscr.getmaxyx()
        self.stdscr.addstr(3, 0, ' ' + self.title.ljust(width - 1),
                           curses.color_pair(4) | curses.A_BOLD)
        self.stdscr.move(4, 0)
        self.stdscr.clrtoeol()

    def print_empty_sep(self):
        height, width = self.stdscr.getmaxyx()
        self.stdscr.addstr(4, 0, ' ' * (width - 1),
                           curses.color_pair(3) | curses.A_REVERSE)

    def load_data(self):
        try:
            self.data = pickle.loads(self.command(self.name))
            return True
        except:
            return False

    def prepare_data(self):
        return True

    def get_render_window(self):
        height, width = self.stdscr.getmaxyx()
        return curses.newwin(height - 6, width, 5, 0)

    def start(self, *args, **kwargs):
        super().start(*args, **kwargs)
        if self.title is None:
            self.title = self.name.capitalize()
        if self.short_name is None:
            self.short_name = self.name[:6].capitalize()
        with self.scr_lock:
            self.print_section_title()
        self.on_start()

    def stop(self, *args, **kwargs):
        super().stop(*args, **kwargs)
        with self.scr_lock:
            self.stdscr.move(3, 0)
            self.stdscr.clrtoeol()
            self.stdscr.refresh()
        self.on_stop()

    def on_start(self):
        pass

    def on_stop(self):
        pass

    def handle_key_event(self, event, window):
        pass

    def run(self, **kwargs):
        if not self.load_data() or not self.prepare_data():
            return False
        with self.scr_lock:
            window = self.get_render_window()
            self.handle_pager_event(window)
            self.handle_key_event(self.key_event, window)
            if self.key_event:
                self.key_event = None
            self.render(window)
            window.refresh()

    def render(self, window):
        height, width = window.getmaxyx()
        fancy_tabulate(
            window,
            self.data[self.shift:self.shift + height - 1],
            cursor=self.cursor - self.shift,
            hshift=self.hshift)


def format_mod_name(f, path):
    for p in path:
        if f.startswith(p):
            f = f[len(p) + 1:]
            break
    if f.endswith('.py'):
        f = f[:-3]
    return f.replace('/', '.')


def fancy_tabulate(stdscr, table, cursor=None, hshift=0):

    def format_str(s, width):
        return s[hshift:].ljust(width - 1)[:width - 1]

    height, width = stdscr.getmaxyx()
    if table:
        d = tabulate.tabulate(table, headers='keys').split('\n')
        stdscr.addstr(0, 0, format_str(d[0], width),
                      curses.color_pair(3) | curses.A_REVERSE)
        for i, t in enumerate(d[2:]):
            stdscr.addstr(
                1 + i, 0, format_str(t, width),
                curses.color_pair(7) | curses.A_REVERSE
                if cursor == i else curses.A_NORMAL)
    else:
        stdscr.addstr(0, 0, ' ' * (width - 1),
                      curses.color_pair(3) | curses.A_REVERSE)
    stdscr.clrtobot()


ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')


def ansi_to_plain(txt):
    return ansi_escape.sub('', txt)


def print_ansi_str(stdscr, txt):
    stdscr.addstr(ansi_to_plain(txt))
    stdscr.clrtoeol()

from pptop.core import start
