# Changelog

All notable changes to aqua-claima are documented here.

## [Unreleased]

- Minimal `aqua.claima` plugin package for the aqua-core plugin contract v2, with project `analysis`, `collections` and `tools` configuration and one extra grid (#1)
- Temporary minimum versions `aqua-core>=1.2.4` and `aqua-diagnostics>=0.26.0`, to be raised to 1.3.0 and 0.27.0 before releasing 0.1.0 (#1)
- Second collection `climate_metrics` (Gregory plot), legacy collections and the `claima-experiment-kind.yaml` experiment kinds (#2)
- Config contract, install and analysis dry-run tests (#2)
- CI workflows (tests in cross-check mode, PyPI, ruff, conda relock), dependabot, environment files, agent rules and contribution templates (#2)
- `aqua.claima.preprocess.dlesym` rewrites DLESyM output in HEALPix nested order, readable with the `hpz6-nested` grid (#5)
