'''
Client-server communication

After injection, client asks server to create socket /tmp/.pptop_<Client-PID>

Server accepts only one connection to socket. After connection, server sends to
client pickle protocol version (lower or equal to requested at start) as a
single byte.

Then client and server exchange data via simple binary/text protocol:

Client request:

    bytes 1-4 : frame length
    bytes 5-8 : client frame id
    bytes 9-N : cmd and pickled cmd params, separated with \xff

Server response:

    bytes 1-4 : frame length
    bytes 5-8 : server frame id
    bytes 9-N : frame

    First frame byte: command status:

        0x00 - OK
        0x01 - Command not found
        0x02 - Command failed

    Frame bytes 2-N: pickled response

Commands:

    .test            Test server
    .status          Get process status
    .path            Get sys.path
    .inject          Inject a plugin
    .le              Get last exception
    .x               Exec code
    .exec            Exec command
    .gs              Grab stdout
    <plugin_id>      Command for plugin
    .bye             End communcation

If client closes connection, connection is timed out (default: 10 sec) or
server receives "bye" command, it immediately terminate itself and loaded
plugins.
'''

__injection_version__ = '0.6.13'

import threading
import struct
import socket
import sys
import os
import time

# try all variations on older versions
try:
    import cPickle as pickle
    PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL
except:
    try:
        import _pickle as pickle
        import pickle as _pickle_orig
        PICKLE_PROTOCOL = _pickle_orig.HIGHEST_PROTOCOL
    except:
        import pickle
        PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL

from pptop.logger import config as log_config, log, log_traceback

socket_timeout = 10

socket_buf = 8192

# compat. with Python 2


class SimpleNamespace:

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# don't use threading.Event to hide presence

g = SimpleNamespace(clients=0,
                    _runner_status=-1,
                    _runner_ready=False,
                    _server_finished=False,
                    _last_exception=())

_g_lock = threading.Lock()


def init_logging(fname):
    log_config.fname = fname
    log_config.name = 'injection:{}'.format(os.getpid())


def stop_logging():
    log_config.fname = None


def safe_serialize(obj):
    if obj is None or \
            isinstance(obj, str) or \
            isinstance(obj, float) or \
            isinstance(obj, int) or \
            isinstance(obj, bool):
        result = obj
    elif isinstance(obj, list):
        result = []
        for o in obj.copy():
            result.append(safe_serialize(o))
    elif isinstance(obj, dict):
        result = {}
        for o, v in obj.copy().items():
            result[safe_serialize(o)] = safe_serialize(v)
    else:
        result = str(obj)
    return result


