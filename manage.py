#!/usr/bin/env python
"""Convenience wrapper to invoke the backend Django manage.py."""
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    """Execute the backend manage.py entry point."""
    backend_manage = Path(__file__).resolve().parent / "Backend" / "manage.py"
    if not backend_manage.exists():
        raise FileNotFoundError("Backend/manage.py could not be found.")

    runpy.run_path(str(backend_manage), run_name="__main__")


if __name__ == "__main__":
    main()
