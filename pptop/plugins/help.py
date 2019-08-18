from pptop.plugin import GenericPlugin
from atasker import background_task
import pptop.core as core
import textwrap
import tabulate


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
            self.data.append({'help': '-' * self.stdscr.getmaxyx()[1]})
        # global shortcuts
        keyhelp = {}
        for k, e in core.events_by_key.items():
            keyhelp.setdefault(e, []).append(core.format_shortcut(k))
        result = []
        for e in sorted(keyhelp):
            result.append({'e': e, 'k': ', '.join(sorted(keyhelp[e]))})
        self.data.append({'help': ''})
        self.data.append({'help': 'Global shorcuts'})
        self.data.append({'help': '-' * 15})
        for d in tabulate.tabulate(result, tablefmt='plain').split('\n'):
            self.data.append({'help': ' ' * 4 + d})
        # end global shortcuts
        self.data.append({'help': ''})
        for x in textwrap.dedent(core.__doc__).split('\n'):
            self.data.append({'help': x})

    def handle_key_event(self, event, key, dtd):
        if event == 'ESC' and self._previous_plugin:
            background_task(self.switch_plugin)(self.stdscr,
                                                self._previous_plugin)

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def pause(self):
        return
