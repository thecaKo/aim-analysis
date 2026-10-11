"""Non-blocking line sender over TCP (stdlib only).

The Raw Input callback must never block, so lines go into a queue and a worker
thread batches them onto the socket. If the connection drops, sending stops and
the failure is reported once; the caller's local file (if any) is unaffected.
"""
import queue
import socket
import threading


class Sender:
    def __init__(self, host, port, name=None, timeout=5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(None)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.q = queue.SimpleQueue()
        self.ok = True
        self.sent = 0
        hello = '{"ev":"hello","name":%s}\n' % ('"%s"' % name if name else "null")
        self.sock.sendall(hello.encode())
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def send(self, line):
        """line: one JSON object as str, without trailing newline."""
        if self.ok:
            self.q.put(line)

    def _run(self):
        try:
            while True:
                line = self.q.get()
                if line is None:
                    return
                batch = [line]
                while len(batch) < 512:
                    try:
                        nxt = self.q.get_nowait()
                    except queue.Empty:
                        break
                    if nxt is None:
                        self._flush(batch)
                        return
                    batch.append(nxt)
                self._flush(batch)
        except OSError as e:
            self.ok = False
            print("network send failed (%s); continuing without it" % e)

    def _flush(self, batch):
        self.sock.sendall(("\n".join(batch) + "\n").encode())
        self.sent += len(batch)

    def close(self):
        self.q.put(None)
        self.th.join(timeout=5)
        try:
            self.sock.close()
        except OSError:
            pass
