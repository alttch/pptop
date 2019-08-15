__version__ = "0.1.6"

from pptop import GenericPlugin, palette


class Plugin(GenericPlugin):
    '''
    list_modules plugin: list modules
    '''

    def on_load(self):
        self.title = 'List modules'
        self.description = 'List all loaded modules'
        self.sorting_rev = False
        self.need_status_line = True

    def process_data(self, data):
        result = []
        for d in data:
            result.append({
                'name': d[0],
                'version': str(d[1]),
                'author': str(d[2]),
                'license': d[3]
            })
        return result

    def format_dtd(self, dtd):
        # Usually this method is used to convert e.g. numbers to strings, to
        # add leading zeroes and limit digits after comma, changing strings to
        # other values is a bad practice and is provided here only for example.
        # All data should be prepared by process_data method
        for d in dtd:
            z = d.copy()
            if z['license'] == '':
                z['license'] = 'unknown'
            yield z

    def render_status_line(self):
        height, width = self.status_line.getmaxyx()
        self.status_line.addstr(
            'Total: {} modules loaded'.format(len(self.dtd)).rjust(width - 1),
            palette.BAR)

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)


def injection(**kwargs):
    import sys
    result = []
    for i, mod in sys.modules.items():
        if i != 'builtins':
            try:
                version = mod.__version__
            except:
                version = ''
            try:
                author = mod.__author__
            except:
                author = ''
            try:
                license = mod.__license__
            except:
                license = ''
            result.append((i, version, author, license))
    return result
