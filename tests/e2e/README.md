# End-to-end tests

Full-pipeline tests that invoke the CLI as a subprocess, exercising the real
command-line surface.

Tests that require real network access must be marked with
`@pytest.mark.network` so they can be deselected by default.
