"""Pytest entry configuration (path bootstrap).

`backend/` must be on sys.path so `app` is importable regardless of the
directory pytest is invoked from.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
