"""Functions shared by the catalog generators of the CLAIMA project."""

import os

from aqua.core.lock import SafeFileLock
from aqua.core.util import dump_yaml, load_yaml


def write_catalog_entry(catalog_dir, model, model_description, exp, sources, description, parameters, loglevel="INFO"):
    """
    Write the catalog entry file of an experiment and update the main YAML files of the catalog.

    Args:
        catalog_dir (str): The folder of the catalog.
        model (str): The AQUA model name.
        model_description (str): The description of the model.
        exp (str): The AQUA experiment name.
        sources (dict): The sources of the experiment.
        description (str): The description of the experiment.
        parameters (dict): The intake parameters of the catalog, used only if the catalog is created.
        loglevel (str, optional): Logging level. Defaults to "INFO".
    """
    output_dir = os.path.join(catalog_dir, "catalog", model)
    dump_yaml(os.path.join(output_dir, f"{exp}.yaml"), {"sources": sources})

    # Update main.yaml
    main_yaml_path = os.path.join(output_dir, "main.yaml")
    with SafeFileLock(main_yaml_path + ".lock", loglevel=loglevel):
        main_yaml = load_yaml(main_yaml_path) if os.path.exists(main_yaml_path) else {"sources": {}}
        main_yaml["sources"][exp] = {
            "description": description,
            "driver": "yaml_file_cat",
            "args": {"path": f"{{{{CATALOG_DIR}}}}/{exp}.yaml"},
        }
        dump_yaml(main_yaml_path, main_yaml)

    # Update catalog.yaml, creating it if this is a new catalog
    catalog_yaml_path = os.path.join(catalog_dir, "catalog.yaml")
    with SafeFileLock(catalog_yaml_path + ".lock", loglevel=loglevel):
        if os.path.exists(catalog_yaml_path):
            catalog_yaml = load_yaml(catalog_yaml_path, jinja=False)
        else:
            catalog_yaml = {"metadata": {"parameters": parameters}, "sources": {}}
        catalog_yaml["sources"][model] = {
            "description": model_description,
            "driver": "yaml_file_cat",
            "args": {"path": f"{{{{CATALOG_DIR}}}}/catalog/{model}/main.yaml"},
        }
        dump_yaml(catalog_yaml_path, catalog_yaml)
