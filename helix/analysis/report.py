import statistics as st

from .flicks import METRICS_VERSION


def summarize(flicks):
    if not flicks:
        return {"metrics_version": METRICS_VERSION, "n_flicks": 0}
    med = lambda f: st.median(f(x) for x in flicks)
    clicks = [x.peak_to_click for x in flicks if x.peak_to_click is not None]
    return {
        "metrics_version": METRICS_VERSION,
        "n_flicks": len(flicks),
        "peak_speed_med": med(lambda x: x.peak_speed),
        "duration_ms_med": med(lambda x: x.duration),
        "peak_pos_med": med(lambda x: x.peak_pos),
        "decel_frac_med": med(lambda x: x.decel_frac),
        "path_eff_med": med(lambda x: x.path_eff),
        "corrections_per_flick": sum(x.corrections for x in flicks) / len(flicks),
        "flicks_with_correction_pct": 100 * sum(x.corrections > 0 for x in flicks) / len(flicks),
        "flicks_with_reversal_pct": 100 * sum(x.reversed_motion for x in flicks) / len(flicks),
        "peak_to_click_ms_med": st.median(clicks) if clicks else None,
    }


def format_summary(s):
    return "\n".join("%-28s %s" % (k, "%.3f" % v if isinstance(v, float) else v) for k, v in s.items())
