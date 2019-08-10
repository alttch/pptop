from pptop import GenericPlugin


class Plugin(GenericPlugin):

    def on_load(self):
        self.short_name = 'Thrds'

    def prepare_data(self):
        self.data = sorted(self.data, key=lambda k: k['ttot'], reverse=True)
        for t in self.data:
            t['ttot'] = '{:.3f}'.format(t['ttot'])
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
    import threading
    result = []
    yi = {}
    for d in yappi.get_thread_stats():
        yi[d[2]] = (d[3], d[4])
    for t in threading.enumerate():
        try:
            target = '{}.{}'.format(t._target.__module__, t._target.__name__)
        except:
            target = None
        y = yi.get(t.ident)
        result.append({
            'ident': t.ident,
            'daemon': t.daemon,
            'name': t.getName(),
            'target': target if target else '',
            'ttot': y[0] if y else 0,
            'scnt': y[1] if y else 0
        })
    return result
