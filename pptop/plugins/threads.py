from pptop.plugin import GenericPlugin, palette
from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    threads plugin: process thread stats

        ident: thread ident (Python)
        daemon: is thread running as daemon
        name: thread name
        target: target function
        ttot: time spent total
        scnt: schedule count

    requires yappi profiler module for times and schedule count
    https://github.com/sumerc/yappi
    '''

    def on_load(self):
        self.short_name = 'Thrds'
        self.sorting_col = 'ttot'
        self.description = 'Process active threads'
        self.background_loader = True

    def process_data(self, data):
        result = []
        for d in data:
            r = OrderedDict()
            r['ident'] = d[0]
            r['daemon'] = 'daemon' if d[1] else ''
            r['name'] = d[2] if d[2] else ''
            r['target'] = d[3] if d[3] else ''
            r['ttot'] = d[4]
            r['scnt'] = d[5]
            r['cmd'] = d[6] if d[6] else ''
            r['file'] = d[7] if d[7] else ''
            result.append(r)
        return result

    def format_dtd(self, dtd):
        for t in dtd:
            z = t.copy()
            z['ttot'] = '{:.3f}'.format(z['ttot'])
            yield z

    def get_table_col_color(self, element, key, value):
        if key == 'ident':
            return palette.YELLOW if not element['daemon'] else None
        elif key == 'daemon':
            return
        elif key == 'name':
            return palette.YELLOW if not element['daemon'] else None
        elif key == 'target':
            return palette.BOLD
        elif key == 'cmd':
            return palette.YELLOW
        elif key == 'file':
            return
        else:
            return palette.CYAN

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection_load(**kwargs):
    import threading
    try:
        import yappi
        if not yappi.is_running():
            yappi.start()
    except:
        pass


def injection_unload(**kwargs):
    try:
        import yappi
        if yappi.is_running():
            yappi.stop()
    except:
        pass


def injection(**kwargs):
    import threading
    import sys
    import linecache
    result = []
    yi = {}
    try:
        import yappi
        if not yappi.is_running():
            yappi.start()
        for d in yappi.get_thread_stats():
            yi[d[2]] = (d[3], d[4])
    except:
        pass
    for t in threading.enumerate():
        if not t.name.startswith('__pptop_injection'):
            try:
                target = '{}.{}'.format(
                    t._target.__module__, t._target.__qualname__ if hasattr(
                        t._target, '__qualname__') else t._target.__name__)
            except:
                target = None
            y = yi.get(t.ident)
            r = (t.ident, t.daemon, t.name, target, y[0] if y else 0,
                 y[1] if y else 0)
            try:
                frame = sys._current_frames()[t.ident]
                f = frame.f_code.co_filename
                ln = frame.f_lineno
                r += (linecache.getline(f, ln).strip(), '{}:{}'.format(f, ln))
            except:
                log_traceback()
                r += (None, None)
            result.append(r)
    return result
