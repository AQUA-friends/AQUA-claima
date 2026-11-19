# AQUA-claima

AQUA configuration for the CLAIMA project.

`aqua-claima` is an [aqua-core](https://github.com/DestinE-Climate-DT/AQUA) plugin that ships the CLAIMA
project configuration (analysis, collections, tools and extra grids) through the `aqua.plugins` entry point,
using the plugin contract v2. At install time aqua-core copies the `analysis`, `collections` and `tools`
folders into `~/.aqua/<folder>/claima`, and the files in `grids` into the flat `~/.aqua/grids`.

## Install

Work in progress: requires the aqua-core version implementing the plugin contract v2.

```bash
pip install -e .
aqua install <machine> -c                  # aqua-core configuration, if not installed yet
aqua project install claima                # or: aqua project install claima -e <path-to-AQUA-claima> (editable)
```

## Tests

```bash
pytest tests -m claima
```
