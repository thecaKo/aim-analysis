"""Load a raw-input JSONL trace into a 1 ms grid.

Units are mouse counts; all metrics used downstream are unit-free, so DPI and
sensitivity are not needed for the first experiment.
"""
import json
from dataclasses import dataclass, field

LEFT_DOWN = 0x0001
MAX_SPREAD_MS = 20      # a report covers the time since the previous one, capped for idle gaps


@dataclass
class Trace:
    dx: list                      # counts per 1 ms bin
    dy: list
    clicks: list = field(default_factory=list)   # bin indices of left-button downs

    def __len__(self):
        return len(self.dx)


def load_events(path):
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("ev") == "m":
                events.append(r)
    return events


def load(path):
    return from_events(load_events(path))


def from_events(events):
    """events: dicts with t (ms), dx, dy, b.

    A mouse report holds the motion accumulated since the previous report, so at
    low polling rates (e.g. 125 Hz) it is spread evenly over the preceding
    interval (<= MAX_SPREAD_MS) instead of being dropped into a single 1 ms bin,
    which would look like an isolated spike.
    """
    if not events:
        return Trace([], [])
    t0 = events[0]["t"]
    n = int(events[-1]["t"] - t0) + 1
    dx, dy, clicks = [0.0] * n, [0.0] * n, []
    prev = None
    for e in events:
        i = int(e["t"] - t0)
        k = 1 if prev is None else max(1, min(MAX_SPREAD_MS, int(round(e["t"] - prev))))
        k = min(k, i + 1)
        for j in range(i - k + 1, i + 1):
            dx[j] += e["dx"] / k
            dy[j] += e["dy"] / k
        if e.get("b", 0) & LEFT_DOWN:
            clicks.append(i)
        prev = e["t"]
    return Trace(dx, dy, clicks)


def report_interval_ms(events):
    """Median time between reports; ~1 ms for a 1000 Hz mouse, ~8 ms at 125 Hz."""
    ts = [e["t"] for e in events]
    gaps = sorted(b - a for a, b in zip(ts, ts[1:]) if b - a < 100)
    return gaps[len(gaps) // 2] if gaps else None
