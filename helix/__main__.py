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
    s = report.summarize(flicks.extract(trace.load(args.trace)))
    print(json.dumps(s, indent=2) if args.json else report.format_summary(s))


main()
