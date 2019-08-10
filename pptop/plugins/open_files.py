from pptop import GenericPlugin

class Plugin(GenericPlugin):

    def on_load(self):
        import os
        self.title = 'Open files'
        self.short_name = 'Files'
        self.sorting_rev = False

    def load_data(self):
        try:
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
