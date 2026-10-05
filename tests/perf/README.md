# Performance tests

Quantitative threshold assertions that guard against performance regressions.
No network access. Hundreds of milliseconds scale.

Not run by the default `pytest` invocation — run explicitly:

```bash
uv run pytest tests/perf
```

File naming mirrors the capability under test with a `_perf` suffix:
`prune.py` -> `test_prune_perf.py`.