def loop(cpid, protocol, runner_mode=False):

    class STD:
        pass

    class ppStdout(object):

        write_through = False
        mode = 'w'

        def __init__(self, name, real, std):
            self.name = '<{}>'.format(name)
            self.real = real
            self.std = std
            try:
                self.encoding = real.encoding
            except:
                self.encoding = 'UTF-8'
            self.flush = real.flush
            self.isatty = real.isatty

        def writable(self):
            return True

        def write(self, text):
            with self.std.lock:
                self.std.buf += text
            return self.real.write(text)

        def writelines(self, lines):
            with self.std.lock:
                for l in lines:
                    self.std.buf += l
            return self.real.writelines(lines)

    def send_frame(conn, frame_id, data):
        conn.sendall(
            struct.pack('I', len(data)) + struct.pack('I', frame_id) + data)
        # log('{}: frame {}, {} bytes sent'.format(cpid, frame_id, len(data)))

    def send_serialized(conn, frame_id, data):
        send_frame(conn, frame_id,
                   b'\x00' + pickle.dumps(data, protocol=protocol))

    def send_ok(conn, frame_id):
        send_frame(conn, frame_id, b'\x00')

    def format_injection_unload_code(injection_id, src):
        return compile(u + '\ninjection_unload()',
                       '__pptop_injection_unload_' + injection_id, 'exec')

    server_address = '/tmp/.pptop.{}'.format(cpid)
    try:
        os.unlink(server_address)
    except:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(server_address)
    os.chmod(server_address, 0o600)
    server.listen(0)
    server.settimeout(socket_timeout)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, socket_buf)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, socket_buf)
    injections = {}
    real_stdout = None
    real_stderr = None
    log('Pickle protocol: {}'.format(protocol))
    log('listening')
    try:
        connection, client_address = server.accept()
        log('connected')
        connection.sendall(struct.pack('b', protocol))
        with _g_lock:
            g.clients += 1
        connection.settimeout(socket_timeout)
        exec_globals = {}
        while True:
            try:
                time_start = time.time()
                data = connection.recv(4)
                frame_id = struct.unpack('I', connection.recv(4))[0]
                if data:
                    l = struct.unpack('I', data)[0]
                    frame = b''
                    while len(frame) != l:
                        if time.time() > time_start + socket_timeout:
                            raise TimeoutError
                        frame += connection.recv(socket_buf)
                else:
                    break
            except:
                log_traceback('invalid data received or client is gone')
                break
            if frame:
                try:
                    cmd, params = frame.split(b'\xff', 1)
                    cmd = cmd.decode()
                    params = pickle.loads(params)
                except:
                    cmd = frame.decode()
                    params = {}
                try:
                    if cmd == '.test':
                        send_ok(connection, frame_id)
                    elif cmd == '.bye':
                        break
                    elif cmd == '.gs':
                        if real_stdout is None:
                            std = STD()
                            std.lock = threading.Lock()
                            std.buf = ''
                            with std.lock:
                                real_stdout = sys.stdout
                                real_stderr = sys.stderr
                                sys.stdout = ppStdout('stdout', real_stdout,
                                                      std)
                                sys.stderr = ppStdout('stderr', real_stderr,
                                                      std)
                                buf = ''
                        else:
                            with std.lock:
                                buf = std.buf
                                std.buf = ''
                        send_serialized(connection, frame_id, buf)
                    elif cmd == '.status':
                        send_serialized(connection, frame_id,
                                        g._runner_status if runner_mode else 1)
                    elif cmd == '.path':
                        send_serialized(connection, frame_id, sys.path)
                    elif cmd == '.x':
                        x = {}
                        try:
                            exec(params, x)
                            result = (0, x.get('out'))
                        except:
                            log_traceback()
                            e = sys.exc_info()
                            result = (1, e[0].__name__, str(e[1]))
                        send_serialized(connection, frame_id, result)
                    elif cmd == '.exec':
                        try:
                            if params.startswith('help'):
                                raise RuntimeError(
                                    'Help on remote is not supported')
                            if params.startswith('try: __result '):
                                src = params
                            else:
                                p1 = params.split(' ', 1)[0]
                                prfunc = '_print' if sys.version_info < (
                                    3, 0) else 'print'
                                if p1 in [
                                        'import', 'def', 'class', 'for',
                                        'while', 'raise', 'if', 'with', 'from',
                                        'try:'
                                ]:
                                    src = (
                                        'def {}(*args):\n' +
                                        ' __resultl.append(\' \'.join(str(a) ' +
                                        'for a in args))\n__resultl=[]\n{}' +
                                        '\n__result = \'\\n\'.join(__resultl) '
                                        + 'if __resultl else None').format(
                                            prfunc, params)
                                else:
                                    src = ('def {}(*args): ' +
                                           'return \' \'.join(str(a) ' +
                                           'for a in args)\n' +
                                           '__result = {}').format(
                                               prfunc, params)
                            exec(src, exec_globals)
                            result = exec_globals.get('__result')
                            try:
                                data = pickle.dumps((0, safe_serialize(result)),
                                                    protocol=protocol)
                            except:
                                log_traceback()
                                data = pickle.dumps((0, str(result)),
                                                    protocol=protocol)
                            send_frame(connection, frame_id, b'\x00' + data)
                        except:
                            log_traceback()
                            e = sys.exc_info()
                            with _g_lock:
                                g._last_exception = (e[0].__name__, str(e[1]),
                                                     [''])
                            send_serialized(connection, frame_id,
                                            (-1, e[0].__name__, str(e[1])))
                    elif cmd == '.le':
                        with _g_lock:
                            send_serialized(connection, frame_id,
                                            g._last_exception)
                    elif cmd == '.ready':
                        g._runner_ready = True
                        send_ok(connection, frame_id)
                    elif cmd == '.inject':
                        log(params)
                        injection_id = params['id']
                        if injection_id in injections:
                            u = injections[injection_id].get('u')
                            if u:
                                try:
                                    code = format_injection_unload_code(
                                        injection_id, u)
                                    exec(code, injections[injection_id]['g'])
                                    log('injection removed: {}'.format(
                                        injection_id))
                                except:
                                    log_traceback()
                        injections[injection_id] = {
                            'g': {
                                'g': SimpleNamespace(),
                                'mg': g
                            },
                            'u': params.get('u')
                        }
                        if 'l' in params:
                            code = compile(
                                params['l'] + '\ninjection_load(**load_kw)',
                                '__pptop_injection_load_' + injection_id,
                                'exec')
                            injections[injection_id]['g'][
                                'load_kw'] = params.get('lkw', {})
                            exec(code, injections[injection_id]['g'])
                        if 'i' in params:
                            src = params['i'] + '\n_r = injection(**kw)'
                        else:
                            src = '_r = None'
                        injections[injection_id]['i'] = compile(
                            src, '__pptop_injection_' + injection_id, 'exec')
                        log('injection completed: {}'.format(injection_id))
                        send_ok(connection, frame_id)
                    elif cmd in injections:
                        log('command {}, data: {}'.format(cmd, params))
                        gl = injections[cmd]['g']
                        gl['kw'] = params
                        exec(injections[cmd]['i'], gl)
                        send_serialized(connection, frame_id, gl['_r'])
                    else:
                        send_frame(connection, frame_id, b'\x01')
                except:
                    log_traceback()
                    send_frame(connection, frame_id, b'\x02')
            else:
                break
    except Exception as e:
        log_traceback()
    for i, v in injections.items():
        u = v.get('u')
        if u:
            try:
                code = format_injection_unload_code(i, u)
                exec(code, v['g'])
                log('injection removed: {}'.format(i))
            except:
                log_traceback()
    try:
        server.close()
    except:
        pass
    try:
        with _g_lock:
            g.clients -= 1
    except:
        pass
    if real_stdout is not None:
        sys.stdout = real_stdout
    if real_stderr is not None:
        sys.stderr = real_stderr
    try:
        os.unlink(server_address)
    except:
        pass
    log('finished')
    if runner_mode:
        g._server_finished = True
        os._exit(0)


