# Helix — AI aim coach (experiment 1)

Question: can raw mouse input alone give reproducible braking/correction metrics per flick?

## On the Windows PC (needs only Python 3.10+, no pip installs)
    python -m helix.capture.rawinput_logger data/run01_fast.jsonl     # Ctrl+C after the scenario
Play one fixed small-target static-clicking scenario, 10-15 runs. Do runs in two induced
conditions: "fast and sloppy" and "slow and controlled" (name files accordingly).

## Streaming to the Mac (no file copying)
Mac (same network):
    python3 -m helix.capture.receiver            # listens on port 8765, saves to data/
Windows:
    python -m helix.capture.rawinput_logger --send <MAC_IP>:8765 --name A_rapido_01
Ctrl+C on Windows ends the run; the Mac saves data/A_rapido_01.jsonl and prints the summary.
Unencrypted and unauthenticated: trusted home network only. Add `--out file.jsonl` to also keep a local copy.

## Analyze (any OS)
    python -m helix analyze data/run01_fast.jsonl
    python -m unittest discover -s tests -t .

Success criterion: the metrics separate the two induced conditions, and repeat within a condition.
Metric definitions: docstring of `helix/analysis/flicks.py` (versioned via METRICS_VERSION).
