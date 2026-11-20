"""AQUA-claima: CLAIMA project configuration shipped as an aqua-core plugin."""

from packaging.version import Version

from .version import __version__

# Minimum aqua-core version implementing the plugin contract v2.
# TODO: raise to 1.3.0 before releasing aqua-claima 0.1.0
MIN_AQUA_CORE = "1.2.4"

PLUGIN_CONTRACT = 2
CONFIG_DIRECTORIES = ["analysis", "collections", "tools"]
FILE_DIRECTORIES = ["grids", "catgen"]

__all__ = ["__version__", "MIN_AQUA_CORE", "get_install_dirs"]


def get_install_dirs():
    """Return the directories aqua-core installs from this plugin (contract v2).

    Paths are relative to ``aqua/claima/config``. ``config`` dirs are copied into
    ``~/.aqua/<dir>/claima``; the files inside each ``files`` dir are copied one by
    one into the flat ``~/.aqua/<dir>``.

    Raises:
        RuntimeError: if the installed aqua-core is older than ``MIN_AQUA_CORE``.
    """
    from aqua.core import __version__ as core_version

    if Version(core_version) < Version(MIN_AQUA_CORE):
        raise RuntimeError(f"aqua-claima requires aqua-core>={MIN_AQUA_CORE}, please update aqua-core")

    return {
        "contract": PLUGIN_CONTRACT,
        "config": list(CONFIG_DIRECTORIES),
        "flat": [],
        "templates": [],
        "files": list(FILE_DIRECTORIES),
    }
