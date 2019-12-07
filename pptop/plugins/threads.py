from pptop.plugin import GenericPlugin, palette, glyph
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

    select thread to view its strack trace

    requires yappi profiler module for times and schedule count
    https://github.com/sumerc/yappi
    '''

    def on_load(self):
        self.short_name = 'Thrds'
        self.sorting_col = 'ttot'
        self.description = 'Process active threads'
        self.background_loader = True
        self.thread_stack_info = None
        self.selectable = True

    def load_remote_data(self):
        if self.thread_stack_info is None:
            self.title = 'Threads'
            return super().load_remote_data()
        else:
            self.title = 'Thread {name} [{ident}] stack trace'.format(
                ident=self.thread_stack_info[0], name=self.thread_stack_info[1])
            return self.injection_command(
                thread_stack_info=self.thread_stack_info[0])

    def process_data(self, data):
        result = []
        if self.thread_stack_info:
            for i, d in enumerate(data):
                r = OrderedDict()
                r['cmd'] = (('   ' * (i - 1) + glyph.DOWNWARDS_RIGHT_ARROW +
                             ' ') if i else '') + d[0]
                r['file'] = d[1]
                result.append(r)
        else:
            for d in data:
                r = OrderedDict()
                r['ident'] = d[0]
                r['daemon'] = 'daemon' if d[1] else ''
                r['name'] = d[2] if d[2] else ''
                r['target'] = d[3] if d[3] else ''
                r['ttot'] = d[4]
                r['scnt'] = d[5]
                r['cmd'] = d[6].replace('\n', ' ') if d[6] else ''
                r['file'] = d[7] if d[7] else ''
                result.append(r)
        return result

    def handle_key_event(self, event, key, dtd):
        if event == 'select' and not self.thread_stack_info:
            row = self.get_selected_row()
            if row:
                self.save_cursor()
                self.sorting_enabled = False
                self.selectable = False
                self.disable_cursor()
                self.hshift = 0
                self.thread_stack_info = (row['ident'], row['name'])
        elif event == 'back':
            self.sorting_enabled = True
            self.selectable = True
            self.enable_cursor()
            self.restore_cursor()
            self.thread_stack_info = None
        else:
            return
        self.resume()
        self.trigger_threadsafe(force=True)

    def handle_pager_event(self, dtd):
        if self.key_event != 'back':
            super().handle_pager_event(dtd)

    def format_dtd(self, dtd):
        if self.thread_stack_info is None:
            for t in dtd:
                z = t.copy()
                z['ttot'] = '{:.3f}'.format(z['ttot'])
                yield z
        else:
            for d in dtd:
                yield d

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

    def render_table_col(self, raw, color, element, key, value):
        r = raw.find(glyph.DOWNWARDS_RIGHT_ARROW)
        if r > -1:
            self.window.addstr(raw[0:r + 2], palette.GREY)
            self.window.addstr(raw[r + 2:], color)
        elif raw.startswith(glyph.DOWNWARDS_RIGHT_ARROW[-1]):
            self.window.addstr('-', palette.GREY)
            self.window.addstr(raw[1:], color)
        else:
            self.window.addstr(raw, color)

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


def injection(thread_stack_info=None, **kwargs):
    import threading
    import sys
    result = []
    if thread_stack_info is None:
        import inspect
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
                    x = inspect.getframeinfo(sys._current_frames()[t.ident])
                    r += (' '.join(x.code_context).strip(),
                          '{}:{}'.format(x.filename, x.lineno))
                except:
                    # from pptop.logger import log_traceback
                    # log_traceback()
                    r += (None, None)
                result.append(r)
    else:
        try:
            import traceback
            import linecache
            for fi in traceback.extract_stack(
                    sys._current_frames()[thread_stack_info]):
                f = fi.filename
                ln = fi.lineno
                cmd = linecache.getline(f, ln).strip()
                result.append((cmd, '{}:{}'.format(f, ln)))
        except Exception:
            e = sys.exc_info()
            result.append((e[0].__name__, str(e[1])))
    return result
