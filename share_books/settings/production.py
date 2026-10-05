"""Production settings for Railway: DEBUG off, PostgreSQL, bucket media storage.

Required environment variables: SECRET_KEY, DATABASE_URL.
Optional: ALLOWED_HOSTS / CSRF_TRUSTED_ORIGINS (comma separated; Railway's
RAILWAY_PUBLIC_DOMAIN is used automatically), and the Railway bucket variables
AWS_S3_BUCKET_NAME, AWS_ENDPOINT_URL, AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION.  Without a bucket, media is stored
in the folder given by MEDIA_ROOT (default: ./media), e.g. a mounted volume.
"""

import os
from pathlib import Path

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, MIDDLEWARE


def _env_list(name):
    return [v.strip() for v in os.environ.get(name, '').split(',') if v.strip()]


SECRET_KEY = os.environ['SECRET_KEY']

DEBUG = False

ALLOWED_HOSTS = _env_list('ALLOWED_HOSTS')
CSRF_TRUSTED_ORIGINS = _env_list('CSRF_TRUSTED_ORIGINS')
_railway_domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN')
if _railway_domain:
    ALLOWED_HOSTS.append(_railway_domain)
    CSRF_TRUSTED_ORIGINS.append(f'https://{_railway_domain}')

DATABASES = {
    'default': dj_database_url.config(
        env='DATABASE_URL', conn_max_age=600, conn_health_checks=True
    )
}

# Static files served by WhiteNoise
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files: Railway bucket (S3 compatible) if configured, else local folder
_bucket = os.environ.get('AWS_S3_BUCKET_NAME')
if _bucket:
    AWS_STORAGE_BUCKET_NAME = _bucket
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_ENDPOINT_URL')
    AWS_S3_REGION_NAME = os.environ.get('AWS_DEFAULT_REGION')
    AWS_S3_ADDRESSING_STYLE = 'virtual'
    AWS_QUERYSTRING_AUTH = True
    STORAGES = {
        'default': {'BACKEND': 'storages.backends.s3.S3Storage'},
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        },
    }
else:
    MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        },
    }

# Security
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
