from pptop import GenericPlugin, format_mod_name

import os


class Plugin(GenericPlugin):
    '''
    yappi plugin: function profiler

    requires yappi profiler module https://github.com/sumerc/yappi
    '''

    def on_load(self):
        self.short_name = 'Prof'
        self.title = 'Function profiler (yappi)'
        self.sorting_col = 'ttot'

    def process_data(self, data):
        sess = []
        for s in data:
            mod = format_mod_name(s[1], self.get_process_path())
            if not mod.startswith('pptop.') and \
                    mod.find('.pptop.__injection') == -1:
                sess.append({
                    'function': '{}.{}'.format(mod, s[0]),
                    'ncall': s[3],
                    'nacall': s[4],
                    'ttot': s[6],
                    'tsub': s[7],
                    'tavg': s[11],
                    'file': '{}:{}'.format(os.path.abspath(s[1]), s[2]),
                    'builtin': 'builtin' if s[5] else ''
                })
        return sess

    def format_dtd(self, dtd):
        ks = ['ttot', 'tsub', 'tavg']
        for s in dtd:
            z = s.copy()
            for k in ks:
                z[k] = '{:.3f}'.format(z[k])
            yield z


def injection_load(*args, **kwargs):
    import yappi
    import threading
    if not yappi.is_running():
        yappi.start()


def injection_unload(*args, **kwargs):
    import yappi
    if yappi.is_running():
        yappi.stop()


def injection(*args, **kwargs):
    import yappi
    d = list(yappi.get_func_stats())
    for v in d:
        del v[9]
    return d
