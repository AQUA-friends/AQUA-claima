.. _catalog_generator_aimip_claima:

Catalog Generator for aimip-claima
==================================

`aimip-claima <https://github.com/CliDyn/aimip-claima>`_ runs AI climate emulators as climate experiments.
A second generator writes the AQUA catalog entries of its output, once this has been converted to the
CF conventions. It has the same structure as the generator of the AIMIP archive (see :ref:`catalog_generator`).

The converted output has one folder for each set of runs, with a few netCDF files for each model::

    <experiment>/<model>/[<realm>/]<file>.nc

The generator looks in each model folder for a list of known files, and writes one catalog entry for each
model and experiment with one source for each file found. Model and experiment are named after their folders.

.. warning::

    Only the 3D files are in the catalog for now: ``atmosphere/monthly_levels.nc`` and ``ocean/monthly_thetao.nc``,
    which only ``archesclimate-ssp`` provides. In ``monthly_mean_predictions.nc`` the ``member`` dimension comes
    before ``time``, which cdo does not support (``Time must be the first dimension``): these files are not
    listed in the definitions, and the generator refuses any file with this structure.

python -m aqua.claima.catgen.aimip_claima -c <config_file>
----------------------------------------------------------

This command scans the experiment folders and writes the catalog entries of all the models found.

.. option:: -c <config>, --config <config>

    The configuration file to use. A ``claima-aimip-claima-config.yaml`` is available to be copied and edited.

.. option:: -l <loglevel>, --loglevel <loglevel>

    The logging level, following the python standards.

The generator can also be used from python:

.. code-block:: python

    from aqua.claima.catgen import AimipClaimaCatalogGenerator

    generator = AimipClaimaCatalogGenerator(config_path="claima-aimip-claima-config.yaml")
    generator.generate_catalog()

The steps are the same as for the AIMIP archive: install the claima project, clone the Climate-DT-catalog
repository, copy ``.aqua/catgen/claima-aimip-claima-config.yaml`` and set the path of the repository in it,
then run the command. ``README.md`` and ``machine.yaml`` of the catalog are not generated.

Configuration file
------------------

The configuration file ``claima-aimip-claima-config.yaml`` contains the following keys:

- ``author``: the author of the catalog.
- ``machine``: the machine where the output is stored. This field is mandatory.
- ``repos``: the path to the Climate-DT-catalog repository (``Climate-DT-catalog_path``). This field is mandatory.
- ``catalog_dir``: the folder in the Climate-DT-catalog where the catalog entries will be stored. This field is mandatory.
- ``archive_path``: the folder containing the experiment folders. This field is mandatory.
  It is also the default value of the ``CLAIMA_PATH`` intake parameter of the catalog.
- ``experiments``: the experiment folders to include. All the folders of ``archive_path`` if missing.

Definitions
-----------

The files to look for are defined in ``claima-aimip-claima.yaml``, installed in ``.aqua/catgen`` together with the
template of the catalog entries, ``claima-aimip-claima-entry.j2``. Any of its keys can be overridden by adding it
to the configuration file.

- ``sources``: the sources of the catalog. For each AQUA source name:

  - ``file``: the file to look for, relative to the model folder. This field is mandatory.
  - ``description``: the description of the source. Number of levels, variables and period are read from the
    file and added to it.
  - ``time_chunk``: the number of time steps in each dask chunk. Default is 1.
  - ``grid``: the AQUA grid of the data (``source_grid_name``). Default is ``lon-lat``.
  - ``drop_variables``: variables to be ignored when opening the file.

- ``descriptions``: the description of each experiment folder.
- ``models``: the description of each model folder. If missing, the ``source`` global attribute of the files is used.

To add a file to the catalog it is enough to add a source to ``sources``.

Generated catalog
-----------------

.. code-block:: python

    from aqua import Reader

    reader = Reader(catalog="claima", model="archesclimate-ssp", exp="aimip-claima-5y", source="monthly-atm3d")
    data = reader.retrieve()

- ``monthly-atm3d``: ``hus``, ``ta``, ``ua``, ``va`` and ``zg`` on 17 pressure levels. No fixer is defined:
  the AQUA convention renames them to ``q``, ``t``, ``u`` and ``v`` (``zg`` keeps its name) and converts the
  levels to Pa.
- ``monthly-oce3d``: ``thetao`` on 10 depth levels, converted to K.

The 3D fields have missing values below the surface and on land, so that the mask changes with the level.
For this reason the two sources use the ``lon-lat-skipna`` grid: with ``lon-lat`` the regridder applies the mask of
the first level to all the levels. ``time_bnds`` is dropped, because the field mean of a whole dataset fails on it.

Selection of the files
^^^^^^^^^^^^^^^^^^^^^^

A file listed in the definitions is skipped, with a warning, if:

1. it cannot be opened;
2. ``time`` is not the first dimension of all its variables;
3. its variables have more than one vertical dimension.

A model without any valid file does not get an entry.
