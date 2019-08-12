__author__ = "Altertech Group, https://www.altertech.com/"
__copyright__ = "Copyright (C) 2019 Altertech Group"
__license__ = "MIT"
__version__ = "0.0.1"
'''
Client-server communication

After injection, client asks server to create socket /tmp/.pptop_<Client-PID>

Server accepts only one connection to socket. After connection, client and
server exchange data via simple binary/text protocol:

Client request:

    bytes 1-4 : frame length
    bytes 5-8 : client frame id
    bytes 4-N : JSON RPC 2.0 request (batch requests not supported)

Server response:

    bytes 1-4 : frame length
    bytes 5-8 : server frame id
    bytes 4-N : frame

    First frame byte: command status:

        0x00 - OK
        0x01 - Command not found
        0x02 - Command failed

    Frame bytes 2-N: JSON RPC 2.0 response

Commands:

    test            Test server
    path            Get sys.path
    threads         Get threads data
    profile         Get profiler data
    bye             End communcation

If client closes connection, connection is timed out (default: 10 sec) or
server receives "bye" command, it immediately terminates itself.
'''
import threading
import pptop.json as json
import struct
import socket
import sys
import os

from types import SimpleNamespace

socket_timeout = 60

socket_buf = 1024

g = SimpleNamespace(clients=0)

_g_lock = threading.Lock()


def loop(cpid):

    def send_frame(conn, frame_id, data):
        conn.sendall(
            struct.pack('I', len(data)) + struct.pack('I', frame_id) + data)
        print('{}: frame {}, {} bytes sent'.format(cpid, frame_id, len(data)))

    def send_serialized(conn, frame_id, req_id, data):
        if not req_id: return
        result = {'jsonrpc': '2.0', 'id': req_id, 'result': data}
        send_frame(conn, frame_id, b'\x00' + json.dumps(result).encode())

    def send_ok(conn, frame_id):
        send_frame(conn, frame_id, b'\x00')

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
                data = connection.recv(4)
                frame_id = struct.unpack('I', connection.recv(4))[0]
                if data:
                    l = struct.unpack('I', data)
                    frame = b''
                    for i in range(l[0] // socket_buf):
                        frame += connection.recv(socket_buf)
                    frame += connection.recv(l[0] % socket_buf)
                else:
                    break
            except:
                raise
                break
            if frame:
                d = json.loads(frame.decode())
                cmd = d['method']
                params = d.get('params', {})
                req_id = d.get('id')
                try:
                    if cmd == 'test':
                        send_ok(connection, frame_id)
                    elif cmd == 'bye':
                        break
                    elif cmd == 'path':
                        send_serialized(connection, frame_id, req_id, sys.path)
                    elif cmd == 'inject':
                        print(params)
                        injection_id = params['id']
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
                        send_serialized(connection, frame_id, req_id, gl['_r'])
                    else:
                        send_frame(connection, frame_id, b'\x01')
                except:
                    raise
                    send_frame(connection, frame_id, b'\x02')
            else:
                break
    except:
        raise
        pass
    for i, v in injections.items():
        u = v.get('u')
        if u:
            try:
                code = compile(u + '\ninjection_unload()',
                               '__pptop_injection_unload_' + injection_id,
                               'exec')
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


def start(cpid):
    print('starting injection server for pid {}'.format(cpid))
    t = threading.Thread(
        name='__pptop_injection_{}'.format(cpid), target=loop, args=(cpid,))
    t.setDaemon(True)
    t.start()


import logging
logging.basicConfig(level=10)


def test():
    import time, logging
    logger = logging.getLogger('pptop-test')
    while True:
        z()
        time.sleep(1)
        logger.debug('test')
        logger.info('info test')
        logger.warning('warn test')
        logger.error('warn test')
        logger.critical('critical test')


def z():
    pass


# f = open('/tmp/test-test', 'w')
# f2 = open('/tmp/test-test2', 'w')
# t = threading.Thread(target=test)
# t2 = threading.Thread(target=test, name='test thread 2')
# t.setDaemon(True)
# t2.setDaemon(True)
# t.start()
# t2.start()
# start(777)
