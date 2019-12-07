from pptop.plugin import GenericPlugin, format_mod_name, not_my_mod, palette
from pptop.plugin import abspath, bytes_to_iso

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    malloc plugin: trace memory allocation

    Shortcuts:

        g      : toggle grouping (lineno/filename/traceback)
    '''

    def on_load(self):
        self.short_name = 'Mallc'
        self.grouping_types = ('lineno', 'filename', 'traceback')
        self.current_grouping = 0
        self.set_title()
        self.sorting_col = 'size'
        self.background_loader = True

    def set_title(self):
        self.title = 'Memory allocation ({})'.format(
            self.grouping_types[self.current_grouping])

    def load_remote_data(self):
        return self.injection_command(
            key_type=self.grouping_types[self.current_grouping])

    def handle_key_event(self, event, key, dtd):
        if event == 'g':
            self.current_grouping += 1
            if self.current_grouping >= len(self.grouping_types):
                self.current_grouping = 0
            self.set_title()
            self.resume()
            self.trigger_threadsafe(force=True)
        elif event == 'reset':
            self.injection_command(key_type='reset')
            self.print_message('Malloc stats were reset', color=palette.WARNING)

    def process_data(self, data):
        sess = []
        for s in data:
            mod = format_mod_name(s[0])
            if not_my_mod(mod):
                d = OrderedDict()
                d['mod'] = mod
                d['file'] = '{}:{}'.format(abspath(
                    s[0]), s[1]) if self.current_grouping != 1 else abspath(
                        s[0])
                d['size'] = s[2]
                d['count'] = s[3]
                d['avg'] = round(s[2] / s[3])
                d['cmd'] = s[4]
                sess.append(d)
        return sess

    def format_dtd(self, dtd):
        for s in dtd:
            z = s.copy()
            for x in ('size', 'avg'):
                z[x] = bytes_to_iso(z[x])
            yield z

    def get_table_col_color(self, element, key, value):
        if key == 'size':
            return palette.CYAN
        elif key == 'avg':
            return palette.BLUE
        elif key == 'cmd':
            return palette.YELLOW
        elif key == 'count' or key == 'mod':
            return palette.BOLD

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection_load(**kwargs):
    import tracemalloc
    tracemalloc.start()


def injection_unload(**kwargs):
    import tracemalloc
    tracemalloc.stop()


def injection(key_type=None, **kwargs):
    import tracemalloc
    if key_type == 'reset':
        tracemalloc.stop()
        tracemalloc.start()
        return
    result = []
    # make sure it's started
    tracemalloc.start()
    snap = tracemalloc.take_snapshot()
    for s in snap.statistics(key_type):
        f, ln = str(s.traceback).split(':')
        import linecache
        cmd = linecache.getline(f, int(ln)).strip()
        result.append((f, ln, s.size, s.count, cmd))
    return result
