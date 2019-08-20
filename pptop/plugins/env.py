from pptop.plugin import GenericPlugin, palette

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    env plugin: view process OS environment
    '''

    default_interval = 10

    def on_load(self):
        self.description = 'Process OS environment'
        self.title = 'OS Environment'
        self.short_name = 'Env'
        self.sorting_rev = False

    def load_data(self):
        max_length = 350
        self.data.clear()
        for i, v in self.get_process().environ().items():
            v = v.replace('\r',' ').replace('\n', ' ')
            if len(v) > max_length:
                v = v[:max_length - 3] + '...'
            d = OrderedDict()
            d['var'] = i
            d['value'] = v
            self.data.append(d)

    def get_table_col_color(self, element, key, value):
        if key == 'var':
            return palette.BOLD
        else:
            return palette.YELLOW

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)
