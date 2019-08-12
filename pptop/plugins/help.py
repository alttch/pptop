from pptop import GenericPlugin, format_mod_name
import pptop.core as core
import textwrap


class Plugin(GenericPlugin):

    def on_load(self):
        self.short_name = 'Help'
        self.sorting_enabled = False
        self.cursor_enabled = False

    def load_data(self):
        self.data.clear()
        self.data.append({'help': ''})
        pdoc = textwrap.dedent(self._previous_plugin['p'].__doc__)
        if pdoc:
            for x in pdoc.strip().split('\n'):
                self.data.append({'help': x})
            self.data.append({'help': ''})
            self.data.append({'help': '-' * self.stdscr.getmaxyx()[1]})
        for x in textwrap.dedent(core.__doc__).split('\n'):
            self.data.append({'help': x})

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)
