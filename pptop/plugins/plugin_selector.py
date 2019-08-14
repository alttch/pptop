from pptop import GenericPlugin

from atasker import background_task


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
                        raise
                        pass
                self.data.append({
                    'id': p.name,
                    'name': p.title,
                    'description': p.description,
                    'shortcut': sh
                })

    def handle_key_event(self, event, dtd):
        if event == 'ENTER':
            background_task(self.switch_plugin)(
                self.stdscr, self.get_plugin(self.get_selected_row()['id']))

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def pause(self):
        return
