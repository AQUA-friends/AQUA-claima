"""Install aqua-claima with the aqua console in a temporary HOME (plugin contract v2, project-scoped folders)."""

import io
import os
import sys

import pytest
from conftest import CONFIG_ROOT, PROJECT

from aqua.core.util import dump_yaml, load_yaml

try:
    from aqua.core.configurer.context import PROJECT_FOLDERS, PROJECT_KEY
except ImportError:
    pytest.skip("aqua-core without project support (needs aqua-core>=1.3.0)", allow_module_level=True)

from aqua.core.console.main import AquaConsole

pytestmark = pytest.mark.claima

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CONFIG_ROOT)))


@pytest.fixture
def aqua(monkeypatch, tmp_path):
    """Run the aqua console in-process with HOME in a temporary folder; return the ~/.aqua path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("AQUA_CONFIG", raising=False)
    monkeypatch.delenv("AQUA_PROJECT", raising=False)

    def run(*args, answer="yes"):
        monkeypatch.setattr(sys, "argv", ["aqua", *args])
        monkeypatch.setattr(sys, "stdin", io.StringIO(answer + "\n"))
        AquaConsole().execute()

    run.configdir = os.path.join(tmp_path, ".aqua")
    return run


def _install(aqua):
    """aqua-core configuration only, then claima as a project."""
    aqua("install", "github", "--core")
    aqua("project", "install", PROJECT)


def _active_project(configdir):
    return load_yaml(os.path.join(configdir, "config-aqua.yaml")).get(PROJECT_KEY)


@pytest.mark.parametrize("editable", [False, True], ids=["standard", "editable"])
def test_install_layout(aqua, editable):
    """`aqua project install claima [-e path]` creates the nested project folders and selects claima."""
    aqua("install", "github", "--core")
    aqua("project", "install", PROJECT, *(["-e", REPO_ROOT] if editable else []))

    for folder in PROJECT_FOLDERS:
        target = os.path.join(aqua.configdir, folder, PROJECT)
        assert os.path.isdir(target), f"{target} missing"
        assert os.path.islink(target) == editable
    assert os.path.isfile(
        os.path.join(aqua.configdir, "collections", PROJECT, "jinja", "atmosphere2d", "config-atmosphere2d-era5.j2")
    )
    assert not os.path.exists(os.path.join(aqua.configdir, "catgen", PROJECT)), "catgen is not project-scoped"
    for name in ("claima-aimip-entry.j2", "claima-aimip-claima-entry.j2"):
        entry = os.path.join(aqua.configdir, "catgen", name)
        assert os.path.isfile(entry), "catgen files are merged into the flat aqua-core folder"
        assert os.path.islink(entry) == editable
    assert _active_project(aqua.configdir) == PROJECT

    grid = os.path.join(aqua.configdir, "grids", "claima-example.yaml")
    assert os.path.isfile(grid)
    assert os.path.islink(grid) == editable


def test_project_set_list_uninstall(aqua, capsys):
    _install(aqua)
    configfile = os.path.join(aqua.configdir, "config-aqua.yaml")
    dump_yaml(configfile, {**load_yaml(configfile), PROJECT_KEY: "diagnostics"})  # pretend another project is active
    assert _active_project(aqua.configdir) != PROJECT

    aqua("project", "set", PROJECT)
    assert _active_project(aqua.configdir) == PROJECT

    capsys.readouterr()
    aqua("list")
    assert f"* {PROJECT} (standard" in capsys.readouterr().out

    aqua("uninstall")
    assert not os.path.exists(aqua.configdir)


def test_project_update_remove(aqua):
    _install(aqua)
    shipped = os.path.join(aqua.configdir, "analysis", PROJECT, "config.aqua-analysis.yaml")
    user_file = os.path.join(aqua.configdir, "analysis", PROJECT, "my-config.yaml")
    with open(shipped, "w") as f:
        f.write("modified: true\n")
    with open(user_file, "w") as f:
        f.write("mine: true\n")

    aqua("project", "update", PROJECT)
    assert "modified" not in load_yaml(shipped)
    assert os.path.isfile(user_file)

    aqua("project", "remove", PROJECT)
    for folder in PROJECT_FOLDERS:
        assert not os.path.exists(os.path.join(aqua.configdir, folder, PROJECT))
    assert not os.path.exists(os.path.join(aqua.configdir, "grids", "claima-example.yaml"))
    assert _active_project(aqua.configdir) != PROJECT
