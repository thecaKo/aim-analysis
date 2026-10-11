import json
import os
import tempfile
import threading
import unittest

from helix.analysis import flicks, synth, trace
from helix.capture import netsink, receiver


class NetworkTests(unittest.TestCase):
    def test_stream_roundtrip_matches_local_analysis(self):
        events = synth.session(n_flicks=10, overshoot=0.25)
        with tempfile.TemporaryDirectory() as d:
            done = threading.Event()
            srv = receiver.serve("127.0.0.1", 0, d, on_done=lambda p: done.set())
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            s = netsink.Sender("127.0.0.1", srv.server_address[1], "B_test 01!")
            s.send(json.dumps({"ev": "clock_map", "perf0": 0, "epoch0": 0}))
            for e in events:
                s.send(json.dumps(dict(ev="m", **e)))
            s.close()
            self.assertTrue(done.wait(5))
            srv.shutdown()
            files = os.listdir(d)
            self.assertEqual(files, ["B_test_01_.jsonl"])
            got = flicks.extract(trace.load(os.path.join(d, files[0])))
            want = flicks.extract(trace.from_events(events))
            self.assertEqual(len(got), len(want))
            self.assertEqual(len(got), 10)


if __name__ == "__main__":
    unittest.main()
