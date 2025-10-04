#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import subprocess
import sys
from pathlib import Path


def _install_requirements() -> bool:
    """Install backend requirements if the requirements file is present."""

    requirements_path = Path(__file__).resolve().parent / "requirements.txt"
    if not requirements_path.exists():
        return False

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
        )
    except subprocess.CalledProcessError as error:  # pragma: no cover - setup helper
        raise ImportError(
            "Django is not installed and the automatic installation of requirements failed."
        ) from error

    return True


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError:
        if not _install_requirements():
            raise ImportError(
                "Couldn't import Django and no requirements.txt was found to install it from."
            )

        try:
            from django.core.management import execute_from_command_line
        except ImportError as exc:  # pragma: no cover - should now be installed
            raise ImportError(
                "Couldn't import Django even after installing Backend/requirements.txt."
            ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
