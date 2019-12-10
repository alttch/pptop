import os
import shutil
import curses
import neotasker
import threading

from types import SimpleNamespace

from pptop.logger import log, log_traceback

palette = SimpleNamespace(DEFAULT=curses.A_NORMAL,
                          BOLD=curses.A_BOLD,
                          REVERSE=curses.A_REVERSE,
                          DEBUG=curses.A_NORMAL,
                          WARNING=curses.A_BOLD,
                          ERROR=curses.A_BOLD,
                          CRITICAL=curses.A_BOLD,
                          CAPTION=curses.A_BOLD,
                          HEADER=curses.A_REVERSE,
                          CURSOR=curses.A_REVERSE,
                          BAR=curses.A_REVERSE,
                          BAR_OK=curses.A_REVERSE,
                          BAR_WARNING=curses.A_REVERSE | curses.A_BOLD,
                          BAR_ERROR=curses.A_REVERSE | curses.A_BOLD,
                          GREY=curses.A_NORMAL,
                          GREY_BOLD=curses.A_BOLD,
                          DARKGREY=curses.A_NORMAL,
                          DARKGREY_BOLD=curses.A_BOLD,
                          GREEN=curses.A_NORMAL,
                          GREEN_BOLD=curses.A_BOLD,
                          OK=curses.A_BOLD,
                          BLUE=curses.A_NORMAL,
                          BLUE_BOLD=curses.A_BOLD,
                          RED=curses.A_NORMAL,
                          RED_BOLD=curses.A_BOLD,
                          CYAN=curses.A_NORMAL,
                          CYAN_BOLD=curses.A_BOLD,
                          MAGENTA=curses.A_NORMAL,
                          MAGENTA_BOLD=curses.A_BOLD,
                          YELLOW=curses.A_NORMAL,
                          YELLOW_BOLD=curses.A_BOLD,
                          WHITE=curses.A_NORMAL,
                          WHITE_BOLD=curses.A_BOLD,
                          PROMPT=curses.A_BOLD,
                          color=curses.color_pair)

glyph = SimpleNamespace(UPLOAD='<',
                        DOWNLOAD='>',
                        ARROW_UP='|',
                        ARROW_DOWN='|',
                        SELECTOR='>',
                        CONNECTION='=',
                        DOWNWARDS_LEFT_ARROW='-\'',
                        DOWNWARDS_RIGHT_ARROW='`-',
                        UPWARDS_LEFT_ARROW='-,',
                        UPWARDS_RIGHT_ARROW='.-')

scr = SimpleNamespace(stdscr=None,
                      infowin=None,
                      active=False,
                      before_resize=None,
                      after_resize=None,
                      lock=threading.Lock(),
                      top_lines=6)

tput = shutil.which('tput')
term = os.getenv('TERM')
if not term: term = ''


def init_color_palette(force256=False):
    if term.endswith('256color') or force256:
        log('initializing terminal palette with 256 colors')
        palette.DARKGREY = curses.color_pair(238)
        palette.DARKGREY_BOLD = curses.color_pair(238) | curses.A_BOLD
        palette.DEBUG = curses.color_pair(244)
        palette.WARNING = curses.color_pair(187) | curses.A_BOLD
        palette.ERROR = curses.color_pair(198) | curses.A_BOLD
        palette.CRITICAL = curses.color_pair(197) | curses.A_BOLD
        palette.HEADER = curses.color_pair(37) | curses.A_REVERSE
        palette.CURSOR = curses.color_pair(32) | curses.A_REVERSE
        palette.BAR = curses.color_pair(37) | curses.A_REVERSE
        palette.BAR_OK = curses.color_pair(29) | curses.A_REVERSE
        palette.BAR_WARNING = curses.color_pair(4) | curses.A_REVERSE
        palette.BAR_ERROR = curses.color_pair(198) | curses.A_REVERSE
        palette.GREY = curses.color_pair(244)
        palette.GREY_BOLD = curses.color_pair(244) | curses.A_BOLD
        palette.GREEN = curses.color_pair(41)
        palette.GREEN_BOLD = curses.color_pair(41) | curses.A_BOLD
        palette.OK = curses.color_pair(121) | curses.A_BOLD
        palette.BLUE = curses.color_pair(40)
        palette.BLUE_BOLD = curses.color_pair(40) | curses.A_BOLD
        palette.RED = curses.color_pair(198)
        palette.RED_BOLD = curses.color_pair(198) | curses.A_BOLD
        palette.CYAN = curses.color_pair(51)
        palette.CYAN_BOLD = curses.color_pair(51) | curses.A_BOLD
        palette.MAGENTA = curses.color_pair(208)
        palette.MAGENTA_BOLD = curses.color_pair(208) | curses.A_BOLD
        palette.YELLOW = curses.color_pair(187)
        palette.YELLOW_BOLD = curses.color_pair(187) | curses.A_BOLD
        palette.WHITE_BOLD = curses.color_pair(231) | curses.A_BOLD
        palette.PROMPT = curses.color_pair(76) | curses.A_BOLD
    else:
        log('initializing terminal palette with 16 colors')
        palette.DARKGREY = curses.color_pair(1)
        palette.DARKGREY_BOLD = curses.color_pair(1) | curses.A_BOLD
        palette.DEBUG = curses.color_pair(1) | curses.A_BOLD
        palette.WARNING = curses.color_pair(4) | curses.A_BOLD
        palette.ERROR = curses.color_pair(2) | curses.A_BOLD
        palette.CRITICAL = curses.color_pair(2) | curses.A_BOLD
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
        palette.RED = curses.color_pair(2)
        palette.RED_BOLD = curses.color_pair(2) | curses.A_BOLD
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
    glyph.DOWNWARDS_LEFT_ARROW = '↲ '
    glyph.DOWNWARDS_RIGHT_ARROW = ' ↳'
    glyph.UPWARDS_LEFT_ARROW = '↰ '
    glyph.UPWARDS_RIGHT_ARROW = ' ↱'


