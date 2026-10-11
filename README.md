# Helix — AI aim coach (experiment 1)

Question: can raw mouse input alone give reproducible braking/correction metrics per flick?

## On the Windows PC (needs only Python 3.10+, no pip installs)
    python -m helix.capture.rawinput_logger data/run01_fast.jsonl     # Ctrl+C after the scenario
Play one fixed small-target static-clicking scenario, 10-15 runs. Do runs in two induced
conditions: "fast and sloppy" and "slow and controlled" (name files accordingly).

## Analyze (any OS)
    python -m helix analyze data/run01_fast.jsonl
    python -m unittest discover -s tests -t .

Success criterion: the metrics separate the two induced conditions, and repeat within a condition.
Metric definitions: docstring of `helix/analysis/flicks.py` (versioned via METRICS_VERSION).
