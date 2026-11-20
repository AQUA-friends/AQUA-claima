# AQUA-claima Repository Instructions

Read this file after AQUA's remotely retrieved `AGENTS.common.md`, as directed by
this repository's `AGENTS.md`. AQUA's shared rules take precedence for common
matters; this file contains claima-specific instructions.

`aqua.claima` ships the configuration of the CLAIMA project as an aqua-core **project plugin**
(`aqua.plugins` entry point `claima`, plugin contract v2). It depends on aqua-core
([DestinE-Climate-DT/AQUA](https://github.com/DestinE-Climate-DT/AQUA)) and aqua-diagnostics
([DestinE-Climate-DT/AQUA-diagnostics](https://github.com/DestinE-Climate-DT/AQUA-diagnostics)).
Diagnostics code, collection schema and `aqua analysis` rules live there: read aqua-diagnostics' `AGENTS.repo.md`
before editing collections or the analysis config. The name "project" is provisional.

## Repository Map

| Path | Content |
|---|---|
| `aqua/claima/__init__.py` | `get_install_dirs()`: the plugin contract (`config`, `flat`, `templates`, `files`) |
| `aqua/claima/config/analysis/` | `config.aqua-analysis.yaml` and `claima-experiment-kind.yaml`, installed in `~/.aqua/analysis/claima` |
| `aqua/claima/config/collections/{jinja,legacy}/<collection>/` | Collection configs, installed in `~/.aqua/collections/claima` |
| `aqua/claima/config/tools/` | Tool static files, installed in `~/.aqua/tools/claima` |
| `aqua/claima/config/grids/` | Extra files merged one by one into the flat `~/.aqua/grids`: names must not collide with core's (prefix `claima-`) |
| `aqua/claima/catgen/` | Catalog generators for CLAIMA data, run with `python -m` (`aimip.py` for the AIMIP archive, `aimip_claima.py` for the output of aimip-claima; shared code in `util.py`) |
| `aqua/claima/config/catgen/` | Entry templates, definitions and sample configurations of the catalog generators, merged one by one into the flat `~/.aqua/catgen` (prefix `claima-`) |
| `docs/sphinx/` | Sphinx documentation (`pip install -e .[docs]`, then `make html` in `docs/sphinx`) |
| `tests/` | Contract, install and analysis dry-run tests (marker `claima`) |

## Rules

- Analysis configs refer to files with `${AQUA_CONFIG}/<folder>/${AQUA_PROJECT}/...`, never with a hard-coded project name
- Every collection exists in `jinja/` (rendered with each kind of `claima-experiment-kind.yaml`) and `legacy/` (fixed dates)
- A new tool key in a collection must be added to `KNOWN_DIAGNOSTIC_KEYS` in `tests/test_config_contract.py`
- `catgen` stays a flat aqua-core folder, never project-scoped: the files of `aqua/claima/config/catgen/` are merged into it as `files`, and the generators read them with `ConfigContext.get_folder("catgen")`, as the aqua-core `catgen` does
- Every test module has `pytestmark = pytest.mark.claima`; tests needing aqua-diagnostics or unreleased aqua-core verbs skip with a reason
- Every PR adds one short line under `## [Unreleased]` in `CHANGELOG.md`, citing the PR

```bash
pytest tests -m claima        # data-free, temporary HOME for the install tests
```
