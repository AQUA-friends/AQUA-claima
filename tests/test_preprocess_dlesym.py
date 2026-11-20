"""Tests for the DLESyM HEALPix preprocessing."""

import os

import numpy as np
import pytest
import xarray as xr

from aqua.claima.preprocess import DlesymHealpix

pytestmark = pytest.mark.claima

# value of each cell: 100 * face + 10 * height + width
CODE = 100 * np.arange(12)[:, None, None] + 10 * np.arange(2)[None, :, None] + np.arange(2)[None, None, :]
# nested order within a face is (ix, iy) = (0, 0), (1, 0), (0, 1), (1, 1), with ix = 1 - height and iy = 1 - width
NESTED_FACE = [11, 1, 10, 0]


@pytest.fixture
def dlesym_data():
    """A nside=2 dataset on the DLESyM layout, with a 2D and a 3D variable."""
    coords = {dim: np.arange(size, dtype="int32") for dim, size in zip(("face", "height", "width"), (12, 2, 2))}
    coords.update(time=[10.5, 11.5, 12.5], plev=[85000.0])
    tas = (np.arange(3)[:, None, None, None] * 1000 + CODE).astype("float32")
    data = xr.Dataset(
        {
            "tas": (("time", "face", "height", "width"), tas, {"units": "K"}),
            "ta": (("time", "plev", "face", "height", "width"), tas[:, None] + 0.5),
        },
        coords=coords,
        attrs={"source_id": "DLESyM"},
    )
    data.time.attrs = {"units": "days since 1850-01-01 00:00:00", "calendar": "gregorian"}
    return data


def test_to_nested_reorders_cells(dlesym_data):
    """A wrong flip, transpose or face order of the cells would change the hard-coded nested sequence."""
    nested = DlesymHealpix().to_nested(dlesym_data)
    expected = np.concatenate([100 * face + np.array(NESTED_FACE) for face in range(12)])

    assert nested.tas.dims == ("time", "cells")
    assert nested.ta.dims == ("time", "plev", "cells")
    assert nested.tas.isel(time=1).values.tolist() == (1000 + expected).tolist()
    assert nested.ta.isel(time=2, plev=0).values.tolist() == (2000.5 + expected).tolist()
    assert not {"face", "height", "width"} & set(nested.variables)
    assert nested.healpix.attrs == {"grid_mapping_name": "healpix", "healpix_nside": 2, "healpix_order": "nested"}
    assert nested.tas.attrs == {"units": "K", "grid_mapping": "healpix"}
    assert nested.attrs["source_id"] == "DLESyM"
    assert "HEALPix nested order (nside=2)" in nested.attrs["history"]


@pytest.mark.parametrize("shape", [(6, 2, 2), (12, 1, 2), (12, 3, 3)])
def test_to_nested_rejects_other_layouts(shape):
    """Data that are not 12 square faces with a power of two side must not be reordered silently."""
    data = xr.Dataset({"tas": (("face", "height", "width"), np.zeros(shape))})
    with pytest.raises(ValueError, match="Not a DLESyM HEALPix layout"):
        DlesymHealpix().to_nested(data)


def test_convert_keeps_tree_values_and_time(dlesym_data, tmp_path):
    """The files are written on the same tree, with the same values, the raw time axis and no overwriting."""
    source = tmp_path / "in" / "aimip" / "r1i1p1f1"
    source.mkdir(parents=True)
    dlesym_data.to_netcdf(source / "tas.nc", encoding={"tas": {"_FillValue": np.nan}})
    target = tmp_path / "out"
    outfile = os.path.join(target, "aimip", "r1i1p1f1", "tas.nc")

    converter = DlesymHealpix()
    assert converter.convert(tmp_path / "in", target) == [outfile]
    assert converter.convert(tmp_path / "in", target) == []
    assert converter.convert(tmp_path / "in", target, overwrite=True) == [outfile]
    assert os.listdir(os.path.dirname(outfile)) == ["tas.nc"]

    with xr.open_dataset(outfile, decode_times=False) as written:
        assert dict(written.sizes) == {"time": 3, "plev": 1, "cells": 48}
        assert written.tas.dtype == "float32"
        assert np.isnan(written.tas.encoding["_FillValue"])
        assert written.time.attrs == dlesym_data.time.attrs
        assert written.time.values.tolist() == [10.5, 11.5, 12.5]
        assert written.tas.isel(time=0, cells=slice(0, 4)).values.tolist() == NESTED_FACE
        # same values, only reordered
        assert np.sort(written.tas.values).tolist() == np.sort(dlesym_data.tas.values.reshape(3, 48)).tolist()
