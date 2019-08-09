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
    bytes 4-N : text command frame in format <CMD>[|DATA]

Server response:

    bytes 1-4 : frame length
    bytes 4-N : frame

    First frame byte: command status:

        0x00 - OK
        0x01 - Command not found
        0x02 - Command failed

    Frame bytes 2-N: pickled data

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

from types import SimpleNamespace

timeout = 10

_d = SimpleNamespace(clients=0)

_d_lock = threading.Lock()


def loop(cpid):

    def send_data(conn, data):
        import struct
        conn.sendall(struct.pack('I', len(data)) + data)

    def send_pickle(conn, data):
        import pickle
        send_data(conn, b'\x00' + pickle.dumps(data))

    def send_ok(conn):
        send_data(conn, b'\x00')

    import socket
    import sys
    import os
    import struct
    import pickle
    import yappi
    server_address = '/tmp/.pptop_{}'.format(cpid)
    try:
        os.unlink(server_address)
    except:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(server_address)
    os.chmod(server_address, 0o600)
    server.listen(0)
    server.settimeout(timeout)
    try:
        connection, client_address = server.accept()
        with _d_lock:
            _d.clients += 1
            if not yappi.is_running():
                yappi.start()
        connection.settimeout(timeout)
        while True:
            try:
                data = connection.recv(4)
                if data:
                    l = struct.unpack('I', data)
                    cmd = connection.recv(l[0]).decode().strip()
                else:
                    break
            except:
                raise
                break
            if cmd:
                try:
                    cmd, cmd_data = cmd.split('|', 1)
                except:
                    cmd_data = None
                try:
                    if cmd == 'test':
                        send_ok(connection)
                    elif cmd == 'bye':
                        break
                    elif cmd == 'path':
                        send_pickle(connection, sys.path)
                    elif cmd == 'profiler':
                        d = yappi.get_func_stats()
                        for v in d:
                            del v[9]
                        send_pickle(connection, d)
                    elif cmd == 'threads':
                        result = []
                        yi = {}
                        for d in yappi.get_thread_stats():
                            yi[d[2]] = (d[3], d[4])
                        for t in threading.enumerate():
                            try:
                                target = '{}.{}'.format(t._target.__module__,
                                                        t._target.__name__)
                            except:
                                target = None
                            y = yi.get(t.ident)
                            result.append({
                                'ident': t.ident,
                                'daemon': t.daemon,
                                'name': t.getName(),
                                'target': target if target else '',
                                'ttot': y[0] if y else 0,
                                'scnt': y[1] if y else 0
                            })
                        send_pickle(connection, result)
                    else:
                        send_data(connection, b'\x01')
                except:
                    raise
                    send_data(connection, b'\x02')
            else:
                break
    except:
        raise
        pass
    try:
        server.close()
    except:
        pass
    try:
        with _d_lock:
            _d.clients -= 1
            if not _d.clients: yappi.stop()
    except:
        pass
    try:
        os.unlink(server_address)
    except:
        pass


def start(cpid):
    loop(cpid)


def test():
    import time
    while True:
        z()
        time.sleep(0.2)


def z():
    pass


f = open('/tmp/test-test', 'w')
f2 = open('/tmp/test-test2', 'w')
t = threading.Thread(target=test)
t2 = threading.Thread(target=test, name='test thread 2')
t.setDaemon(True)
t2.setDaemon(True)
t.start()
t2.start()
start(777)
