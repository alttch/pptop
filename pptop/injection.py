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
    <plugin_id>      Command for plugin
    .bye             End communcation

If client closes connection, connection is timed out (default: 10 sec) or
server receives "bye" command, it immediately terminate itself and loaded
plugins.
'''

__author__ = "Altertech Group, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech Group"
__license__ = "MIT"
__version__ = "0.0.15"

import threading
import struct
import signal
import socket
import sys
import os
import time

import pickle

from types import SimpleNamespace

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


def loop(cpid, runner_mode=False):

    def send_frame(conn, frame_id, data):
        conn.sendall(
            struct.pack('I', len(data)) + struct.pack('I', frame_id) + data)
        print('{}: frame {}, {} bytes sent'.format(cpid, frame_id, len(data)))

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
        injections = {}
        with _g_lock:
            g.clients += 1
        connection.settimeout(socket_timeout)
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
                raise
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
                    elif cmd == '.le':
                        with _g_lock:
                            send_serialized(connection, frame_id,
                                            g._last_exception)
                    elif cmd == '.ready':
                        g._runner_ready = True
                        send_ok(connection, frame_id)
                    elif cmd == '.inject':
                        print(params)
                        injection_id = params['id']
                        if injection_id in injections:
                            u = injections[injection_id].get('u')
                            if u:
                                try:
                                    code = format_injection_unload_code(
                                        injection_id, u)
                                    exec(code, injections[injection_id]['g'])
                                    print('injection removed {}'.format(
                                        injection_id))
                                except:
                                    raise
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
                                params['l'] + '\ninjection_load()',
                                '__pptop_injection_load_' + injection_id,
                                'exec')
                            exec(code, injections[injection_id]['g'])
                        if 'i' in params:
                            src = params['i'] + '\n_r = injection(**kw)'
                        else:
                            src = '_r = None'
                        injections[injection_id]['i'] = compile(
                            src, '__pptop_injection_' + injection_id, 'exec')
                        print('injection completed {}'.format(injection_id))
                        send_ok(connection, frame_id)
                    elif cmd in injections:
                        print('command {}, data: {}'.format(cmd, params))
                        gl = injections[cmd]['g']
                        gl['kw'] = params
                        exec(injections[cmd]['i'], gl)
                        send_serialized(connection, frame_id, gl['_r'])
                    else:
                        send_frame(connection, frame_id, b'\x01')
                except:
                    raise
                    send_frame(connection, frame_id, b'\x02')
            else:
                break
    except Exception as e:
        raise
        pass
    for i, v in injections.items():
        u = v.get('u')
        if u:
            try:
                code = format_injection_unload_code(i, u)
                exec(code, v['g'])
                print('injection removed {}'.format(i))
            except:
                raise
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
    print('finished')
    if runner_mode:
        g._server_finished = True
        os._exit(0)


def start(cpid, runner_mode=False):
    print('starting injection server for pid {}'.format(cpid))
    threading.Thread(
        name='__pptop_injection_{}'.format(cpid),
        target=loop,
        args=(cpid, runner_mode),
        daemon=True).start()


def launch(cpid, wait=True):
    start(cpid, runner_mode=True)
    if wait is True:
        print('waiting for ready')
        while not g._runner_ready:
            time.sleep(0.2)
        print('completed. executing main code')
    elif wait > 0:
        print('waiting {} seconds'.format(wait))
        t_end = time.time() + wait
        while time.time() < t_end:
            if g._runner_ready:
                break
            time.sleep(0.1)


def main():
    import argparse
    import shlex
    ap = argparse.ArgumentParser()
    ap.add_argument('file', metavar='FILE', help='File to launch')
    ap.add_argument('cpid', metavar='PID', type=int, help='Client PID')
    ap.add_argument(
        '-w', '--wait', metavar='SEC', type=int, help='Wait seconds till start')
    ap.add_argument('-a', '--args', metavar='ARGS', help='Child args (quoted)')
    a = ap.parse_args()
    with open(a.file) as fh:
        src = fh.read()
    sys.argv = [a.file]
    if a.args:
        sys.argv += shlex.split(a.args)
    launch(a.cpid, wait=True if a.wait is None else a.wait)
    g._runner_status = 1
    try:
        code = compile(src, a.file, 'exec')
        exec(code)
        g._runner_status = 0
    except:
        g._runner_status = -2
        import traceback
        e = sys.exc_info()
        with _g_lock:
            g._last_exception = (e[0].__name__, e[1], ['']
                                )  # TODO: correct tb traceback.format_tb(e[2]))
    while not g._server_finished:
        time.sleep(0.2)
    print('pptop injection runner stopped')


if __name__ == '__main__':
    main()
