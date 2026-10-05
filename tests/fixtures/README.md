# Test fixtures

Local HTML samples used by unit, smoke, and perf tests.

**No test in `unit/`, `smoke/`, or `perf/` may access the network.** Tests that
need real network access belong in `e2e/` and must be marked with
`@pytest.mark.network`.
