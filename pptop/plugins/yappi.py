from pptop import GenericPlugin, format_mod_name


class Plugin(GenericPlugin):

    def on_load(self):
        self.short_name = 'Prof'
        self.title = 'Function profiler (yappi)'

    def prepare_data(self):
        sess = []
        for s in self.data:
            mod = format_mod_name(s[1], self.get_process_path())
            if not mod.startswith('!pptop.'):
                sess.append({
                    'function': '{}.{}'.format(mod, s[0]),
                    'ncall': s[3],
                    'nacall': s[4],
                    'ttot': s[6],
                    'tsub': s[7],
                    'tavg': s[11],
                    'file': '{}:{}'.format(s[1], s[2]),
                    'builtin': s[5]
                    })
        sess = sorted(sess, key=lambda k: k['ttot'], reverse=True)
        ks = ['ttot', 'tsub', 'tavg']
        for s in sess:
            for k in ks:
                s[k] = '{:.3f}'.format(s[k])
        self.data = sess
        return True


def injection_load():
    import yappi
    import threading
    if not yappi.is_running():
        yappi.start()


def injection_unload():
    import yappi
    if yappi.is_running():
        yappi.stop()


def injection():
    import yappi
    d = yappi.get_func_stats()
    for v in d: del v[9]
    return d
