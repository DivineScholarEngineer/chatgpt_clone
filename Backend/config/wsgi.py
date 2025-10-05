"""WSGI config for the ChatGPT clone project."""
from __future__ import annotations

import os

from django.core.wsgi import get_wsgi_application

from app.startup import ensure_database_schema

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

ensure_database_schema()
