"""Startup utilities for the application."""
from __future__ import annotations

import logging

from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import OperationalError, ProgrammingError
from django.core.management import call_command

logger = logging.getLogger(__name__)


def ensure_database_schema(database: str = DEFAULT_DB_ALIAS) -> None:
    """Ensure required Django migrations have been applied.

    The development server is frequently started against a fresh SQLite
    database where the built-in auth tables have not yet been created. When
    that happens every authentication view crashes with ``OperationalError``.
    Running ``migrate`` once during startup makes the environment usable
    immediately without requiring manual intervention.
    """

    connection = connections[database]

    try:
        existing_tables = set(connection.introspection.table_names())
    except (OperationalError, ProgrammingError):
        existing_tables = set()

    # ``auth_user`` is present once the core Django migrations have been run.
    if "auth_user" in existing_tables:
        return

    logger.info("Database tables missing; applying migrations for %s", database)
    call_command("migrate", database=database, interactive=False, run_syncdb=True)