def init_curses(initial=False,
                before_resize=None,
                after_resize=None,
                colors=False,
                glyphs=False):
    if not scr.active:
        scr.stdscr = curses.initscr()
        scr.infowin = curses.newwin(scr.top_lines - 1,
                                    scr.stdscr.getmaxyx()[1], 0, 0)
        scr.active = True
        scr.before_resize = before_resize
        scr.after_resize = after_resize
        resize_handler.start()
        if initial:
            if curses.has_colors():
                if colors:
                    curses.start_color()
                    curses.use_default_colors()
                    for i in range(0, curses.COLORS):
                        curses.init_pair(i + 1, i, -1)
                    init_color_palette(force256=colors == 256)
            if glyphs:
                init_glyphs()
        curses.noecho()
        curses.cbreak()
        scr.stdscr.keypad(True)
        hide_cursor()
        return True


def end_curses():
    if scr.active:
        resize_handler.stop()
        curses.nocbreak()
        scr.stdscr.keypad(False)
        curses.echo()
        show_cursor()
        curses.endwin()
        scr.active = False


def set_cursor(mode):
    if (term.startswith('screen') or not scr.active) and tput:
        try:
            code = os.system(tput + ' ' + ('civis' if not mode else 'cnorm'))
            if code:
                raise RuntimeError('tput error code: {}'.format(code))
            return
        except:
            log_traceback()
    try:
        curses.curs_set(mode)
    except:
        pass


def hide_cursor():
    return set_cursor(0)


def show_cursor():
    return set_cursor(2)


def prompt(ps=None, value=''):
    if ps is None:
        ps = ': '
    height, width = scr.stdscr.getmaxyx()
    scr.stdscr.addstr(scr.top_lines + 1, 0, ' ' + ps, palette.PROMPT)
    editwin = curses.newwin(1, width - len(ps) - 1, scr.top_lines + 1,
                            len(ps) + 1)
    from curses.textpad import Textbox
    show_cursor()
    editwin.addstr(0, 0, str(value))
    box = Textbox(editwin, insert_mode=True)
    scr.stdscr.refresh()
    box.edit(enter_is_terminate)
    result = box.gather().rstrip()
    hide_cursor()
    scr.stdscr.move(scr.top_lines + 1, 0)
    scr.stdscr.clrtoeol()
    scr.stdscr.refresh()
    return result


def print_debug(msg):
    scr.stdscr.addstr(scr.top_lines + 1, 0, '"{}"'.format(msg))
    scr.stdscr.clrtoeol()
    scr.stdscr.refresh()


def enter_is_terminate(x):
    if x == 10:
        x = 7
    return x


def cls():
    if scr.stdscr:
        scr.stdscr.clear()


def print_message(msg='', color=None):
    if scr.stdscr:
        height, width = scr.stdscr.getmaxyx()
        scr.stdscr.addstr(scr.top_lines + 1, 0,
                          str(msg)[:width - 1],
                          color if color else palette.DEFAULT)
        scr.stdscr.clrtoeol()
        scr.stdscr.refresh()


def resize_term():
    # works in 100% cases
    if scr.stdscr:
        if scr.before_resize: scr.before_resize()
        width, height = os.get_terminal_size(0)
        curses.resizeterm(height, width)
        scr.stdscr.resize(height, width)
        cls()
        if scr.after_resize: scr.after_resize()


def after_resize():
    pass


@neotasker.background_worker(event=True, loop='service')
def resize_handler(**kwargs):
    log('resize event')
    with scr.lock:
        resize_term()
