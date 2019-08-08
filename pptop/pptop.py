#!/usr/bin/env python3

__author__ = "Altertech Group, http://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech Group"
__license__ = "MIT"
__version__ = "0.0.1"

import psutil
import os
import time
import tabulate

import curses

import atasker
import threading

import logging

from types import SimpleNamespace

logging.getLogger('asyncio').setLevel(logging.CRITICAL)

work_pid = None


def select_process(stdscr):
    stdscr.clear()
    curses.curs_set(0)
    if curses.can_change_color():
        curses.init_color(0, 0, 0, 0)
    height, width = stdscr.getmaxyx()
    stdscr.addstr(0, 0, 'Select process', curses.color_pair(5) | curses.A_BOLD)
    stdscr.addstr(1, 0, '-' * width, curses.color_pair(9))
    index = 0
    processes = []
    for p in psutil.process_iter():
        name = p.name()
        if name in ['python', 'python3'] and p.pid != os.getpid():
            processes.append(p)

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


@atasker.background_worker(delay=1)
def show_process_info(stdscr, p, **kwargs):
    height, width = stdscr.getmaxyx()
    with scr_lock:
        try:
            ct = p.cpu_times()
            stdscr.move(0, 0)
            stdscr.addstr('Process: ')
            stdscr.addstr(' '.join(p.cmdline()), curses.color_pair(4))
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
            stdscr.clrtoeol()
            stdscr.refresh()
        except psutil.NoSuchProcess:
            stdscr.clear()
            stdscr.addstr(0, 0, 'Process is gone', curses.color_pair(2))
            stdscr.refresh()
            return False


def print_section_title(stdscr, title):
    height, width = stdscr.getmaxyx()
    stdscr.addstr(3, 0, ' ' + title.ljust(width - 1),
                  curses.color_pair(3) | curses.A_REVERSE)


def fancy_tabulate(stdscr, table):
    if table:
        d = tabulate.tabulate(table, headers='keys').split('\n')
        stdscr.addstr(4, 0, d[0], curses.color_pair(5))
        stdscr.addstr(5, 0, d[1], curses.color_pair(9))
        stdscr.addstr(6, 0, '\n'.join(d[2:]))


@atasker.background_worker(delay=1)
def show_function_profiler(stdscr, p, **kwargs):
    height, width = stdscr.getmaxyx()
    with scr_lock:
        print_section_title(stdscr, 'Profiler')
        stdscr.clrtobot()
        stdscr.refresh()


@atasker.background_worker(delay=1)
def show_open_files(stdscr, p, **kwargs):
    height, width = stdscr.getmaxyx()
    files = []
    for f in p.open_files():
        files.append({
            'path': f.path,
            'fd': f.fd,
            'pos.': f.position,
            'mode': f.mode
        })
    with scr_lock:
        print_section_title(stdscr, 'Files')
        files = sorted(files, key=lambda k: k['path'])
        fancy_tabulate(stdscr, files)
        stdscr.clrtobot()
        stdscr.refresh()


_d = SimpleNamespace(current_worker=None)


def main(stdscr):

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
    height, width = stdscr.getmaxyx()
    stdscr.clear()
    curses.curs_set(0)
    switch_worker(show_function_profiler)
    atasker.background_task(show_process_info.start)(stdscr=stdscr, p=p)
    worker_shortcuts = {'f': show_open_files, 'p': show_function_profiler}
    while True:
        try:
            k = stdscr.getkey()
            if not show_process_info.is_active():
                return
            if k == 'q':
                return
            elif k in worker_shortcuts:
                switch_worker(worker_shortcuts[k])
            else:
                show_process_info.trigger()
        except:
            raise
            return


atasker.task_supervisor.start()
# work_pid = 114958
curses.wrapper(main)
atasker.task_supervisor.stop(wait=False)
