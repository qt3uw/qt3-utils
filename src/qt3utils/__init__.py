from importlib.metadata import PackageNotFoundError, version

try:
    # Use the installed distribution version when available
    __version__ = version("qt3utils")
except PackageNotFoundError:
    # Fallback for running directly from source without an installed package
    __version__ = "0.0.0"
