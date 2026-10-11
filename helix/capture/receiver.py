"""Receives raw-input traces streamed by rawinput_logger --send and saves them.

  python -m helix.capture.receiver [--port 8765] [--out data]

One connection = one run -> <out>/<name>.jsonl (name from the sender's --name,
else a timestamp; never overwrites). Prints the flick summary when the run ends.
No encryption or authentication: use only on a trusted home network.
"""
import argparse
import json
import os
import re
import socketserver
import threading
import time

from ..analysis import flicks, report, trace


def _safe_name(name):
    name = re.sub(r"[^A-Za-z0-9_-]", "_", name or "")
    return name or time.strftime("run_%Y%m%d_%H%M%S")


def _unique(out_dir, name):
    path, n = os.path.join(out_dir, name + ".jsonl"), 1
    while os.path.exists(path):
        n += 1
        path = os.path.join(out_dir, "%s_%d.jsonl" % (name, n))
    return path


def make_handler(out_dir, on_done=None):
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            first = self.rfile.readline()
            try:
                hello = json.loads(first)
                name = hello.get("name") if hello.get("ev") == "hello" else None
            except ValueError:
                return
            os.makedirs(out_dir, exist_ok=True)
            path = _unique(out_dir, _safe_name(name))
            events, last_print = 0, time.time()
            print("run started -> %s (from %s)" % (path, self.client_address[0]))
            with open(path, "w", encoding="utf-8") as f:
                for line in self.rfile:
                    f.write(line.decode("utf-8"))
                    events += 1
                    if time.time() - last_print > 5:
                        print("  %d events" % events)
                        last_print = time.time()
            print("run ended: %d events" % events)
            if events:
                s = report.summarize(flicks.extract(trace.load(path)))
                print(report.format_summary(s))
            if on_done:
                on_done(path)
    return Handler


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(host="0.0.0.0", port=8765, out_dir="data", on_done=None):
    return Server((host, port), make_handler(out_dir, on_done))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    srv = serve(port=args.port, out_dir=args.out)
    print("listening on port %d, saving to %s/ (Ctrl+C to quit)" % (args.port, args.out))
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
