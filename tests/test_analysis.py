"""Dry run of `aqua analysis` on the claima analysis config, with the diagnostic tools recorded instead of run."""

import os

import pytest
from conftest import ANALYSIS_CONFIG, CONFIG_ROOT, PROJECT, diagnostics_path

from aqua.core.analysis.analysis import Analysis
from aqua.core.console.analysis import analysis_execute, analysis_parser
from aqua.core.util import dump_yaml, load_yaml

pytestmark = pytest.mark.claima


@pytest.fixture
def scripts_dir(tmp_path):
    """aqua-diagnostics install path; without aqua-diagnostics, a stand-in with empty scripts at the cli paths."""
    path = diagnostics_path()
    if path is not None:
        return path
    fake = os.path.join(tmp_path, "diagnostics")
    for script in load_yaml(ANALYSIS_CONFIG)["cli"].values():
        os.makedirs(os.path.dirname(os.path.join(fake, script)), exist_ok=True)
        open(os.path.join(fake, script), "w").close()
    return fake


@pytest.fixture
def configdir(monkeypatch, tmp_path):
    """A ~/.aqua with the claima folders linked as an editable install does, and claima as the active project."""
    configdir = os.path.join(tmp_path, ".aqua")
    for folder in ("analysis", "collections"):
        os.makedirs(os.path.join(configdir, folder))
        os.symlink(os.path.join(CONFIG_ROOT, folder), os.path.join(configdir, folder, PROJECT))
    dump_yaml(os.path.join(configdir, "config-aqua.yaml"), {"machine": "github", "project": PROJECT})
    monkeypatch.setenv("AQUA_CONFIG", configdir)
    monkeypatch.setenv("AQUA_PROJECT", PROJECT)  # exported by `aqua analysis -p` with aqua-core>=1.3.0
    return configdir


@pytest.mark.parametrize("kind", ["default", "scenario"])
def test_analysis_dry_run(monkeypatch, tmp_path, configdir, scripts_dir, kind):
    """Every tool of the analysis config gets an existing script and a rendered collection config."""
    calls = []

    def record(self, collection, tool, script_path, extra_args, logfile=None):
        config = extra_args.split("--config ")[1].split()[0]
        assert os.path.isfile(script_path), script_path
        assert load_yaml(config)["diagnostics"], config  # rendered file, removed after the tool runs
        calls.append((collection, tool))
        return 0

    monkeypatch.setattr(Analysis, "run_diagnostic_tool", record)
    monkeypatch.setattr(Analysis, "run_setup_checker", lambda self, **kwargs: 0)
    monkeypatch.setattr(Analysis, "get_aqua_paths", lambda self: ("", scripts_dir, configdir))

    config = os.path.join(configdir, "analysis", PROJECT, "config.aqua-analysis.yaml")
    args = analysis_parser().parse_args(
        ["--config", config, "-c", "ci", "-m", "IFS", "-e", "test-tco79", "-s", "teleconnections",
         "-o", str(tmp_path / "output"), "-k", kind, "--serial"]
    )  # fmt: skip
    analysis_execute(args)

    expected = {
        (collection, tool) for collection, tools in load_yaml(ANALYSIS_CONFIG)["diagnostics"].items() for tool in tools
    }
    assert set(calls) == expected
