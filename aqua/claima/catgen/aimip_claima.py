#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AQUA catalog generator for the output of aimip-claima.

aimip-claima (https://github.com/CliDyn/aimip-claima) runs AI climate emulators and writes,
after the conversion to the CF conventions, a few netCDF files for each model:
<experiment>/<model>/[<realm>/]<file>.nc. The generator scans the experiment folders and
writes one AQUA catalog entry for each model and experiment, with one source for each
file listed in the definitions which is found and can be read by AQUA.

The entry template and the definitions of the sources are read from the catgen folder of the
AQUA installation, where `aqua project install claima` puts them
(claima-aimip-claima-entry.j2, claima-aimip-claima.yaml).

Usage:
    python -m aqua.claima.catgen.aimip_claima -c claima-aimip-claima-config.yaml

or, from python:
    AimipClaimaCatalogGenerator(config_path="claima-aimip-claima-config.yaml").generate_catalog()
"""

import argparse
import os
import sys

import netCDF4

from aqua.core.configurer import ConfigContext
from aqua.core.logger import log_configure
from aqua.core.util import get_arg, load_yaml

from .util import write_catalog_entry

INTAKE_PATH = "{{CLAIMA_PATH}}"
HORIZONTAL_DIMS = {"time", "lat", "lon"}


class AimipClaimaCatalogGenerator:
    """Class for generating the AQUA catalog entries of the aimip-claima output."""

    def __init__(self, config_path: str, configcontext: ConfigContext | None = None, loglevel: str = "INFO"):
        """
        Initialize the generator with the specified configuration.

        Args:
            config_path (str): Path to the configuration YAML file.
            configcontext (ConfigContext, optional): An instance of ConfigContext for configuration management.
                                                     Defaults to None.
            loglevel (str, optional): Logging level. Defaults to "INFO".
        """
        self.loglevel = loglevel
        self.logger = log_configure(self.loglevel, "aimip-claima catalog generator")

        # get the template and the definitions from the AQUA installation
        configcontext = configcontext or ConfigContext()
        self.catgendir = configcontext.get_folder("catgen")
        self.logger.debug("Reading configuration files from %s", self.catgendir)
        self.template = os.path.join(self.catgendir, "claima-aimip-claima-entry.j2")

        # the configuration file can override the definitions
        self.config = {**load_yaml(os.path.join(self.catgendir, "claima-aimip-claima.yaml")), **load_yaml(config_path)}

        required_keys = ["machine", "archive_path", "catalog_dir", "sources"]
        missing = [k for k in required_keys if not self.config.get(k)]
        if not (self.config.get("repos") or {}).get("Climate-DT-catalog_path"):
            missing.append("repos.Climate-DT-catalog_path")
        if missing:
            raise ValueError(f"Missing required configuration keys: {', '.join(missing)}")

        self.archive = self.config["archive_path"]
        self.catalog_dir = os.path.join(
            self.config["repos"]["Climate-DT-catalog_path"], "catalogs", self.config["catalog_dir"]
        )

    def read_header(self, path):
        """
        Read from a file what is needed to describe it in the catalog.

        Args:
            path (str): The path of the netCDF file.

        Returns:
            dict: ``variables`` with the names of the data variables, ``levels`` with the number of
                  vertical levels (None for 2D data), ``period`` with the first and last month and
                  ``model`` with the description of the model (None if the file does not have it).

        Raises:
            OSError: If the file cannot be opened.
            ValueError: If the file has no time axis, or a variable which AQUA cannot read.
        """
        with netCDF4.Dataset(path) as data:
            if "time" not in data.variables:
                raise ValueError("no time coordinate")
            bounds = {getattr(variable, "bounds", None) for variable in data.variables.values()}
            variables = sorted(
                name
                for name, variable in data.variables.items()
                if "time" in variable.dimensions and name not in data.dimensions and name not in bounds
            )
            if not variables:
                raise ValueError("no variables depending on time")
            # this is also what cdo requires: other leading dimensions (e.g. member) are not supported
            unordered = [name for name in variables if data[name].dimensions[0] != "time"]
            if unordered:
                raise ValueError(f"time is not the first dimension of {', '.join(unordered)}")
            vertical = {dim for name in variables for dim in data[name].dimensions} - HORIZONTAL_DIMS
            if len(vertical) > 1:
                raise ValueError(f"more than one vertical dimension ({', '.join(sorted(vertical))})")
            time = data["time"]
            first, last = netCDF4.num2date(time[[0, -1]], time.units, getattr(time, "calendar", "standard"))
            return {
                "variables": variables,
                "levels": len(data.dimensions[vertical.pop()]) if vertical else None,
                "period": [f"{first.year:04d}-{first.month:02d}", f"{last.year:04d}-{last.month:02d}"],
                "model": getattr(data, "source", None),
            }

    def scan(self):
        """
        Scan the archive, looking in each model folder for the files of the source definitions.
        Files which are missing are ignored; files which cannot be read are skipped with a warning.

        Returns:
            dict: For each experiment folder and model folder, the header of the file of each source.
        """
        folders = self.config.get("experiments") or sorted(
            f for f in os.listdir(self.archive) if os.path.isdir(os.path.join(self.archive, f))
        )
        inventory = {}
        for folder in folders:
            self.logger.info("Scanning %s", os.path.join(self.archive, folder))
            if not os.path.isdir(os.path.join(self.archive, folder)):
                raise FileNotFoundError(f"Experiment folder {os.path.join(self.archive, folder)} not found")
            for model in sorted(os.listdir(os.path.join(self.archive, folder))):
                for source, definition in self.config["sources"].items():
                    path = os.path.join(self.archive, folder, model, definition["file"])
                    if not os.path.isfile(path):
                        continue
                    try:
                        header = self.read_header(path)
                    except (OSError, ValueError) as error:
                        self.logger.warning("Skipping %s: %s", path, error)
                        continue
                    inventory.setdefault(folder, {}).setdefault(model, {})[source] = header
        return inventory

    def get_sources(self, folder, model, headers):
        """
        Generate the catalog sources of one experiment of a model.

        Args:
            folder (str): The experiment folder in the archive.
            model (str): The model folder in the archive.
            headers (dict): The header of the file of each source, as returned by read_header().

        Returns:
            dict: The rendered sources.
        """
        sources = {}
        for source, header in headers.items():
            definition = self.config["sources"][source]
            levels = f"{header['levels']} levels: " if header["levels"] else ""
            content = {
                "source": source,
                "description": f"{definition.get('description', source)} ({levels}{', '.join(header['variables'])}), "
                f"{header['period'][0]} to {header['period'][1]}",
                "grid": definition.get("grid", "lon-lat"),
                "urlpath": f"{INTAKE_PATH}/{folder}/{model}/{definition['file']}",
                "time_chunk": definition.get("time_chunk", 1),
                "drop_variables": definition.get("drop_variables"),
            }
            self.logger.info("Source: %s %s %s", model, folder, source)
            sources.update(load_yaml(self.template, definitions=content, catgen=True))
        return sources

    def generate_catalog(self):
        """
        Generate the entire catalog: one entry for each model of each experiment folder.
        Model and experiment are named after their folders in the archive.
        """
        inventory = self.scan()
        if not inventory:
            self.logger.error("No data found in %s, no entry generated!", self.archive)
        parameter = {
            "type": "str",
            "description": "the path to the aimip-claima output on the local machine",
            "default": self.archive,
        }
        for folder, models in inventory.items():
            description = self.config.get("descriptions", {}).get(folder, folder)
            for model, headers in models.items():
                sources = self.get_sources(folder, model, headers)
                model_description = self.config.get("models", {}).get(model)
                model_description = model_description or next(iter(headers.values()))["model"] or model
                write_catalog_entry(
                    self.catalog_dir,
                    model,
                    model_description,
                    folder,
                    sources,
                    description,
                    {"CLAIMA_PATH": parameter},
                    self.loglevel,
                )
                self.logger.info("File %s.yaml has been created in %s/catalog/%s", folder, self.catalog_dir, model)


def aimip_claima_parser(parser=None):
    """Create the argument parser for the aimip-claima catalog generator"""
    if parser is None:
        parser = argparse.ArgumentParser(description="AQUA catalog generator for the aimip-claima output")

    parser.add_argument("-c", "--config", type=str, help="yaml configuration file", required=True)
    parser.add_argument("-l", "--loglevel", type=str, help="loglevel", default="INFO")

    return parser


def aimip_claima_execute(args, configcontext=None):
    """Useful wrapper for the aimip-claima catalog generator class"""

    config_file = get_arg(args, "config", "config.yaml")
    loglevel = get_arg(args, "loglevel", "INFO")

    generator = AimipClaimaCatalogGenerator(config_path=config_file, loglevel=loglevel, configcontext=configcontext)
    generator.generate_catalog()


if __name__ == "__main__":
    args = aimip_claima_parser().parse_args(sys.argv[1:])
    aimip_claima_execute(args)
