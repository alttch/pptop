from pptop.plugin import GenericPlugin, palette

from pptop.core import format_shortcut

from neotasker import spawn
from collections import OrderedDict


class Plugin(GenericPlugin):

    default_interval = 60

    def on_load(self):
        self.title = 'Select plugin'
        self.short_name = 'Plugns'
        self.sorting_rev = False
        self.selectable = True

    def load_data(self):
        self.data.clear()
        for plugin_id, plugin in self.get_plugins().items():
            p = plugin['p']
            if p.name not in ['plugin_selector', 'help']:
                sh = format_shortcut(plugin['shortcut'])
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
            row = self.get_selected_row()
            if row:
                spawn(self.switch_plugin, self.get_plugin(
                    self.get_selected_row()['id']))

    def get_table_col_color(self, element, key, value):
        if key == 'id':
            return palette.BOLD
        elif key == 'name':
            return palette.YELLOW
        elif key == 'shortcut':
            return palette.CYAN_BOLD

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)

    def pause(self):
        return
