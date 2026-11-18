"""Tests for the aqua-claima plugin contract v2."""

from pathlib import Path

import pytest

import aqua.claima
from aqua.claima import MIN_AQUA_CORE, get_install_dirs

pytestmark = pytest.mark.claima

CONFIG_ROOT = Path(aqua.claima.__file__).parent / "config"

EXPECTED = {"contract": 2, "config": ["analysis", "collections", "tools"], "flat": [], "templates": [], "files": ["grids"]}


@pytest.fixture
def recent_core(monkeypatch):
    """Pretend aqua-core is recent enough, independently of the installed version."""
    import aqua.core

    monkeypatch.setattr(aqua.core, "__version__", MIN_AQUA_CORE)


def test_namespace():
    """aqua.claima and aqua.core coexist in the aqua namespace."""
    import aqua.core

    assert aqua.claima.__version__
    assert aqua.core.__version__
    assert Path(aqua.claima.__file__).parent.parent.name == "aqua"


def test_contract_shape(recent_core):
    assert get_install_dirs() == EXPECTED


def test_old_core_rejected(monkeypatch):
    import aqua.core

    monkeypatch.setattr(aqua.core, "__version__", "1.2.4")
    with pytest.raises(RuntimeError, match=f"aqua-claima requires aqua-core>={MIN_AQUA_CORE}"):
        get_install_dirs()


def test_listed_dirs_exist(recent_core):
    dirs = get_install_dirs()
    for key in ("config", "flat", "templates", "files"):
        for name in dirs[key]:
            path = CONFIG_ROOT / name
            assert path.is_dir(), f"{key}: {path} missing"
            assert any(path.iterdir()), f"{key}: {path} is empty"
