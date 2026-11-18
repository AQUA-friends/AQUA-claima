# Changelog

All notable changes to aqua-claima are documented here.

## [Unreleased]

### Added
- Minimal plugin package `aqua.claima` for the aqua-core plugin contract v2 (DestinE-Climate-DT/AQUA#3278):
  `get_install_dirs()` entry point in `aqua.plugins`, project-scoped `analysis`, `collections` and `tools`
  configuration, and an example grid file installed into the flat `grids` folder.
- Tests for the namespace package, the contract shape and the presence of the listed config folders.

### Notes
- Soft version pins: `aqua-core>=1.2.4` (pyproject and `MIN_AQUA_CORE`) and `aqua-diagnostics>=0.26.0`.
  They must be raised to `aqua-core>=1.3.0` and `aqua-diagnostics>=0.27.0` before releasing 0.1.0.
