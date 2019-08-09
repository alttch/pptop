def loop(cpid):

    def send_data(conn, data):
        import struct
        conn.sendall(struct.pack('L', len(data)) + data)

    def send_pickle(conn, data):
        import pickle
        send_data(conn, b'\x00' + pickle.dumps(data))

    def send_ok(conn):
        send_data(conn, b'\x00')

    import socket
    import os
    import threading
    import struct
    import pyinstrument
    server_address = '/tmp/.pptop_{}'.format(cpid)
    try:
        os.unlink(server_address)
    except:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(server_address)
    os.chmod(server_address, 0o600)
    server.listen(0)
    server.settimeout(10)
    pi_profiler = pyinstrument.Profiler()
    pi_profiler.start()
    try:
        connection, client_address = server.accept()
        connection.settimeout(30)
        while True:
            try:
                data = connection.recv(8)
                if data:
                    l = struct.unpack('L', data)
                    cmd = connection.recv(l[0]).decode().strip()
                else:
                    break
            except:
                raise
                break
            if cmd:
                try:
                    if cmd == 'test':
                        send_ok(connection)
                    elif cmd == 'bye':
                        break
                    elif cmd == 'pyinstrument':
                        pi_profiler.stop()
                        send_pickle(connection, pi_profiler.last_session)
                        pi_profiler.start()
                    elif cmd == 'threads':
                        result = []
                        for t in threading.enumerate():
                            try:
                                target = '{}.{}'.format(t._target.__module__,
                                                        t._target.__name__)
                            except:
                                target = None
                            result.append({
                                'ident': t.ident,
                                'daemon': t.daemon,
                                'name': t.getName(),
                                'target': target if target else ''
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
        pi_profiler.stop()
    except:
        pass
    try:
        os.unlink(server_address)
    except:
        pass


def start(cpid):
    import threading
    loop(cpid)


def test():
    import time
    while True:
        time.sleep(1)


import threading
t = threading.Thread(target=test)
t.setDaemon(True)
t.start()
start(777)
