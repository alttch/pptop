'''
Client-server communication

After injection, client asks server to create socket /tmp/.pptop_<Client-PID>

Server accepts only one connection to socket. After connection, client and
server exchange data via simple binary/text protocol:

Client request:

    bytes 1-4 : frame length
    bytes 5-8 : client frame id
    bytes 4-N : cmd and cmd params, separated with \xff

Server response:

    bytes 1-4 : frame length
    bytes 5-8 : server frame id
    bytes 4-N : frame

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
    .exec            Exec command
    <plugin_id>      Command for plugin
    .bye             End communcation

If client closes connection, connection is timed out (default: 10 sec) or
server receives "bye" command, it immediately terminate itself and loaded
plugins.
'''

__injection_version__ = "0.2.3"

import threading
import struct
import signal
import socket
import sys
import os
import time

import pickle
import traceback

from types import SimpleNamespace

import pptop.logger

from pptop.logger import config as log_config, log, log_traceback

socket_timeout = 10

socket_buf = 8192

# don't use threading.Event to hide presence

g = SimpleNamespace(
    clients=0,
    _runner_status=-1,
    _runner_ready=False,
    _server_finished=False,
    _last_exception=())

_g_lock = threading.Lock()


def init_logging(fname):
    log_config.fname = fname
    log_config.name = 'injection:{}'.format(os.getpid())


def loop(cpid, runner_mode=False):

    def send_frame(conn, frame_id, data):
        conn.sendall(
            struct.pack('I', len(data)) + struct.pack('I', frame_id) + data)
        # log('{}: frame {}, {} bytes sent'.format(cpid, frame_id, len(data)))

    def send_serialized(conn, frame_id, data):
        send_frame(conn, frame_id, b'\x00' + pickle.dumps(data))

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
    try:
        connection, client_address = server.accept()
        log('connected')
        injections = {}
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
                    elif cmd == '.status':
                        send_serialized(connection, frame_id, g._runner_status
                                        if runner_mode else 1)
                    elif cmd == '.path':
                        send_serialized(connection, frame_id, sys.path)
                    elif cmd == '.exec':
                        try:
                            if params.startswith('help'):
                                raise RuntimeError(
                                    'Help on remote is not supported')
                            p1 = params.split(' ', 1)[0]
                            if p1 in [
                                    'import', 'def', 'for', 'while', 'raise',
                                    'if'
                            ]:
                                src = ('def print(*args):\n' +
                                       ' __resultl.append(\' \'.join(str(a) ' +
                                       'for a in args))\n__resultl=[]\n{}' +
                                       '\n__result = \'\\n\'.join(__resultl) ' +
                                       'if __resultl else None').format(params)
                            else:
                                src = (
                                    'def print(*args): ' +
                                    'return \' \'.join(str(a) for a in args)\n'
                                    + '__result = {}').format(params)
                            exec(src, exec_globals)
                            result = exec_globals.get('__result')
                            try:
                                if result is None or \
                                            isinstance(result, dict) or \
                                            isinstance(result, list) or \
                                            isinstance(result, tuple) or \
                                            isinstance(result, float) or \
                                            isinstance(result, int) or \
                                            isinstance(result, bool):
                                    data = pickle.dumps((0, result))
                                else:
                                    raise ValueError
                            except:
                                # TODO - stringify only unpicklable values
                                # but avoid copy.deepcopy
                                data = pickle.dumps((0, str(result)))
                            send_frame(connection, frame_id, b'\x00' + data)
                        except:
                            log_traceback()
                            e = sys.exc_info()
                            with _g_lock:
                                g._last_exception = (e[0].__name__, e[1], [''])
                            send_serialized(connection, frame_id,
                                            (-1, e[0].__name__, e[1]))
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
                                    pass
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
        pass
    for i, v in injections.items():
        u = v.get('u')
        if u:
            try:
                code = format_injection_unload_code(i, u)
                exec(code, v['g'])
                log('injection removed: {}'.format(i))
            except:
                pass
    try:
        server.close()
    except:
        pass
    try:
        with _g_lock:
            g.clients -= 1
    except:
        pass
    try:
        os.unlink(server_address)
    except:
        pass
    log('finished')
    if runner_mode:
        g._server_finished = True
        os._exit(0)


def start(cpid, lg=None, runner_mode=False):
    if lg:
        init_logging(lg)
    log('starting injection server for pid {}'.format(cpid))
    threading.Thread(
        name='__pptop_injection_{}'.format(cpid),
        target=loop,
        args=(cpid, runner_mode),
        daemon=True).start()


def launch(cpid, wait=True):
    start(cpid, runner_mode=True)
    if wait is True:
        log('waiting for ready')
        while not g._runner_ready:
            time.sleep(0.2)
        log('completed. executing main code')
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
    ap.add_argument(
        '-w',
        '--wait',
        metavar='SEC',
        type=float,
        help='Wait seconds till start')
    ap.add_argument('-a', '--args', metavar='ARGS', help='Child args (quoted)')
    ap.add_argument(
        '--debug-file', metavar='FILE', help='Send debug log to file')
    a = ap.parse_args()
    if a.debug_file:
        init_logging(a.debug_file)

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
        exec(code)
        g._runner_status = 0
        log('main code finished')
    except:
        g._runner_status = -2
        log_traceback('exception in main code')
        e = sys.exc_info()
        with _g_lock:
            g._last_exception = (e[0].__name__, e[1], ['']
                                )  # TODO: correct tb traceback.format_tb(e[2]))
    while not g._server_finished:
        time.sleep(0.2)
    # usually not executed as server kills process
    log('pptop injection runner stopped')


if __name__ == '__main__':
    main()
