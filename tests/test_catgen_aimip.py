"""Tests for the AIMIP catalog generator, on a small archive written in the temporary directory."""

import glob
import os

import netCDF4
import pytest

from aqua.claima.catgen import AimipCatalogGenerator
from aqua.core.util import dump_yaml, load_yaml

pytestmark = pytest.mark.claima

BASE = os.path.join("Inst", "MOD")
OLD, NEW = "v20260101", "v20260201"


def _write(archive, exp, member, var, version, period="197810-197812", dims=("time", "lat", "lon"), valid=True):
    """Write one file of the archive: a tiny netCDF file, or an unreadable one if valid is False."""
    folder = os.path.join(archive, BASE, exp, member, "Amon", var, "gn", version)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{var}_Amon_MOD_{exp}_{member}_gn_{period}.nc")
    if not valid:
        with open(path, "wb") as stream:
            stream.write(b"\x89HDF\r\n\x1a\ntruncated")
        return
    with netCDF4.Dataset(path, "w") as data:
        for dim in dims:
            data.createDimension(dim, 2)
        data.createVariable(var, "f4", dims)


@pytest.fixture
def generator(tmp_path):
    """Generator on an archive with a re-uploaded file (r2), an unreadable one (r3) and a renamed experiment."""
    archive = os.path.join(tmp_path, "archive")
    for member in ("r1i1p1f1", "r2i1p1f1", "r3i1p1f1"):
        _write(archive, "aimip", member, "tas", OLD, valid=member != "r3i1p1f1")
        _write(archive, "aimip", member, "ta", OLD, dims=("time", "plev", "lat", "lon"))
    _write(archive, "aimip", "r2i1p1f1", "tas", NEW)
    _write(archive, "aimip-2k", "r1i1p1f1", "tas", OLD)

    config = {
        "machine": "test",
        "repos": {"Climate-DT-catalog_path": os.path.join(tmp_path, "repo")},
        "catalog_dir": "aimip",
        "archive_path": archive,
        "inventory": os.path.join(tmp_path, "inventory.json"),
        "time_chunks": {"monthly": 12},
        "models": {"MOD": {"base": BASE, "grid": "lon-lat", "description": "Test model"}},
        "experiments": {"aimip-2k": "aimip-p2k"},
        "descriptions": {"aimip": "AIMIP simulation"},
        "references": {
            "OBS": {
                "description": "Test reference",
                "experiments": {
                    "v1": {
                        "description": "Reference data",
                        "sources": {"monthly": {"description": "monthly data", "time_chunk": 1, "urlpath": ["OBS/pr.nc"]}},
                    }
                },
            }
        },
    }
    config_path = os.path.join(tmp_path, "config.yaml")
    dump_yaml(config_path, config)
    return AimipCatalogGenerator(config_path=config_path, loglevel="ERROR")


def test_sources_select_current_readable_files(generator):
    """Fails if a superseded or unreadable file is matched, or a current one is missed, for any member."""
    generator.generate_catalog()
    catalog = os.path.join(generator.catalog_dir, "catalog", "MOD")
    sources = load_yaml(os.path.join(catalog, "aimip.yaml"), jinja=False)["sources"]

    assert list(sources) == ["monthly-atm2d", "monthly-atm3d"]
    source = sources["monthly-atm2d"]
    folder = "{{AIMIP_PATH}}/Inst/MOD/aimip/{{realization}}/Amon/tas/gn"
    assert source["args"]["urlpath"] == [
        f"{folder}/{OLD}/tas_*_r[!23]i1p1f1_gn_197810-197812.nc",
        f"{folder}/{NEW}/tas_*_gn_*.nc",
    ]
    assert source["parameters"]["realization"]["allowed"] == ["r1i1p1f1", "r2i1p1f1", "r3i1p1f1"]
    assert source["metadata"]["source_grid_name"] == "lon-lat"
    assert source["args"]["chunks"] == {"time": 12}

    expected = {"r1i1p1f1": [OLD], "r2i1p1f1": [NEW], "r3i1p1f1": []}
    for member, versions in expected.items():
        files = [
            f
            for pattern in source["args"]["urlpath"]
            for f in glob.glob(pattern.replace("{{AIMIP_PATH}}", generator.archive).replace("{{realization}}", member))
        ]
        assert [os.path.basename(os.path.dirname(f)) for f in files] == versions


def test_catalog_structure(generator):
    """Fails if experiments are not renamed, or the main and catalog files miss a model, experiment or parameter."""
    generator.generate_catalog()
    main = load_yaml(os.path.join(generator.catalog_dir, "catalog", "MOD", "main.yaml"), jinja=False)["sources"]
    assert list(main) == ["aimip", "aimip-p2k"]
    assert main["aimip"]["description"] == "AIMIP simulation, 3 members"
    assert main["aimip-p2k"]["args"]["path"] == "{{CATALOG_DIR}}/aimip-p2k.yaml"

    catalog = load_yaml(os.path.join(generator.catalog_dir, "catalog.yaml"), jinja=False)
    assert catalog["metadata"]["parameters"]["AIMIP_PATH"]["default"] == generator.archive
    assert {model: entry["description"] for model, entry in catalog["sources"].items()} == {
        "MOD": "Test model",
        "OBS": "Test reference",
    }

    reference = load_yaml(os.path.join(generator.catalog_dir, "catalog", "OBS", "v1.yaml"), jinja=False)["sources"]["monthly"]
    assert reference["args"]["urlpath"] == ["{{AIMIP_PATH}}/OBS/pr.nc"]
    assert "parameters" not in reference


def test_inventory_is_saved_and_reused(generator):
    """Fails if the scan misses the unreadable file, or the saved inventory is not used instead of the archive."""
    inventory = generator.get_inventory()
    broken = f"Inst/MOD/aimip/r3i1p1f1/Amon/tas/gn/{OLD}/tas_Amon_MOD_aimip_r3i1p1f1_gn_197810-197812.nc"
    assert inventory["broken"] == [broken]
    assert inventory["hdr"]["Inst/MOD|Amon|gn|ta"]["dims"] == ["time", "plev", "lat", "lon"]

    generator.archive = os.path.join(generator.archive, "missing")
    assert generator.get_inventory() == inventory


def test_missing_configuration_key(tmp_path):
    """Fails if a configuration without the archive path is accepted."""
    config_path = os.path.join(tmp_path, "config.yaml")
    dump_yaml(config_path, {"machine": "test", "catalog_dir": "aimip", "models": {"MOD": {}}})
    with pytest.raises(ValueError, match="archive_path, repos.Climate-DT-catalog_path"):
        AimipCatalogGenerator(config_path=config_path)
