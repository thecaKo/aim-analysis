"""Synthetic traces (minimum-jerk flicks) for testing the analysis on any OS."""
import math
import random


def _mj(n):
    """Per-ms velocity fractions of a minimum-jerk point-to-point move (sums to 1)."""
    pos = lambda s: 10 * s**3 - 15 * s**4 + 6 * s**5
    return [pos((i + 1) / n) - pos(i / n) for i in range(n)]


def flick_events(t0, vec, dur, overshoot=0.0, settle_gap=40, seed=0):
    """Events for one flick of total displacement vec; optional overshoot then a
    corrective move back after a pause. Returns (events, end_time_ms)."""
    rng = random.Random(seed)
    ev, t = [], t0
    legs = [(vec[0] * (1 + overshoot), vec[1] * (1 + overshoot), dur)]
    if overshoot:
        legs.append((-vec[0] * overshoot, -vec[1] * overshoot, int(dur * 0.5)))
    for k, (x, y, d) in enumerate(legs):
        if k:
            t += settle_gap
        px = py = 0.0
        acc = [0.0, 0.0]
        for i, f in enumerate(_mj(d)):
            acc[0] += x * f; acc[1] += y * f
            ix, iy = round(acc[0] - px), round(acc[1] - py)
            px += ix; py += iy
            ev.append({"t": t + i, "dx": ix, "dy": iy, "b": 0})
        t += d
    return ev, t


def session(n_flicks=20, overshoot=0.0, dist=400, dur=140, gap=300, seed=1):
    rng = random.Random(seed)
    ev, t = [], 100.0
    for i in range(n_flicks):
        ang = rng.uniform(0, 2 * math.pi)
        e, t = flick_events(t, (dist * math.cos(ang), dist * math.sin(ang)), dur, overshoot, seed=i)
        ev += e
        ev.append({"t": t + 20, "dx": 0, "dy": 0, "b": 1})   # click
        t += gap
    return ev
