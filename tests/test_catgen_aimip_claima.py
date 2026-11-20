"""Tests for the aimip-claima catalog generator, on a small archive written in the temporary directory."""

import os

import netCDF4
import pytest
from conftest import CONFIG_ROOT

from aqua.claima.catgen import AimipClaimaCatalogGenerator
from aqua.core.configurer import ConfigContext
from aqua.core.util import dump_yaml, load_yaml

pytestmark = pytest.mark.claima


def _write(path, variables, source=None):
    """Write a tiny CF file with bounds: variables maps each name to its dimensions."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with netCDF4.Dataset(path, "w") as data:
        sizes = {"time": 3, "bnds": 2, "plev": 4, "member": 1}
        for dim in {"time", "bnds"} | {d for dims in variables.values() for d in dims}:
            data.createDimension(dim, sizes.get(dim, 2))
        time = data.createVariable("time", "f8", ("time",))
        time.units, time.calendar, time.bounds = "days since 1850-01-01", "proleptic_gregorian", "time_bnds"
        time[:] = [60340.5, 60371.0, 60401.5]  # mid-month, from 2015-03 to 2015-05
        data.createVariable("time_bnds", "f8", ("time", "bnds"))
        for name, dims in variables.items():
            data.createVariable(name, "f4", dims)
        if source:
            data.source = source


@pytest.fixture
def configcontext(tmp_path):
    """AQUA configuration folder with the catgen files shipped by aqua-claima."""
    configdir = os.path.join(tmp_path, "aqua")
    os.makedirs(configdir)
    dump_yaml(os.path.join(configdir, "config-aqua.yaml"), {"machine": "test"})
    os.symlink(os.path.join(CONFIG_ROOT, "catgen"), os.path.join(configdir, "catgen"))
    return ConfigContext(configdir=configdir)


@pytest.fixture
def generator(tmp_path, configcontext):
    """Generator on an archive with one complete model, one with member before time and one unreadable file."""
    run = os.path.join(tmp_path, "archive", "run-5y")
    grid = ("time", "plev", "lat", "lon")
    _write(os.path.join(run, "good", "atmosphere", "monthly_levels.nc"), {"ta": grid, "zg": grid}, source="Good model")
    _write(os.path.join(run, "good", "atmosphere", "monthly_surface.nc"), {"tas": ("time", "lat", "lon")})
    _write(os.path.join(run, "good", "atmosphere", "not_listed.nc"), {"ta": grid})
    _write(os.path.join(run, "member-first", "atmosphere", "monthly_levels.nc"), {"ta": ("member", *grid)})
    os.makedirs(os.path.join(run, "truncated", "atmosphere"))
    with open(os.path.join(run, "truncated", "atmosphere", "monthly_levels.nc"), "wb") as stream:
        stream.write(b"\x89HDF\r\n\x1a\ntruncated")
    os.makedirs(os.path.join(tmp_path, "archive", "scripts"))

    config = {
        "machine": "test",
        "repos": {"Climate-DT-catalog_path": os.path.join(tmp_path, "repo")},
        "catalog_dir": "claima",
        "archive_path": os.path.join(tmp_path, "archive"),
        "sources": {
            "monthly-atm3d": {"file": "atmosphere/monthly_levels.nc", "description": "3D data", "time_chunk": 12},
            "monthly-atm2d": {"file": "atmosphere/monthly_surface.nc", "drop_variables": ["time_bnds"], "grid": "r100"},
        },
        "descriptions": {"run-5y": "Test runs"},
    }
    config_path = os.path.join(tmp_path, "config.yaml")
    dump_yaml(config_path, config)
    return AimipClaimaCatalogGenerator(config_path=config_path, configcontext=configcontext, loglevel="ERROR")


def test_sources_describe_the_files(generator):
    """Fails if a source misses the path, grid, chunks or content of its file, or bounds count as variables."""
    generator.generate_catalog()
    sources = load_yaml(os.path.join(generator.catalog_dir, "catalog", "good", "run-5y.yaml"), jinja=False)["sources"]

    assert list(sources) == ["monthly-atm3d", "monthly-atm2d"]
    source = sources["monthly-atm3d"]
    assert source["description"] == "3D data (4 levels: ta, zg), 2015-03 to 2015-05"
    assert source["args"]["urlpath"] == "{{CLAIMA_PATH}}/run-5y/good/atmosphere/monthly_levels.nc"
    assert source["args"]["chunks"] == {"time": 12}
    assert source["metadata"]["source_grid_name"] == "lon-lat"
    assert "drop_variables" not in source["args"]["xarray_kwargs"]

    source = sources["monthly-atm2d"]
    assert source["description"] == "monthly-atm2d (tas), 2015-03 to 2015-05"
    assert source["args"]["xarray_kwargs"]["drop_variables"] == ["time_bnds"]
    assert source["metadata"]["source_grid_name"] == "r100"
    assert source["args"]["chunks"] == {"time": 1}


def test_unreadable_files_are_skipped(generator):
    """Fails if a model gets an entry from a truncated file or from one with member before time."""
    generator.generate_catalog()
    catalog = load_yaml(os.path.join(generator.catalog_dir, "catalog.yaml"), jinja=False)

    assert catalog["metadata"]["parameters"]["CLAIMA_PATH"]["default"] == generator.archive
    assert {model: entry["description"] for model, entry in catalog["sources"].items()} == {"good": "Good model"}
    assert os.listdir(os.path.join(generator.catalog_dir, "catalog")) == ["good"]

    main = load_yaml(os.path.join(generator.catalog_dir, "catalog", "good", "main.yaml"), jinja=False)["sources"]
    assert main == {
        "run-5y": {"description": "Test runs", "driver": "yaml_file_cat", "args": {"path": "{{CATALOG_DIR}}/run-5y.yaml"}}
    }


def test_header_errors(generator, tmp_path):
    """Fails if a file with member before time, or with two vertical dimensions, is accepted."""
    run = os.path.join(tmp_path, "archive", "run-5y")
    with pytest.raises(ValueError, match="time is not the first dimension of ta"):
        generator.read_header(os.path.join(run, "member-first", "atmosphere", "monthly_levels.nc"))

    path = os.path.join(tmp_path, "mixed.nc")
    _write(path, {"ta": ("time", "plev", "lat", "lon"), "thetao": ("time", "depth", "lat", "lon")})
    with pytest.raises(ValueError, match="more than one vertical dimension"):
        generator.read_header(path)


def test_selected_experiment_folders(generator, tmp_path):
    """Fails if a missing experiment folder is silently ignored, or the model description is not overridden."""
    generator.config["models"] = {"good": "Described in the configuration"}
    generator.generate_catalog()
    catalog = load_yaml(os.path.join(generator.catalog_dir, "catalog.yaml"), jinja=False)
    assert catalog["sources"]["good"]["description"] == "Described in the configuration"

    generator.config["experiments"] = ["missing"]
    with pytest.raises(FileNotFoundError, match="missing"):
        generator.generate_catalog()


def test_missing_configuration_key(tmp_path, configcontext):
    """Fails if a configuration without the archive path is accepted."""
    config_path = os.path.join(tmp_path, "config.yaml")
    dump_yaml(config_path, {"machine": "test", "catalog_dir": "claima"})
    with pytest.raises(ValueError, match="archive_path, repos.Climate-DT-catalog_path"):
        AimipClaimaCatalogGenerator(config_path=config_path, configcontext=configcontext)


def test_shipped_definitions(configcontext):
    """Fails if the shipped definitions and sample configuration do not make a complete configuration."""
    generator = AimipClaimaCatalogGenerator(
        config_path=os.path.join(CONFIG_ROOT, "catgen", "claima-aimip-claima-config.yaml"), configcontext=configcontext
    )
    assert generator.config["sources"]["monthly-atm3d"]["file"] == "atmosphere/monthly_levels.nc"
    assert generator.config["experiments"] == ["aimip-claima-5y"]
    assert generator.catalog_dir == os.path.join("/path/to/Climate-DT-catalog", "catalogs", "claima")
