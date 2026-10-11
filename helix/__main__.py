import argparse
import json

from .analysis import flicks, report, trace


def main():
    ap = argparse.ArgumentParser(prog="helix")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="summarize flick metrics of a raw-input trace")
    a.add_argument("trace")
    a.add_argument("--json", action="store_true")
    args = ap.parse_args()
    events = trace.load_events(args.trace)
    s = report.summarize(flicks.extract(trace.from_events(events)))
    iv = trace.report_interval_ms(events)
    s["report_interval_ms"] = round(iv, 2) if iv else None
    s["clicks_logged"] = sum(1 for e in events if e.get("b", 0) & trace.LEFT_DOWN)
    if iv and iv > 3:
        print("WARNING: mouse reports every ~%.0f ms (~%.0f Hz). Correction detection is coarse; "
              "set the mouse to 1000 Hz for better data." % (iv, 1000 / iv))
    if not s["clicks_logged"]:
        print("WARNING: no clicks in this trace (peak_to_click unavailable).")
    print(json.dumps(s, indent=2) if args.json else report.format_summary(s))


main()
