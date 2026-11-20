.. _catalog_generator:

Catalog Generator
=================

AQUA-claima provides a generator of AQUA catalog entries for the AIMIP archive, the collection of
AMIP-style simulations of AI climate models stored on Levante. It follows the catalog generator of aqua-core
(``aqua catgen``, see the `AQUA documentation <https://aqua.readthedocs.io/en/latest/catalog_generator.html>`_),
but it is built for netCDF files instead of FDB sources.

The archive stores one netCDF file for each variable, in a CMIP-like tree::

    <institution>/<model>/<experiment>/<member>/<table>/<variable>/<grid>/<version>/<file>.nc

The same variable can be present in more than one version folder, and some files are truncated and cannot be opened.
The generator scans the archive and writes the catalog so that each source points only to the current and readable
version of each file. For this reason the catalog has to be generated again when new data are uploaded.

python -m aqua.claima.catgen.aimip -c <config_file>
---------------------------------------------------

This command scans the archive and writes the catalog entries of all the models and experiments.
The generator is not a subcommand of the ``aqua`` console.

.. option:: -c <config>, --config <config>

    The configuration file to use. A ``claima-aimip-config.yaml`` is available to be copied and edited.

.. option:: -l <loglevel>, --loglevel <loglevel>

    The logging level, following the python standards.

The generator can also be used from python:

.. code-block:: python

    from aqua.claima.catgen import AimipCatalogGenerator

    generator = AimipCatalogGenerator(config_path="claima-aimip-config.yaml")
    generator.generate_catalog()

Basic usage
^^^^^^^^^^^

To generate or update the catalog, follow these steps on the machine where the archive is stored:

1. Install AQUA and the claima project (``aqua install <machine>``, then ``aqua project install claima``).
   This copies the files used by the generator to ``.aqua/catgen``.
2. Clone the `DestinE-ClimateDT-catalog <https://github.com/DestinE-Climate-DT/Climate-DT-catalog/tree/main>`_
   repository to your preferred location.
3. Copy ``.aqua/catgen/claima-aimip-config.yaml`` and set the path of the cloned repository in it.
4. Run the command ``python -m aqua.claima.catgen.aimip -c claima-aimip-config.yaml``.
5. The catalog entries will be created in ``catalogs/<catalog_dir>`` of the ``DestinE-ClimateDT-catalog`` folder.

Scanning the archive opens every file and takes a few minutes. If ``inventory`` is set in the configuration file,
the result of the scan is saved to that file and read back by the following runs: delete the file to scan again.

.. note::

    ``README.md`` and ``machine.yaml`` of the catalog are not generated and have to be written by hand.

Configuration file
------------------

The configuration file ``claima-aimip-config.yaml`` contains the following keys:

- ``author``: the author of the catalog.
- ``machine``: the machine where the archive is stored. This field is mandatory.
- ``repos``: the path to the Climate-DT-catalog repository (``Climate-DT-catalog_path``). This field is mandatory.
- ``catalog_dir``: the folder in the Climate-DT-catalog where the catalog entries will be stored. This field is mandatory.
- ``archive_path``: the root folder of the archive. This field is mandatory.
  It is also the default value of the ``AIMIP_PATH`` intake parameter of the catalog.
- ``inventory``: a JSON file where the scan of the archive is saved and read back. This field is not mandatory.

Definitions
-----------

The description of the content of the archive is not in the configuration file but in ``claima-aimip.yaml``,
installed in ``.aqua/catgen`` together with the template of the catalog entries, ``claima-aimip-entry.j2``.
Any of its keys can be overridden by adding it to the configuration file.

- ``time_chunks``: the number of time steps in each dask chunk, for the ``monthly`` and ``daily`` sources.
- ``models``: the models to be included. For each AQUA model name:

  - ``base``: the folder of the model in the archive.
  - ``grid``: the AQUA grid of the data (``source_grid_name``), or ``false`` if regridding is not possible.
  - ``description``: the description of the model.
  - ``drop_variables``: variables to be ignored when opening the files. This field is not mandatory.

- ``experiments``: the AQUA experiment name of the experiment folders which are named differently in the archive.
  The key is ``<folder>``, or ``<model>/<folder>`` to rename the experiment of a single model.
- ``descriptions``: the description of each AQUA experiment.
- ``references``: the reference datasets (e.g. ERA5), which are few files not following the structure of the
  archive. Their sources are described here one by one, with ``description``, ``time_chunk`` and the list of
  ``urlpath`` relative to ``archive_path``.

To add a new model to the catalog it is enough to add it to ``models``.

Generated catalog
-----------------

The catalog has one entry for each model and experiment, with the same source names for all the models:

- ``monthly-atm2d`` and ``daily-atm2d``: variables without a vertical dimension.
- ``monthly-atm3d`` and ``daily-atm3d``: variables on pressure levels (``plev``) or model layers (``model_layer``).

When a model provides both the native (``gn``) and the regridded (``gr``) data, the regridded ones are the default
and the sources of the native data have the ``-native`` suffix.

The ensemble members are exposed through the ``realization`` intake parameter, which takes the full variant label:

.. code-block:: python

    from aqua import Reader

    reader = Reader(catalog="aimip", model="NeuralGCM", exp="aimip", source="monthly-atm2d", realization="r3i1p1f1")
    data = reader.retrieve(var="tas")

.. warning::

    Each variable is a separate file and not all the variables of a model are on the same pressure levels.
    The ``atm3d`` sources put them on the union of the levels: a variable is filled with missing values on the
    levels it does not have.

Selection of the files
^^^^^^^^^^^^^^^^^^^^^^

For each variable and member the files are selected as follows:

1. Files which cannot be opened are discarded.
2. The newest version wins: a file of an older version is kept only if it does not overlap in time with any file
   of a newer version.

The selected files are written in the catalog as glob patterns, one for each version folder. When a file has
been discarded only for some members, the pattern excludes them through their realization index,
e.g. ``tas_*_r[!2]i1p1f1_gn_197810-202412.nc``. A member without any valid file for a variable simply does not
have that variable.
