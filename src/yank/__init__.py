"""yank — yank the web."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("yank-tui")
except PackageNotFoundError:
    __version__ = "0.3.2"  # fallback for development / editable installs

__all__ = ["__version__"]
