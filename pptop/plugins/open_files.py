from pptop import GenericPlugin


class Plugin(GenericPlugin):
    '''
    open_files plugin: files, open by process

        path: full file path
        fd: file descriptor
        pos: position in file
        mode: work mode
    '''

    def on_load(self):
        self.title = 'Open files'
        self.short_name = 'Files'
        self.sorting_rev = False

    def load_data(self):
        try:
            with self.data_lock:
                self.data.clear()
                for f in self.get_process().open_files():
                    self.data.append({
                        'path': f.path,
                        'fd': f.fd,
                        'pos.': f.position,
                        'mode': f.mode
                    })
                return True
        except:
            return False

    async def run(self, *args, **kwargs):
        super().run(*args, **kwargs)
