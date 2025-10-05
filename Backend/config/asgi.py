"""ASGI config for the ChatGPT clone project."""
from __future__ import annotations

import os

from django.core.asgi import get_asgi_application

from app.startup import ensure_database_schema

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_asgi_application()

ensure_database_schema()
