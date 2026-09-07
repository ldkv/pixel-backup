"""Django settings for the pixel_backup project."""

from pathlib import Path

from pixel_backup.env import ENV_VARS

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = "django-insecure-pixel-backup"  # nosec: no user-facing web app, LAN/local tool only
DEBUG = False
ALLOWED_HOSTS = ["*"]

ROOT_URLCONF = "pixel_backup.urls"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django_bolt",
    "pixel_backup.history",
]

ENV_VARS.db_path.parent.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ENV_VARS.db_path,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
