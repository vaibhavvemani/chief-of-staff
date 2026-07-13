"""HTTP adapter for the local Course Builder prototype.

The package depends on the existing domain modules; domain code does not depend
on FastAPI or on this package.
"""

__all__ = ["create_app"]


def create_app(*args, **kwargs):
    """Import the FastAPI application factory lazily.

    Keeping this import lazy lets repository/projector tooling work in a minimal
    deterministic environment before the optional web dependencies are installed.
    """
    from api.main import create_app as factory

    return factory(*args, **kwargs)
