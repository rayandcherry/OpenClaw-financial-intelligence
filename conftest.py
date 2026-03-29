"""Root conftest — ensure venv site-packages are on sys.path.

The venv shebang path may differ when the repo is cloned to a new location,
so we resolve the site-packages directory relative to this file and inject it
at the front of sys.path before any test imports happen.
"""
import sys
import os
from pathlib import Path

_ROOT = Path(__file__).parent
_VENV_SITE = _ROOT / "venv" / "lib"

# Walk venv/lib/ to find the first pythonX.Y/site-packages directory
for _candidate in sorted(_VENV_SITE.glob("python*/site-packages")):
    _site = str(_candidate)
    if _site not in sys.path:
        sys.path.insert(0, _site)
    break
