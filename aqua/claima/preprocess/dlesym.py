"""Rewrite DLESyM output on the standard HEALPix nested grid.

DLESyM (DLWP-HEALPix) stores its HEALPix fields by base face, with dimensions
``(face, height, width)`` and no coordinates, which AQUA cannot regrid nor average.
``data[face, height, width]`` is the pixel ``ix = nside - 1 - height``,
``iy = nside - 1 - width`` of that HEALPix base face (``hpx1d2hpx3d`` in
``data_processing/remap/healpix.py`` of the DLESyM code), so the cells only have to be
reordered: the values are not changed. The result has a single ``cells`` dimension in
nested order and can be read in AQUA with the ``hpz<zoom>-nested`` grids (``hpz6-nested``
for the AIMIP archive).

Example:
    >>> from aqua.claima.preprocess import DlesymHealpix
    >>> DlesymHealpix().convert("/archive/DLESyM", "/scratch/DLESyM-nested")

or, from the command line::

    python -m aqua.claima.preprocess.dlesym /archive/DLESyM /scratch/DLESyM-nested
"""

import argparse
import os

import numpy as np
import xarray as xr

from aqua.core.logger import log_configure, log_history

FACE_DIMS = ("face", "height", "width")
CELL_DIM = "cells"
GRID_MAPPING = "healpix"


class DlesymHealpix:
    """Reorder DLESyM fields from the (face, height, width) layout to HEALPix nested order.

    Args:
        loglevel (str, optional): Logging level. Defaults to "WARNING".
    """

    def __init__(self, loglevel="WARNING"):
        self.logger = log_configure(log_level=loglevel, log_name="DlesymHealpix")
        self.loglevel = loglevel

    @staticmethod
    def _nested_index(nside):
        """Face, height and width of each pixel of a HEALPix grid, in nested order."""
        pixel = np.arange(12 * nside**2)
        within = pixel % nside**2
        # ix and iy are the even and odd bits of the index of the pixel within its face
        ix = sum(((within >> (2 * bit)) & 1) << bit for bit in range(nside.bit_length() - 1))
        iy = sum(((within >> (2 * bit + 1)) & 1) << bit for bit in range(nside.bit_length() - 1))
        return pixel // nside**2, nside - 1 - ix, nside - 1 - iy

    def to_nested(self, data):
        """Reorder the cells of DLESyM data to HEALPix nested order.

        Args:
            data (xr.Dataset): Data with the dimensions ``face`` (12), ``height`` and ``width`` (nside).

        Returns:
            xr.Dataset: The same data along a single ``cells`` dimension in nested order,
                with a ``healpix`` grid mapping variable.

        Raises:
            ValueError: If the data are not on the DLESyM layout.
        """
        sizes = [data.sizes.get(dim) for dim in FACE_DIMS]
        nside = sizes[1]
        if sizes[0] != 12 or nside != sizes[2] or nside & (nside - 1):
            raise ValueError(f"Not a DLESyM HEALPix layout: {dict(zip(FACE_DIMS, sizes))}")

        index = {dim: xr.DataArray(idx, dims=CELL_DIM) for dim, idx in zip(FACE_DIMS, self._nested_index(nside))}
        nested = data.isel(index).drop_vars(FACE_DIMS, errors="ignore")
        for var in nested.data_vars:
            nested[var].attrs["grid_mapping"] = GRID_MAPPING
        mapping = {"grid_mapping_name": "healpix", "healpix_nside": np.int32(nside), "healpix_order": "nested"}
        nested = nested.assign({GRID_MAPPING: xr.DataArray(np.int32(0), attrs=mapping)})
        log_history(nested, f"Cells reordered from the DLESyM face layout to HEALPix nested order (nside={nside})")
        return nested

    def convert_file(self, source, target):
        """Write the netCDF file ``source`` to ``target`` in HEALPix nested order, with the time axis untouched."""
        with xr.open_dataset(source, decode_times=False, chunks={"time": 120}) as data:
            nested = self.to_nested(data)
            encoding = {
                var: {"dtype": field.dtype, "_FillValue": field.encoding.get("_FillValue"), "zlib": True, "complevel": 1}
                for var, field in data.data_vars.items()
            }
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            nested.to_netcdf(f"{target}.tmp", encoding=encoding)
        os.replace(f"{target}.tmp", target)

    def convert(self, source, target, overwrite=False):
        """Convert all the netCDF files below ``source``, keeping the same tree below ``target``.

        Args:
            source (str): Directory with the DLESyM files, searched recursively.
            target (str): Output directory.
            overwrite (bool, optional): Convert again the files found in ``target``. Defaults to False.

        Returns:
            list[str]: The files written.
        """
        written = []
        for folder, _, files in sorted(os.walk(source)):
            for name in sorted(file for file in files if file.endswith(".nc")):
                outfile = os.path.normpath(os.path.join(target, os.path.relpath(folder, source), name))
                if os.path.exists(outfile) and not overwrite:
                    self.logger.info("%s exists, skipping", outfile)
                    continue
                self.logger.info("Writing %s", outfile)
                self.convert_file(os.path.join(folder, name), outfile)
                written.append(outfile)
        return written


def main(argv=None):
    """Command line interface."""
    parser = argparse.ArgumentParser(description="Rewrite DLESyM output on the standard HEALPix nested grid")
    parser.add_argument("source", help="directory with the DLESyM netCDF files, searched recursively")
    parser.add_argument("target", help="output directory, with the same tree as the source")
    parser.add_argument("--overwrite", action="store_true", help="convert again the files already in the target")
    parser.add_argument("-l", "--loglevel", default="INFO", help="logging level")
    args = parser.parse_args(argv)
    DlesymHealpix(loglevel=args.loglevel).convert(args.source, args.target, overwrite=args.overwrite)


if __name__ == "__main__":
    main()
