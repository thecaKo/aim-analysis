"""Load a raw-input JSONL trace into a 1 ms grid.

Units are mouse counts; all metrics used downstream are unit-free, so DPI and
sensitivity are not needed for the first experiment.
"""
import json
from dataclasses import dataclass, field

LEFT_DOWN = 0x0001


@dataclass
class Trace:
    dx: list                      # counts per 1 ms bin
    dy: list
    clicks: list = field(default_factory=list)   # bin indices of left-button downs

    def __len__(self):
        return len(self.dx)


def load(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("ev") == "m":
                events.append(r)
    return from_events(events)


def from_events(events):
    """events: dicts with t (ms), dx, dy, b. Sums motion into whole-ms bins."""
    if not events:
        return Trace([], [])
    t0 = events[0]["t"]
    n = int(events[-1]["t"] - t0) + 1
    dx, dy, clicks = [0] * n, [0] * n, []
    for e in events:
        i = int(e["t"] - t0)
        dx[i] += e["dx"]
        dy[i] += e["dy"]
        if e.get("b", 0) & LEFT_DOWN:
            clicks.append(i)
    return Trace(dx, dy, clicks)
