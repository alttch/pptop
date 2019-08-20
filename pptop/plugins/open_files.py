from pptop.plugin import GenericPlugin, palette

from collections import OrderedDict


class Plugin(GenericPlugin):
    '''
    open_files plugin: files, open by process

        path: full file path
        fd: file descriptor
        pos: position in file
        mode: work mode
    '''
    default_interval = 0.5

    def on_load(self):
        self.description = 'Process open files'
        self.title = 'Open files'
        self.short_name = 'Files'
        self.sorting_rev = False

    def load_data(self):
        try:
            with self.data_lock:
                self.data.clear()
                for f in self.get_process().open_files():
                    d = OrderedDict()
                    d['path'] = f.path
                    d['fd'] = f.fd
                    d['pos.'] = f.position
                    d['mode'] = f.mode
                    self.data.append(d)
                return True
        except:
            return False

    def get_table_col_color(self, element, key, value):
        if key == 'path':
            return palette.BOLD
        elif key == 'mode':
            if value == 'r':
                return palette.GREEN
            else:
                return palette.BLUE_BOLD
        else:
            return palette.CYAN

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)
