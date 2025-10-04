from __future__ import annotations

import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "Frontend"

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "insecure-secret-key")
DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS: list[str] = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "app",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [FRONTEND_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/uploads/"
MEDIA_ROOT = BASE_DIR / "uploads"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

APPEND_SLASH = False

DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@example.com")
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

ADMIN_APPROVAL_BASE_URL = os.getenv(
    "ADMIN_APPROVAL_BASE_URL", "http://localhost:8000/admin/requests/approve"
)
ADMIN_EMAIL_CONFIG_PATH = Path(
    os.getenv("ADMIN_EMAIL_CONFIG_PATH", PROJECT_ROOT / "Backend" / "config" / "admin_email.json")
)
ADMIN_APPROVER_EMAIL = os.getenv("ADMIN_APPROVER_EMAIL")

if ADMIN_EMAIL_CONFIG_PATH.exists():
    try:
        with ADMIN_EMAIL_CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config_data = json.load(handle)
    except json.JSONDecodeError:
        config_data = {}

    EMAIL_HOST = config_data.get("host", EMAIL_HOST)
    EMAIL_PORT = int(config_data.get("port", EMAIL_PORT))
    use_tls_value = config_data.get("use_tls", EMAIL_USE_TLS)
    if isinstance(use_tls_value, str):
        EMAIL_USE_TLS = use_tls_value.lower() == "true"
    else:
        EMAIL_USE_TLS = bool(use_tls_value)
    EMAIL_HOST_USER = config_data.get("email", EMAIL_HOST_USER) or ""
    EMAIL_HOST_PASSWORD = config_data.get("app_password", EMAIL_HOST_PASSWORD) or ""
    ADMIN_APPROVER_EMAIL = (
        config_data.get("approver_email")
        or ADMIN_APPROVER_EMAIL
        or (EMAIL_HOST_USER or None)
    )
    DEFAULT_FROM_EMAIL = config_data.get("from_email", DEFAULT_FROM_EMAIL)

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