def start(cpid, protocol=None, lg=None, runner_mode=False):
    if lg:
        init_logging(lg)
    else:
        stop_logging()
    log('starting injection server for pid {}'.format(cpid))
    if protocol and protocol <= PICKLE_PROTOCOL:
        protocol = protocol
    else:
        protocol = PICKLE_PROTOCOL
    t = threading.Thread(name='__pptop_injection_{}'.format(cpid),
                         target=loop,
                         args=(cpid, protocol, runner_mode))
    t.setDaemon(True)
    t.start()


def launch(cpid, wait=True, protocol=None):
    start(cpid, protocol=None, runner_mode=True)
    if wait is True:
        log('waiting for ready')
        while not g._runner_ready:
            time.sleep(0.2)
    elif wait > 0:
        log('waiting {} seconds'.format(wait))
        t_end = time.time() + wait
        while time.time() < t_end:
            if g._runner_ready:
                break
            time.sleep(0.1)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('file', metavar='FILE', help='File to launch')
    ap.add_argument('cpid', metavar='PID', type=int, help='Client PID')
    ap.add_argument('-w',
                    '--wait',
                    metavar='SEC',
                    type=float,
                    help='Wait seconds till start')
    ap.add_argument('-p',
                    '--protocol',
                    metavar='VER',
                    type=int,
                    help='Pickle protocol')
    ap.add_argument('-a', '--args', metavar='ARGS', help='Child args (quoted)')
    ap.add_argument('--log', metavar='FILE', help='Send debug log to file')
    a = ap.parse_args()
    if a.protocol and a.protocol > PICKLE_PROTOCOL:
        raise ValueError('Protocol {} is not supported'.format(a.protocol))
    if a.log:
        init_logging(a.log)
    with open(a.file) as fh:
        src = fh.read()
    sys.argv = [a.file]
    if a.args:
        import shlex
        sys.argv += shlex.split(a.args)
    log('pptop injection runner started')
    launch(a.cpid, wait=True if a.wait is None else a.wait)
    g._runner_status = 1
    log('starting main code')
    try:
        code = compile(src, a.file, 'exec')
        launcher_g = {'__file__': a.file}
        exec(code, launcher_g)
        g._runner_status = 0
        log('main code finished')
    except:
        g._runner_status = -2
        log_traceback('exception in main code')
        e = sys.exc_info()
        with _g_lock:
            g._last_exception = (e[0].__name__, str(e[1]), ['']
                                )  # TODO: correct tb traceback.format_tb(e[2]))
    while not g._server_finished:
        time.sleep(0.2)
    # usually not executed as server kills process
    log('pptop injection runner stopped')


if __name__ == '__main__':
    main()
