from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

try:
    __version__ = version("codexdatalab")
except PackageNotFoundError:
    # Fallback for source checkouts without installed metadata.
    __version__ = "0.1.0"
