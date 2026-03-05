"""Single source of version truth — read from pyproject.toml at import time."""
from __future__ import annotations

try:
    # Always prefer pyproject.toml when running from source — this stays correct
    # without requiring `pip install -e .` after every version bump.
    from pathlib import Path
    import re
    _pyproject = Path(__file__).parent.parent / "pyproject.toml"
    if _pyproject.exists():
        _match = re.search(r'^version\s*=\s*"([^"]+)"', _pyproject.read_text(), re.MULTILINE)
        __version__: str = _match.group(1) if _match else "0.0.0"
    else:
        # Installed as a package without source tree — fall back to package metadata.
        from importlib.metadata import version, PackageNotFoundError
        try:
            __version__ = version("pywiki")
        except PackageNotFoundError:
            __version__ = "0.0.0"
except Exception:
    __version__ = "0.0.0"
