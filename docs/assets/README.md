# README visuals

[Back to the project](../../README.md)

`overview.svg` is an original explanatory workflow illustration, not a product screenshot.

`demo.png`: A styled transcript of real CLI output from the included repository fixture. It is not a screenshot of an application dashboard.

The demo uses synthetic local data; it does not represent a production deployment or a live model evaluation.

## Reproduce the data

Run from the repository root after following the main README installation steps:

```bash
PYTHONPATH=src python3 -m memorylint scan --repo examples/demo
# Exit 1 is expected: the fixture has two stale candidates.
```

Timing values and generated paths may differ between runs. Screenshots show the relevant report view; complete artifacts stay in your selected output directory.
