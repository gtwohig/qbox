# QBox Repository Guidelines

## Quick Reference

```bash
uv sync                                    # Install dependencies
uv run pytest                              # Run tests (100% coverage required)
uv run ruff check src tests --fix          # Lint and auto-fix
uv run ruff format src tests               # Format code
uv run ty check src                        # Type check
uv run sphinx-build -b html docs docs/_build/html  # Build docs
```

## Architecture

```
src/qbox/
├── __init__.py      # Public API exports
├── _loop.py         # BackgroundLoopManager (singleton event loop thread)
├── _isinstance.py   # Opt-in transparent isinstance support
├── qbox.py          # Core QBox class
├── qbox.pyi         # Type stubs
└── py.typed         # PEP 561 marker
```

**QBox** wraps awaitables, runs them on a background thread, caches results.

**Magic methods**: Lazy ops (`+`, `[]`, `.attr`) return new QBox. Force ops (`==`, `bool`, `str`, `len`, `in`, `iter`) block and return concrete values.

**Observation**: `observe(box, scope='locals'|'stack'|'globals')` forces evaluation and replaces references.

## Code Standards

- Python 3.10+ (use `|` for unions)
- 100% test coverage
- Google-style docstrings
- 88 char line length
- Use `QBox._qbox_is_qbox(obj)` for runtime type checks

## Docs

Sources in `docs/`, key files: `how-it-works.rst`, `observation.rst`, `isinstance.rst`, `static-typing.rst`.
