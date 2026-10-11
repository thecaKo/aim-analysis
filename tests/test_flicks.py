import unittest

from helix.analysis import flicks, report, synth, trace


def run(**kw):
    return flicks.extract(trace.from_events(synth.session(**kw)))


class FlickTests(unittest.TestCase):
    def test_detects_every_clean_flick(self):
        fs = run(n_flicks=20)
        self.assertEqual(len(fs), 20)

    def test_clean_flick_shape(self):
        s = report.summarize(run())
        self.assertAlmostEqual(s["peak_pos_med"], 0.5, delta=0.08)   # min-jerk is symmetric
        self.assertGreater(s["path_eff_med"], 0.95)
        self.assertEqual(s["corrections_per_flick"], 0)

    def test_overshoot_is_separated_from_clean(self):
        clean = report.summarize(run(overshoot=0.0))
        over = report.summarize(run(overshoot=0.25))
        self.assertGreater(over["flicks_with_correction_pct"], 80)
        self.assertEqual(clean["flicks_with_correction_pct"], 0)
        self.assertGreater(over["flicks_with_reversal_pct"], 80)
        self.assertEqual(over["corrections_per_flick"], 1)

    def test_peak_to_click_measured(self):
        s = report.summarize(run())
        self.assertIsNotNone(s["peak_to_click_ms_med"])


def at_125hz(events):
    """Re-report 1 kHz events the way a 125 Hz mouse would (sum per 8 ms window)."""
    out = {}
    for e in events:
        w = int(e["t"] // 8)
        o = out.setdefault(w, {"t": (w + 1) * 8.0, "dx": 0, "dy": 0, "b": 0})
        o["dx"] += e["dx"]; o["dy"] += e["dy"]; o["b"] |= e["b"]
    return [out[k] for k in sorted(out)]


class LowPollingRateTests(unittest.TestCase):
    def test_flick_count_survives_125hz(self):
        fs = flicks.extract(trace.from_events(at_125hz(synth.session(n_flicks=20))))
        self.assertEqual(len(fs), 20)

    def test_clicks_survive_125hz(self):
        fs = flicks.extract(trace.from_events(at_125hz(synth.session(n_flicks=20))))
        self.assertTrue(all(f.peak_to_click is not None for f in fs))


if __name__ == "__main__":
    unittest.main()
