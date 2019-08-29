from pptop.plugin import GenericPlugin, abspath, palette

import os

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    log plugin: view process logs
    '''

    def on_load(self):
        self.description = 'Log viewer (injects into all loggers)'
        self.data_records_max = 1000
        self.append_data = True
        self.sorting_col = 'time'
        self.sorting_rev = True
        self.background = True

    def process_data(self, data):
        result = []
        for record in data:
            r = OrderedDict()
            r['logger'] = record.name
            r['time'] = record.created
            r['level'] = record.levelno
            r['module'] = record.module
            r['thread'] = record.threadName
            r['file'] = '{}:{}'.format(abspath(record.pathname), record.lineno)
            r['message'] = record.getMessage().replace('\n', ' ')
            result.append(r)
        return result

    def format_dtd(self, dtd):
        import logging
        from datetime import datetime
        for t in dtd:
            z = t.copy()
            z['time'] = datetime.fromtimestamp(
                    z['time']).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
            z['level'] = logging.getLevelName(z['level'])
            yield z

    def start(self, *args, **kwargs):
        self.row_colors = {
            'DEBUG': palette.DEBUG,
            'WARNING': palette.WARNING,
            'ERROR': palette.ERROR,
            'CRITICAL': palette.CRITICAL
        }
        super().start(*args, **kwargs)

    def get_table_row_color(self, element=None, raw=None):
        return self.row_colors.get(element['level'])

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection_load(**kwargs):
    import logging
    import threading

    class LogHandler(logging.Handler):

        def __init__(self, *args, **kwargs):
            logging.Handler.__init__(self, *args, **kwargs)
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
    logging.getLogger().addHandler(g.log_handler)


def injection_unload(**kwargs):
    import logging
    logging.getLogger().removeHandler(g.log_handler)


def injection(**kwargs):
    return g.log_handler.get_collected()
