from pptop import GenericPlugin

import os
import curses


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

    def start(self, *args, **kwargs):
        self.row_colors = {
            'DEBUG': curses.color_pair(1) | curses.A_BOLD,
            'WARNING': curses.color_pair(4) | curses.A_BOLD,
            'ERROR': curses.color_pair(2) | curses.A_BOLD,
            'CRITICAL': curses.color_pair(2) | curses.A_BOLD | curses.A_BOLD
        }
        super().start(*args, **kwargs)

    def get_table_row_color(self, element=None, raw=None):
        return self.row_colors.get(element['level'])


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
