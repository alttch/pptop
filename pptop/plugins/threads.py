from pptop import GenericPlugin


class Plugin(GenericPlugin):

    def on_load(self):
        self.short_name = 'Thrds'
        self.sorting_col = 'ttot'

    def formatted_data(self, limit):
        for t in self.dtd[self.shift:self.shift + limit - 1]:
            z = t.copy()
            z['ttot'] = '{:.3f}'.format(z['ttot'])
            yield z


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
