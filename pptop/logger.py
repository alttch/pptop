'''
pptop doesn't use logging because two processes must write to the same file
'''

import fcntl
import time
import traceback

from datetime import datetime


class SimpleNamespace:

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


config = SimpleNamespace(fname=None, name='')

retries = 5


def log(*args):
    if not config.fname:
        return
    s = '{} {}  {}'.format(
        datetime.strftime(datetime.now(), '%Y-%m-%d %H:%M:%S,%f')[:-3],
        config.name, ' '.join([str(x) for x in args]))
    for i in range(retries):
        try:
            with open(config.fname, 'a') as fh:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fh.seek(0, 2)
                fh.write(s + '\n')
                fcntl.flock(fh, fcntl.LOCK_UN)
                break
        except:
            time.sleep(0.1)


def log_traceback(msg=None):
    if not config.fname:
        return
    args = ()
    if msg is not None:
        args += (msg,)

    args += (traceback.format_exc(),)
    log(*args)


def init_logging():

    import logging

    class LogHandler(logging.Handler):

        def emit(self, record):
            log('{} {} {} {}'.format(record.levelname, record.module,
                                     record.funcName, record.getMessage()))

    logging.getLogger().addHandler(LogHandler())
