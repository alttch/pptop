from pptop import GenericPlugin


class Plugin(GenericPlugin):
    '''
    env plugin: view process OS environment
    '''
    def on_load(self):
        self.description = 'Process OS environment'
        self.title = 'OS Environment'
        self.short_name = 'Env'
        self.sorting_rev = False

    def load_data(self):
        max_length = 350
        self.data.clear()
        for i, v in self.get_process().environ().items():
            if len(v) > max_length:
                v = v[:max_length - 3] + '...'
            self.data.append({'var': i, 'value': v})

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)
