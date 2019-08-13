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
                    sh = 'F' + sh[6:-1]
                self.data.append({
                    'id': p.name,
                    'name': p.title,
                    'description': p.description,
                    'shortcut': sh
                })

    def handle_key_event(self, event, dtd):
        if event == '\n':
            background_task(self.switch_plugin)(
                self.stdscr, self.get_plugin(self.get_selected_row()['id']))

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def toggle_pause(self):
        pass
