"""Global test configuration and fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src is on Python path
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))
