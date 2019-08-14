'''
pptop don't use logging because two processes must write to the same fname
'''

import fcntl
import traceback

from datetime import datetime
from types import SimpleNamespace

config = SimpleNamespace(fname=None, name='')


def log(*args):
    if not config.fname:
        return
    s = '{} {}  {}'.format(
        datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S'),
        config.name, ' '.join([str(x) for x in args]))
    with open(config.fname, 'a') as fh:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.seek(0, 2)
        fh.write(s + '\n')
        fcntl.flock(fh, fcntl.LOCK_UN)


def log_traceback(msg=None):
    if not config.fname:
        return
    args = ()
    if msg is not None:
        args += (msg,)

    args += (traceback.format_exc(),)
    log(*args)
