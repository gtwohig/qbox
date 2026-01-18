# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-01-18

### Added

- Initial working implementation of QBox
- Background event loop manager (`BackgroundLoopManager`) running on a daemon thread
- Lazy composition of operations (arithmetic, item access, attribute access, calls)
- Force-evaluation triggers (comparisons, boolean context, type conversions, iteration)
- Reference replacement on observation with configurable scope (`locals`, `stack`, `globals`)
- Type mimicry via ABC registration (`mimic_type` parameter)
- Optional `isinstance` patching (`enable_qbox_isinstance`, `qbox_isinstance` context manager)
- `observe()` function for explicit observation
- `start` parameter: `'soon'` (eager, default) or `'observed'` (lazy)
- `repr_observes` parameter to control whether `repr()` triggers observation
- `cancel_on_delete` parameter to control cleanup behavior on garbage collection
- Composed QBoxes inherit `start='soon'` if any parent uses it
- Exception caching and re-raising
- Thread-safe value caching
- Comprehensive documentation (how-it-works, observation, isinstance guides)

### Changed

- Complete rewrite from concept to working implementation
- Now requires Python 3.10+ (uses modern type syntax)
- Uses `uv` for package management (replaces Poetry/Nox)
- Uses `ruff` for linting and formatting (replaces flake8/black)

### Removed

- Poetry and Nox configuration (replaced with uv)
- Old test infrastructure
