"""Shared paths and helpers for the aqua-claima tests."""

import os
from unittest.mock import patch

import pytest

import aqua.claima

PROJECT = "claima"
CONFIG_ROOT = os.path.join(os.path.dirname(aqua.claima.__file__), "config")
ANALYSIS_CONFIG = os.path.join(CONFIG_ROOT, "analysis", "config.aqua-analysis.yaml")
EXPERIMENT_KIND_CONFIG = os.path.join(CONFIG_ROOT, "analysis", "claima-experiment-kind.yaml")
COLLECTIONS_DIR = os.path.join(CONFIG_ROOT, "collections")


def diagnostics_path():
    """Install path of aqua.diagnostics, or None if aqua-diagnostics is not installed."""
    try:
        import aqua.diagnostics
    except ImportError:
        return None
    return os.path.dirname(aqua.diagnostics.__file__)


@pytest.fixture(autouse=True)
def _restore_environ():
    """Restore the environment after each test: `aqua analysis` exports AQUA_* variables."""
    with patch.dict(os.environ):
        yield
