"""Contract tests keeping the analysis config, the collections and the experiment kinds consistent."""

import glob
import os

import pytest
from conftest import ANALYSIS_CONFIG, COLLECTIONS_DIR, CONFIG_ROOT, EXPERIMENT_KIND_CONFIG, diagnostics_path

from aqua.core.analysis.analysis import resolve_experiment_kind
from aqua.core.util import load_yaml

pytestmark = pytest.mark.claima

# Keep additions and removals of diagnostic keys explicit and reviewed.
KNOWN_DIAGNOSTIC_KEYS = {"biases", "gregory", "seasonalcycles", "timeseries"}

YAML_FILES = sorted(glob.glob(os.path.join(CONFIG_ROOT, "**", "*.yaml"), recursive=True))
JINJA_FILES = sorted(glob.glob(os.path.join(COLLECTIONS_DIR, "jinja", "**", "*.j2"), recursive=True))
LEGACY_FILES = sorted(glob.glob(os.path.join(COLLECTIONS_DIR, "legacy", "**", "*.yaml"), recursive=True))
KINDS = sorted(load_yaml(EXPERIMENT_KIND_CONFIG))


def _relative(path):
    return os.path.relpath(path, CONFIG_ROOT)


def _strings(node):
    """All string values of a nested config."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)
    elif isinstance(node, str):
        yield node


def _render(template, kind):
    """Render a jinja collection as `aqua analysis` does (strict jinja, kind deep-merged on default)."""
    return load_yaml(template, definitions=resolve_experiment_kind(load_yaml(EXPERIMENT_KIND_CONFIG), kind), strict=True)


@pytest.mark.parametrize("path", YAML_FILES, ids=_relative)
def test_yaml_loads(path):
    assert isinstance(load_yaml(path), dict)


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("template", JINJA_FILES, ids=_relative)
def test_jinja_collection_renders(template, kind):
    """A variable missing from a kind is only logged at runtime and silently skips the collection."""
    rendered = _render(template, kind)
    assert isinstance(rendered, dict) and rendered.get("diagnostics")


def test_jinja_and_legacy_collections_match():
    """Every collection exists in jinja and legacy form, with the same diagnostic keys."""
    jinja = {os.path.splitext(os.path.relpath(p, os.path.join(COLLECTIONS_DIR, "jinja")))[0]: p for p in JINJA_FILES}
    legacy = {os.path.splitext(os.path.relpath(p, os.path.join(COLLECTIONS_DIR, "legacy")))[0]: p for p in LEGACY_FILES}
    assert jinja and set(jinja) == set(legacy)
    for name, template in jinja.items():
        assert set(_render(template, "default")["diagnostics"]) == set(load_yaml(legacy[name])["diagnostics"]), name


def test_analysis_paths_exist():
    """Every ${AQUA_CONFIG} path of the analysis config points to a file of this repository once the project is set."""
    prefix = "${AQUA_CONFIG}/"
    paths = [value for value in _strings(load_yaml(ANALYSIS_CONFIG)) if value.startswith(prefix)]
    assert paths
    for value in paths:
        folder, project, *rest = value[len(prefix) :].split("/")
        assert project == "${AQUA_PROJECT}", f"{value}: use ${{AQUA_PROJECT}}, not a hard-coded project"
        assert os.path.isfile(os.path.join(CONFIG_ROOT, folder, *rest)), f"{value} not found in {CONFIG_ROOT}"


def test_analysis_run_groups_and_cli_aliases():
    cfg = load_yaml(ANALYSIS_CONFIG)
    groups = {group for run_group in cfg["run"] for group in run_group}
    assert groups == set(cfg["diagnostics"])
    for collection, tools in cfg["diagnostics"].items():
        assert set(tools) <= set(cfg["cli"]), f"{collection}: unknown cli aliases {set(tools) - set(cfg['cli'])}"


def test_cli_scripts_exist():
    path = diagnostics_path()
    if path is None:
        pytest.skip("aqua-diagnostics is not installed")
    cli = load_yaml(ANALYSIS_CONFIG)["cli"]
    missing = {alias: script for alias, script in cli.items() if not os.path.isfile(os.path.join(path, script))}
    assert not missing, f"cli aliases point to missing aqua-diagnostics scripts: {missing}"


@pytest.mark.parametrize("path", LEGACY_FILES, ids=_relative)
def test_collection_diagnostic_keys(path):
    diagnostics = load_yaml(path)["diagnostics"]
    assert set(diagnostics) <= KNOWN_DIAGNOSTIC_KEYS, (
        f"update KNOWN_DIAGNOSTIC_KEYS: {set(diagnostics) - KNOWN_DIAGNOSTIC_KEYS}"
    )
    for key, block in diagnostics.items():
        assert isinstance(block, dict) and "run" in block, f"{key}: missing 'run' switch"
