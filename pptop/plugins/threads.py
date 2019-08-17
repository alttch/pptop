from pptop.plugin import GenericPlugin


class Plugin(GenericPlugin):
    '''
    threads plugin: process thread stats

        ident: thread ident (Python)
        daemon: is thread running as daemon
        name: thread name
        target: target function
        ttot: time spent total
        scnt: schedule count

    requires yappi profiler module https://github.com/sumerc/yappi
    '''

    def on_load(self):
        self.short_name = 'Thrds'
        self.sorting_col = 'ttot'
        self.description = 'Process active threads'
        self.background_loader = True

    def process_data(self, data):
        result = []
        for d in data:
            if not d['name'].startswith('__pptop_injection'):
                d['daemon'] = 'daemon' if d['daemon'] else ''
                result.append(d)
        return result

    def format_dtd(self, dtd):
        for t in dtd:
            z = t.copy()
            z['ttot'] = '{:.3f}'.format(z['ttot'])
            yield z

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
