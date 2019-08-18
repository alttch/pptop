from pptop.plugin import GenericPlugin

from atasker import background_task
from collections import OrderedDict


class Plugin(GenericPlugin):

    def on_load(self):
        self.title = 'Select plugin'
        self.short_name = 'Plugns'
        self.sorting_rev = False

    def load_data(self):
        self.data.clear()
        for plugin_id, plugin in self.get_plugins().items():
            p = plugin['p']
            if p.name not in ['plugin_selector', 'help']:
                sh = plugin['shortcut']
                if sh.startswith('KEY_F('):
                    try:
                        fnkey = int(sh[6:-1])
                        if fnkey > 48:
                            sh = 'M-F{}'.format(fnkey - 48)
                        elif fnkey > 24:
                            sh = 'C-F{}'.format(fnkey - 24)
                        elif fnkey > 12:
                            sh = 'Sh-F{}'.format(fnkey - 12)
                        else:
                            sh = 'F{}'.format(fnkey)
                    except:
                        pass
                try:
                    version = str(plugin['m'].__version__)
                except:
                    version = ''
                d = OrderedDict()
                d['id'] = p.name
                d['name'] = p.title
                d['description'] = p.description
                d['shortcut'] = sh
                d['version'] = version
                self.data.append(d)

    def handle_key_event(self, event, key, dtd):
        if event == 'select':
            background_task(self.switch_plugin)(
                self.stdscr, self.get_plugin(self.get_selected_row()['id']))

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def pause(self):
        return
