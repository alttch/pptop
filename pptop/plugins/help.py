from pptop.plugin import GenericPlugin
from pptop.ui.console import scr
from neotasker import spawn
import pptop.core as core
import textwrap
import rapidtables


class Plugin(GenericPlugin):

    def on_load(self):
        self.short_name = 'Help'
        self.sorting_enabled = False
        self.cursor_enabled = False

    def load_data(self):
        self.data.clear()
        try:
            pdoc = textwrap.dedent(self._previous_plugin['p'].__doc__)
        except:
            pdoc = None
        if pdoc:
            self.data.append({'help': ''})
            for x in pdoc.strip().split('\n'):
                self.data.append({'help': x})
            self.data.append({'help': ''})
            self.data.append({'help': '-' * scr.stdscr.getmaxyx()[1]})
        # global shortcuts
        keyhelp = {}
        for k, e in core.events_by_key.items():
            keyhelp.setdefault(e, []).append(core.format_shortcut(k))
        result = []
        for e in sorted(keyhelp):
            result.append({'e': e, 'k': ', '.join(sorted(keyhelp[e]))})
        self.data.append({'help': ''})
        self.data.append({'help': 'Global shorcuts'})
        keys_table = tuple(rapidtables.format_table(result,
                                              fmt=1,
                                              generate_header=False))
        self.data.append({'help': '-' * (len(keys_table[0]) + 4)})
        for d in keys_table:
            self.data.append({'help': ' ' * 4 + d})
        # end global shortcuts
        self.data.append({'help': ''})
        for x in textwrap.dedent(core.__doc__).split('\n'):
            self.data.append({'help': x})

    def handle_key_event(self, event, key, dtd):
        if event == 'back' and self._previous_plugin:
            spawn(self.switch_plugin, self._previous_plugin)

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def pause(self):
        return
