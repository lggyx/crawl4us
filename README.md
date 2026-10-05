# crawl4us

LLM-ready web crawler: any website into clean Markdown.

Built for the G10 crowdtest — a Coding-class task that turns real engineering work
into a model evaluation exercise.

## Status

Early scaffolding phase. No capabilities implemented yet.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture, layout, and conventions
- [`docs/crawl4ai-analysis.md`](docs/crawl4ai-analysis.md) — analysis of the reference implementation
- [`docs/DESIGN.md`](docs/DESIGN.md) — early design notes

## Architecture at a glance

One capability per file, flat layout, CLI as the only entry point.

```
src/crawl4us/
├── cli.py            # CLI entry point (the only public interface)
├── types.py          # shared data types
├── crawl.py          # pipeline orchestration
├── fetch_http.py     # HTTP static fetching
├── parse_dom.py      # HTML -> lxml DOM
├── prune.py          # O(N) content pruning
└── render_md.py      # DOM -> Markdown
```

Every capability ships with four kinds of tests: `unit`, `smoke`, `e2e`, `perf`.

## Development

```bash
uv sync                          # install dependencies
uv run pytest                    # unit + smoke + e2e
uv run pytest tests/perf         # performance tests
uv run ruff check .              # lint
uv run mypy src                  # type check
```

## License

Apache-2.0
