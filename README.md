# AQUA-claima

AQUA configuration for the CLAIMA project.

`aqua-claima` is an [aqua-core](https://github.com/DestinE-Climate-DT/AQUA) **project**: a plugin package that ships
the CLAIMA configuration (analysis, collections, tools and extra grids) and runs the tools of
[aqua-diagnostics](https://github.com/DestinE-Climate-DT/AQUA-diagnostics). It is registered through the `aqua.plugins`
entry point `claima` (plugin contract v2). The name "project" is provisional in aqua-core.

At install time aqua-core copies (or links, in editable mode) the `analysis`, `collections` and `tools` folders into
`~/.aqua/<folder>/claima`, and merges the files in `grids` into the flat `~/.aqua/grids`.

## Install

Work in progress: requires aqua-core 1.3.0 and aqua-diagnostics 0.27.0 (not released yet).

```bash
mamba env create -f environment.yml          # or environment-dev.yml, with ../AQUA and ../AQUA-diagnostics
aqua install <machine>                       # aqua-core and the diagnostics project (-c: aqua-core only)
aqua project install claima                  # add claima and make it the active project (-e <path>: editable)
aqua project set claima                      # switch back to claima later, e.g. after `aqua project set diagnostics`
aqua analysis -p claima -c <catalog> -m <model> -e <exp> -s <source>
```

`aqua list` shows the installed projects and the active one; `aqua project update claima` refreshes the installed files.

## Add a collection

1. Add `aqua/claima/config/collections/jinja/<collection>/config-<collection>-<name>.j2`, with dates taken from the
   experiment kinds (`{{ default.startdate }}`), and the same file with fixed dates in `collections/legacy/<collection>/`.
2. Add any new date key to every kind of `aqua/claima/config/analysis/claima-experiment-kind.yaml`.
3. In `aqua/claima/config/analysis/config.aqua-analysis.yaml`, add the tool to `cli` if missing, the collection to
   `diagnostics` with `config: "${AQUA_CONFIG}/collections/${AQUA_PROJECT}/jinja/<collection>/<file>.j2"`, and the
   collection to a `run` group.
4. Add new tool keys to `KNOWN_DIAGNOSTIC_KEYS` in `tests/test_config_contract.py` and run the tests.

## Generate the AIMIP catalog

`aqua/claima/catgen/aimip.py` writes the `aimip` catalog of
[Climate-DT-catalog](https://github.com/DestinE-Climate-DT/Climate-DT-catalog) from the content of the AIMIP archive
on Levante, in the style of the `aqua catgen` generator of aqua-core. It scans the archive, so that each source points
only to the current and readable version of each file: run it again after new data are uploaded.

```bash
cp aqua/claima/catgen/config-aimip.yaml .    # then set repos.Climate-DT-catalog_path
python -m aqua.claima.catgen.aimip -c config-aimip.yaml
```

Models, grids, experiment names and the reference datasets are defined in the configuration file. `README.md` and
`machine.yaml` of the catalog are not generated.

## Tests

```bash
pytest tests -m claima
```

Contract, install (temporary `HOME`) and analysis dry-run tests; see [CONTRIBUTING.md](CONTRIBUTING.md) for the CI.
