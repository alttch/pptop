from pptop import GenericPlugin

import os


class Plugin(GenericPlugin):
    '''
    log plugin: view process logs
    '''
    pass

    def on_load(self):
        self.data_records_max = 1000
        self.append_data = True
        self.sorting_col = 'time'
        self.sorting_rev = True
        self.background = True

    def process_data(self, data):
        result = []
        for record in data:
            result.append({
                'logger':
                record.name,
                'time':
                record.created,
                'level':
                record.levelno,
                'module':
                record.module,
                'thread':
                record.threadName,
                'file':
                '{}:{}'.format(os.path.abspath(record.pathname), record.lineno),
                'message':
                record.getMessage().replace('\n', ' ')
            })
        return result

    def format_dtd(self, dtd):
        import logging
        from datetime import datetime
        for t in dtd:
            z = t.copy()
            z['time'] = datetime.fromtimestamp(
                z['time']).strftime('%Y-%m-%d %H:%M:%S')
            z['level'] = logging.getLevelName(z['level'])
            yield z

    def fancy_tabulate(self,
                       table,
                       cursor=None,
                       hshift=0,
                       sorting_col=None,
                       sorting_rev=False,
                       print_selector=False):

        import tabulate
        import curses

        def format_str(s, width):
            return s[hshift:].ljust(width - 1)[:width - 1]

        table = list(table)

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
            i = 0
            colors = {
                'DEBUG': curses.color_pair(1) | curses.A_BOLD,
                'WARNING': curses.color_pair(4) | curses.A_BOLD,
                'ERROR': curses.color_pair(2) | curses.A_BOLD,
                'CRITICAL': curses.color_pair(2) | curses.A_BOLD | curses.A_BOLD
            }
            for t, v in zip(d[2:], table):
                color = colors.get(v['level'], curses.A_NORMAL)
                self.window.addstr(
                    1 + i, 0, format_str(t, width),
                    curses.color_pair(0) | curses.A_REVERSE
                    if cursor == i else color)
                i += 1
        else:
            self.window.addstr(0, 0, ' ' * (width - 1),
                               curses.color_pair(3) | curses.A_REVERSE)


def injection_load(**kwargs):
    import logging
    import threading

    class LogHandler(logging.Handler):

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.records = []
            self.records_lock = threading.Lock()

        def emit(self, record):
            if record:
                with self.records_lock:
                    self.records.append(record)

        def get_collected(self):
            with self.records_lock:
                rec = self.records
                self.records = []
            return rec

    g.log_handler = LogHandler()
    g.loggers_injected = [name for name in logging.root.manager.loggerDict]
    if logging.getLogger().name not in g.loggers_injected:
        g.loggers_injected.append(None)
    for l in g.loggers_injected:
        logging.getLogger(l).addHandler(g.log_handler)


def injection_unload(**kwargs):
    import logging
    for l in g.loggers_injected:
        try:
            logging.getLogger(l).removeHandler(g.log_handler)
        except:
            pass


def injection(**kwargs):
    return g.log_handler.get_collected()
