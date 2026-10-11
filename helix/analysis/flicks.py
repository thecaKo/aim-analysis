"""Flick segmentation and per-flick metrics.

Definitions (METRICS_VERSION bumps whenever any of these change):
  speed(t)        smoothed |(dx,dy)| in counts/ms, moving average over SMOOTH_MS
  flick           maximal run where speed >= MOVE_FRAC * run-peak and peak >= MIN_PEAK,
                  split at interior valleys that drop below SPLIT_FRAC * min(adjacent peaks)
  peak_pos        (t_peak - t_start) / duration
  decel_frac      (t_end - t_peak) / duration
  path_eff        net displacement / path length            (1 = straight line)
  corrections     direction reversals AFTER the peak: segments of motion whose velocity,
                  projected on the main (start->peak) direction, is negative or
                  re-accelerates (a new speed bump >= CORR_FRAC * peak)
  merge rule      a segment starting <= CORR_GAP_MS after the previous one ends, with peak speed
                  < CORR_PEAK_FRAC * previous peak, is folded into it as a corrective submovement
                  (heuristic: can misfold a fast chained small flick to a neighbouring target)
  peak_to_click   ms from speed peak to the first click within CLICK_WINDOW_MS after flick end
"""
import math
from dataclasses import dataclass

METRICS_VERSION = 1
SMOOTH_MS = 5
MOVE_FRAC = 0.10
MIN_PEAK = 1.0          # counts/ms; below this it is hand jitter, not a flick
SPLIT_FRAC = 0.35
CORR_FRAC = 0.15
CLICK_WINDOW_MS = 150
CORR_GAP_MS = 80        # a small move starting this soon after a flick is its correction...
CORR_PEAK_FRAC = 0.5    # ...if its peak speed is below this fraction of the flick's peak


@dataclass
class Flick:
    start: int
    end: int
    peak: int
    peak_speed: float
    duration: int
    peak_pos: float
    decel_frac: float
    path_len: float
    net_disp: float
    path_eff: float
    corrections: int
    reversed_motion: bool
    peak_to_click: float | None


def _smooth(xs, w):
    out, acc = [0.0] * len(xs), 0.0
    for i, x in enumerate(xs):
        acc += x
        if i >= w:
            acc -= xs[i - w]
        out[i] = acc / w
    return out


def _runs(speed):
    """Contiguous runs above a low floor; refined per run by MOVE_FRAC."""
    floor, runs, s = 0.05, [], None
    for i, v in enumerate(speed):
        if v >= floor and s is None:
            s = i
        elif v < floor and s is not None:
            runs.append((s, i)); s = None
    if s is not None:
        runs.append((s, len(speed)))
    return runs


def _split_valleys(speed, a, b):
    """Split [a,b) at deep interior valleys. Returns list of (a,b)."""
    peaks = [i for i in range(a + 1, b - 1) if speed[i] >= speed[i - 1] and speed[i] > speed[i + 1]]
    if len(peaks) < 2:
        return [(a, b)]
    cuts, last = [], peaks[0]
    for p in peaks[1:]:
        v = min(range(last, p + 1), key=lambda i: speed[i])
        if speed[v] < SPLIT_FRAC * min(speed[last], speed[p]):
            cuts.append(v)
            last = p
        elif speed[p] > speed[last]:
            last = p
    edges = [a] + cuts + [b]
    return list(zip(edges[:-1], edges[1:]))


def _trim(speed, a, b):
    pk = max(range(a, b), key=lambda i: speed[i])
    thr = MOVE_FRAC * speed[pk]
    while a < pk and speed[a] < thr:
        a += 1
    while b - 1 > pk and speed[b - 1] < thr:
        b -= 1
    return a, b, pk


def _count_corrections(speed, dx, dy, a, b, pk):
    """Returns (corrections, reversed_motion) for the post-peak part of a flick.

    A correction is either a re-acceleration bump in speed (rises >= CORR_FRAC*peak
    above the running minimum) or a reversal of the velocity projected on the
    start->peak direction (the hand moved back toward where it came from).
    """
    peak = speed[pk]
    bumps, valley, armed = 0, speed[pk], True
    for v in speed[pk:b]:
        if v < valley:
            valley, armed = v, True
        elif armed and v - valley >= CORR_FRAC * peak:
            bumps, armed = bumps + 1, False
        if not armed and v <= valley + 0.5 * CORR_FRAC * peak:
            valley, armed = v, True

    ux, uy = sum(dx[a:pk + 1]), sum(dy[a:pk + 1])
    norm = math.hypot(ux, uy) or 1.0
    proj = _smooth([(dx[i] * ux + dy[i] * uy) / norm for i in range(pk, b)], SMOOTH_MS)
    backward = any(v < -CORR_FRAC * peak for v in proj)
    return max(bumps, 1 if backward else 0), backward


def _segments(speed):
    segs = []
    for ra, rb in _runs(speed):
        for a, b in _split_valleys(speed, ra, rb):
            if b - a < 3 or max(speed[a:b]) < MIN_PEAK:
                continue
            a, b, pk = _trim(speed, a, b)
            if b - a >= 3:
                segs.append((a, b, pk))
    merged = []
    for a, b, pk in segs:
        if merged:
            pa, pb, ppk = merged[-1]
            if a - pb <= CORR_GAP_MS and speed[pk] < CORR_PEAK_FRAC * speed[ppk]:
                merged[-1] = (pa, b, ppk)
                continue
        merged.append((a, b, pk))
    return merged


def extract(trace):
    dx, dy = trace.dx, trace.dy
    speed = _smooth([math.hypot(x, y) for x, y in zip(dx, dy)], SMOOTH_MS)
    flicks = []
    for a, b, pk in _segments(speed):
        dur = b - a
        sx, sy = sum(dx[a:b]), sum(dy[a:b])
        path = sum(math.hypot(dx[i], dy[i]) for i in range(a, b))
        net = math.hypot(sx, sy)
        corr, rev = _count_corrections(speed, dx, dy, a, b, pk)
        click = next((c for c in trace.clicks if b - 1 <= c <= b + CLICK_WINDOW_MS), None)
        flicks.append(Flick(a, b, pk, speed[pk], dur, (pk - a) / dur, (b - pk) / dur,
                            path, net, net / path if path else 0.0, corr, rev,
                            (click - pk) if click is not None else None))
    return flicks
