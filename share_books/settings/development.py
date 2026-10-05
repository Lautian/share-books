"""Development settings: SQLite, DEBUG on, local media folder."""

import os

from .base import *  # noqa: F401,F403
from .base import BASE_DIR

# SECURITY WARNING: development-only key, never use in production.
SECRET_KEY = 'django-insecure-_o@ek3vuu9e07uv)v$h-3z817b@sx&q#f600#h8hw#ov#^+xut'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]']

# Trust localhost origins for local development.  Once CSRF_TRUSTED_ORIGINS is
# set Django enforces strict origin checking on every POST, so all origins that
# the browser may report (with or without an explicit port) must be listed.
# Both http:// and https:// are included because VS Code port-forwarding and
# some Codespaces setups serve the forwarded port over HTTPS even for localhost.
CSRF_TRUSTED_ORIGINS = [
    'http://localhost',
    'http://localhost:8000',
    'https://localhost',
    'https://localhost:8000',
    'http://127.0.0.1',
    'http://127.0.0.1:8000',
    'https://127.0.0.1',
    'https://127.0.0.1:8000',
]

# GitHub Codespaces support
# When CODESPACE_NAME is set (automatically by Codespaces), requests arrive through
# a reverse proxy that rewrites the host/scheme.  Enable the proxy-header settings
# so request.build_absolute_uri() returns the correct public URL
# (e.g. https://<id>-8000.app.github.dev) rather than http://localhost:8000.
if os.environ.get('CODESPACE_NAME'):
    USE_X_FORWARDED_HOST = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    ALLOWED_HOSTS += ['.app.github.dev']
    # Also trust the public Codespaces URL so POSTs from the forwarded-port
    # browser tab pass origin checking.
    CSRF_TRUSTED_ORIGINS += ['https://*.app.github.dev']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

MEDIA_ROOT = BASE_DIR / 'media'
