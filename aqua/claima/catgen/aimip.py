#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AQUA catalog generator for the AIMIP archive.

The archive stores the AI model simulations of AIMIP as one netCDF file for each
variable, in a CMIP-like tree (experiment/member/table/variable/grid/version).
The generator scans it and writes one AQUA catalog entry for each experiment, so
that every source points only to the current and readable version of each file.

Usage:
    python -m aqua.claima.catgen.aimip -c config-aimip.yaml

or, from python:
    AimipCatalogGenerator(config_path="config-aimip.yaml").generate_catalog()
"""

import argparse
import json
import os
import re
import sys

import netCDF4

from aqua.core.lock import SafeFileLock
from aqua.core.logger import log_configure
from aqua.core.util import dump_yaml, get_arg, load_yaml

CATGEN_DIR = os.path.dirname(os.path.abspath(__file__))
INTAKE_PATH = "{{AIMIP_PATH}}"
FREQUENCIES = {"Amon": "monthly", "day": "daily"}
VERTICAL_DIMS = {"plev", "model_layer"}


class AimipCatalogGenerator:
    """Class for generating the AQUA catalog entries of the AIMIP archive."""

    def __init__(self, config_path: str | None = None, loglevel: str = "INFO"):
        """
        Initialize the generator with the specified configuration.

        Args:
            config_path (str, optional): Path to the configuration YAML file. Defaults to the
                                         ``config-aimip.yaml`` shipped with aqua-claima.
            loglevel (str, optional): Logging level. Defaults to "INFO".
        """
        self.loglevel = loglevel
        self.logger = log_configure(self.loglevel, "AIMIP catalog generator")

        self.config = load_yaml(config_path or os.path.join(CATGEN_DIR, "config-aimip.yaml"))
        self.template = os.path.join(CATGEN_DIR, "aimip_entry.j2")

        required_keys = ["machine", "archive_path", "catalog_dir", "models"]
        missing = [k for k in required_keys if not self.config.get(k)]
        if not (self.config.get("repos") or {}).get("Climate-DT-catalog_path"):
            missing.append("repos.Climate-DT-catalog_path")
        if missing:
            raise ValueError(f"Missing required configuration keys: {', '.join(missing)}")

        self.archive = self.config["archive_path"]
        self.catalog_dir = os.path.join(
            self.config["repos"]["Climate-DT-catalog_path"], "catalogs", self.config["catalog_dir"]
        )
        self.inventory = None

    def scan(self):
        """
        Scan the archive: files, unreadable files and dimensions of each variable.

        Returns:
            dict: ``inv`` with the files of each "base|experiment|table|grid|variable" for each member
                  and version, ``broken`` with the unreadable files and ``hdr`` with the dimensions
                  of each "base|table|grid|variable".
        """
        inv, hdr, broken = {}, {}, []
        for base in sorted({model["base"] for model in self.config["models"].values()}):
            self.logger.info("Scanning %s", os.path.join(self.archive, base))
            for dirpath, _, filenames in sorted(os.walk(os.path.join(self.archive, base))):
                files = sorted(f for f in filenames if f.endswith(".nc"))
                parts = os.path.relpath(dirpath, os.path.join(self.archive, base)).split(os.sep)
                version = parts.pop() if parts[-1].startswith("v20") else "-"
                if not files:
                    continue
                if len(parts) != 5:
                    self.logger.warning("Skipping %s: not in the expected folder structure", dirpath)
                    continue
                exp, member, table, var, grid = parts
                inv.setdefault("|".join([base, exp, table, grid, var]), {}).setdefault(member, {})[version] = files
                for filename in files:
                    path = os.path.join(dirpath, filename)
                    try:
                        with netCDF4.Dataset(path) as data:
                            hdr.setdefault("|".join([base, table, grid, var]), {"dims": list(data[var].dimensions)})
                    except OSError:
                        self.logger.warning("Unreadable file %s", path)
                        broken.append(os.path.relpath(path, self.archive))
        return {"inv": inv, "hdr": hdr, "broken": sorted(broken)}

    def get_inventory(self):
        """
        Get the inventory of the archive, from the ``inventory`` file of the configuration if it
        exists, otherwise scanning the archive (and saving the result to that file, if defined).

        Returns:
            dict: The inventory, as returned by scan().
        """
        cache = self.config.get("inventory")
        if cache and os.path.exists(cache):
            self.logger.info("Reading the inventory from %s", cache)
            with open(cache, encoding="utf-8") as stream:
                return json.load(stream)
        inventory = self.scan()
        if cache:
            with open(cache, "w", encoding="utf-8") as stream:
                json.dump(inventory, stream)
            self.logger.info("Inventory saved to %s", cache)
        return inventory

    @staticmethod
    def get_period(filename):
        """Get the (start, end) dates of a file from its name, padded to YYYYMMDD."""
        start, end = re.search(r"_(\d+)-(\d+)\.nc$", filename).groups()
        return start.ljust(8, "0"), end.ljust(8, "9")

    def select_files(self, versions, broken):
        """
        Split the files of one variable and member into current and discarded ones.
        Unreadable files are discarded. Then the newest version wins: a file of an older
        version is kept only if it does not overlap in time with any file of a newer version.

        Args:
            versions (dict): Files for each version folder.
            broken (set): Unreadable (version, file) pairs.

        Returns:
            tuple: Sets of current and of discarded (version, file) pairs.
        """
        current, discarded = set(), set(broken)
        for version in sorted(versions, reverse=True):
            for filename in versions[version]:
                if (version, filename) in broken:
                    continue
                start, end = self.get_period(filename)
                newer = [self.get_period(f) for v, f in current if v != version]
                if any(start <= e and end >= s for s, e in newer):
                    discarded.add((version, filename))
                else:
                    current.add((version, filename))
        return current, discarded

    def get_urlpath(self, key):
        """
        Get the glob patterns matching the current files of one variable, for any member.
        One pattern for each version folder is enough when all its files are current. When some
        members have discarded files there, the pattern is split by time period and those
        members are excluded through their realization index.

        Args:
            key (str): The "base|experiment|table|grid|variable" inventory key.

        Returns:
            list: The glob patterns, with the member as intake ``realization`` parameter.
        """
        base, exp, table, grid, var = key.split("|")
        folder = f"{INTAKE_PATH}/{base}/{exp}/{{{{realization}}}}/{table}/{var}/{grid}"
        selection = {}
        for member, versions in self.inventory["inv"][key].items():
            relative = f"{base}/{exp}/{member}/{table}/{var}/{grid}/"
            broken = {tuple(b[len(relative) :].split("/")) for b in self.inventory["broken"] if b.startswith(relative)}
            selection[member] = self.select_files(versions, broken)

        urlpath = []
        for version in sorted({v for current, _ in selection.values() for v, _ in current}):
            prefix = f"{folder}/{version}/" if version != "-" else f"{folder}/"
            periods = {}  # time period of the filename: members for which that file is discarded
            for member, (current, discarded) in selection.items():
                for is_discarded, pairs in ((False, current), (True, discarded)):
                    for _, filename in (p for p in pairs if p[0] == version and f"_{grid}_" in p[1]):
                        periods.setdefault(filename.rsplit("_", 1)[1], set()).update([member] if is_discarded else [])
            if not any(periods.values()):
                urlpath.append(f"{prefix}{var}_*_{grid}_*.nc")
                continue
            for period, excluded in sorted(periods.items()):
                if not excluded:
                    urlpath.append(f"{prefix}{var}_*_{grid}_{period}")
                    continue
                indices = [re.fullmatch(r"r(\d)i1p1f1", member) for member in sorted(excluded)]
                if not all(indices):
                    raise ValueError(f"Cannot exclude members {sorted(excluded)} of {key} with a glob pattern")
                urlpath.append(f"{prefix}{var}_*_r[!{''.join(i.group(1) for i in indices)}]i1p1f1_{grid}_{period}")
        return urlpath

    def get_sources(self, model, folder):
        """
        Generate the catalog sources of one experiment of a model.

        Args:
            model (str): The AQUA model name, as in the configuration.
            folder (str): The experiment folder in the archive.

        Returns:
            tuple: The rendered sources and the sorted list of the members.
        """
        config = self.config["models"][model]
        base = config["base"]
        groups = {}  # (table, grid label, 2d/3d): variables
        for key in self.inventory["inv"]:
            kbase, kexp, table, grid, var = key.split("|")
            if (kbase, kexp) == (base, folder):
                dims = self.inventory["hdr"]["|".join([base, table, grid, var])]["dims"]
                groups.setdefault((table, grid, "atm3d" if VERTICAL_DIMS & set(dims) else "atm2d"), []).append(var)

        sources, all_members = {}, set()
        for (table, grid, kind), variables in sorted(groups.items()):
            frequency = FREQUENCIES[table]
            keys = ["|".join([base, folder, table, grid, var]) for var in sorted(variables)]
            members = sorted({member for key in keys for member in self.inventory["inv"][key]})
            all_members.update(members)
            # the regridded (gr) data are the default source when both grid labels are available
            native = grid == "gn" and (table, "gr", kind) in groups
            content = {
                "source": f"{frequency}-{kind}" + ("-native" if native else ""),
                "description": f"{frequency} {kind[3:].upper()} data on the {grid} grid ({', '.join(sorted(variables))})",
                "grid": config["grid"],
                "urlpath": [pattern for key in keys for pattern in self.get_urlpath(key)],
                "time_chunk": self.config.get("time_chunks", {}).get(frequency, 1),
                "drop_variables": config.get("drop_variables"),
                "members": members,
            }
            self.logger.info("Source: %s %s %s", model, folder, content["source"])
            sources.update(load_yaml(self.template, definitions=content, catgen=True))
        return sources, sorted(all_members)

    def create_catalog_entry(self, model, model_description, exp, sources, description):
        """
        Create the catalog entry file of an experiment and update the main YAML files.

        Args:
            model (str): The AQUA model name.
            model_description (str): The description of the model.
            exp (str): The AQUA experiment name.
            sources (dict): The sources of the experiment.
            description (str): The description of the experiment.
        """
        output_dir = os.path.join(self.catalog_dir, "catalog", model)
        dump_yaml(os.path.join(output_dir, f"{exp}.yaml"), {"sources": sources})
        self.logger.info("File %s.yaml has been created in %s", exp, output_dir)

        # Update main.yaml
        main_yaml_path = os.path.join(output_dir, "main.yaml")
        with SafeFileLock(main_yaml_path + ".lock", loglevel=self.loglevel):
            main_yaml = load_yaml(main_yaml_path) if os.path.exists(main_yaml_path) else {"sources": {}}
            main_yaml["sources"][exp] = {
                "description": description,
                "driver": "yaml_file_cat",
                "args": {"path": f"{{{{CATALOG_DIR}}}}/{exp}.yaml"},
            }
            dump_yaml(main_yaml_path, main_yaml)

        # Update catalog.yaml, creating it if this is a new catalog
        catalog_yaml_path = os.path.join(self.catalog_dir, "catalog.yaml")
        with SafeFileLock(catalog_yaml_path + ".lock", loglevel=self.loglevel):
            if os.path.exists(catalog_yaml_path):
                catalog_yaml = load_yaml(catalog_yaml_path, jinja=False)
            else:
                parameter = {
                    "type": "str",
                    "description": "the path to the AIMIP archive on the local machine",
                    "default": self.archive,
                }
                catalog_yaml = {"metadata": {"parameters": {"AIMIP_PATH": parameter}}, "sources": {}}
            catalog_yaml["sources"][model] = {
                "description": model_description,
                "driver": "yaml_file_cat",
                "args": {"path": f"{{{{CATALOG_DIR}}}}/catalog/{model}/main.yaml"},
            }
            dump_yaml(catalog_yaml_path, catalog_yaml)

    def generate_catalog(self):
        """
        Generate the entire catalog: one entry for each experiment of each model, then the
        reference datasets described in the configuration.
        """
        self.inventory = self.get_inventory()
        names = self.config.get("experiments", {})

        for model, config in self.config["models"].items():
            folders = sorted({key.split("|")[1] for key in self.inventory["inv"] if key.split("|")[0] == config["base"]})
            if not folders:
                self.logger.error("No data found for %s, no entry generated!", model)
            for folder in folders:
                exp = names.get(f"{model}/{folder}", names.get(folder, folder))
                sources, members = self.get_sources(model, folder)
                description = self.config.get("descriptions", {}).get(exp, exp)
                description += f", {len(members)} member{'s' if len(members) > 1 else ''}"
                self.create_catalog_entry(model, config["description"], exp, sources, description)

        for model, config in self.config.get("references", {}).items():
            for exp, experiment in config["experiments"].items():
                sources = {}
                for source, content in experiment["sources"].items():
                    content = {"source": source, "grid": "lon-lat", **content}
                    content["urlpath"] = [f"{INTAKE_PATH}/{path}" for path in content["urlpath"]]
                    sources.update(load_yaml(self.template, definitions=content, catgen=True))
                self.create_catalog_entry(model, config["description"], exp, sources, experiment["description"])


def aimip_parser(parser=None):
    """Create the argument parser for the AIMIP catalog generator"""
    if parser is None:
        parser = argparse.ArgumentParser(description="AQUA catalog generator for the AIMIP archive")

    parser.add_argument("-c", "--config", type=str, help="yaml configuration file")
    parser.add_argument("-l", "--loglevel", type=str, help="loglevel", default="INFO")

    return parser


def aimip_execute(args):
    """Useful wrapper for the AIMIP catalog generator class"""

    config_file = get_arg(args, "config", None)
    loglevel = get_arg(args, "loglevel", "INFO")

    generator = AimipCatalogGenerator(config_path=config_file, loglevel=loglevel)
    generator.generate_catalog()


if __name__ == "__main__":
    args = aimip_parser().parse_args(sys.argv[1:])
    aimip_execute(args)
