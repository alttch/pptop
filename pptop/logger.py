'''
pptop don't use logging because two processes must write to the same file
'''

log_file = None
process_name = ''

import fcntl
from datetime import datetime


def log(*args):
    if not log_file:
        return
    s = '{} {}  {}'.format(
        datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'), process,
        ' '.join([str(x) for x in args]))
    with open(log_file, 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.seek(0, 2)
        fh.write(s + '\n')
        fcntl.flock(fh, fcntl.LOCK_UN)
