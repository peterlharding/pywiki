"""Single source of version truth — read from pyproject.toml at import time."""
from __future__ import annotations

try:
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__: str = version("pywiki")
    except PackageNotFoundError:
        # Package not installed (e.g. running from source without pip install -e .)
        # Fall back to parsing pyproject.toml directly.
        from pathlib import Path
        import re
        _here = Path(__file__).parent.parent  # project root
        _pyproject = _here / "pyproject.toml"
        _match = re.search(r'^version\s*=\s*"([^"]+)"', _pyproject.read_text(), re.MULTILINE)
        __version__ = _match.group(1) if _match else "0.0.0"
except Exception:
    __version__ = "0.0.0"
