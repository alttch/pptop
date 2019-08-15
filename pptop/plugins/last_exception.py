from pptop.plugin import GenericPlugin, palette


class Plugin(GenericPlugin):

    def on_load(self):
        self.sorting_enabled = False
        self.cursor_enabled = False

    def load_data(self):
        self.data.clear()
        e = self.command('.le')
        if e:
            t = 'exception info'
            self.data.append({t: '!{}: {}'.format(e[0], e[1])})
            for c in e[2]:
                self.data.append({t: c})

    def get_table_row_color(self, element=None, raw=None):
        if element['exception info'].startswith('!'):
            return palette.ERROR

    def format_table_row(self, element=None, raw=None):
        return raw[1:] if raw.startswith('!') else raw

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def pause(self):
        return
