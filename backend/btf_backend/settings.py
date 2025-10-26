"""
Django settings for btf_backend project.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'channels',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'storages',

    # Local apps
    'authentication',
    'users',
    'groups',
    'chat',
    'resources',
    'events',
    'announcements',
    'core',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'btf_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'btf_backend.wsgi.application'
ASGI_APPLICATION = 'btf_backend.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'btf_db'),
        'USER': os.getenv('DB_USER', 'btf_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

if 'test' in sys.argv:
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }

# Redis Cache
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME_HOURS', 1))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME_DAYS', 7))),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL_ORIGINS', 'False') == 'True'
if CORS_ALLOW_ALL_ORIGINS:
    CORS_ALLOWED_ORIGINS = []
else:
    CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5173').split(',')
CORS_ALLOW_CREDENTIALS = True

# Email Configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@biotechfutures.org')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '25'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'False') == 'True'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

# Frontend + Authentication configuration
FRONTEND_BASE_URL = os.getenv('FRONTEND_BASE_URL', 'https://yourdomain.com')
MAGIC_LINK_EXPIRY_SECONDS = int(os.getenv('MAGIC_LINK_EXPIRY_SECONDS', '600'))

# DRF Spectacular (OpenAPI) Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'BIOTech Futures Hub API',
    'DESCRIPTION': 'API documentation for BIOTech Futures Hub platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
}

# Realtime messaging / Channels configuration
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

CHANNEL_REDIS_URL = os.getenv('CHANNEL_REDIS_URL') or os.getenv('REDIS_URL')
if CHANNEL_REDIS_URL:
    CHANNEL_LAYERS['default'] = {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [CHANNEL_REDIS_URL],
        },
    }

# File upload scanning defaults
FILE_UPLOAD_MAX_BYTES = int(os.getenv('FILE_UPLOAD_MAX_BYTES', str(25 * 1024 * 1024)))
FILE_UPLOAD_ALLOWED_MIME_TYPES = [
    mime.strip()
    for mime in os.getenv(
        'FILE_UPLOAD_ALLOWED_MIME_TYPES',
        'application/pdf,image/png,image/jpeg,image/gif,text/plain,video/mp4,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/zip'
    ).split(',')
    if mime.strip()
]
FILE_UPLOAD_BLOCKED_EXTENSIONS = [
    ext.strip().lower()
    for ext in os.getenv('FILE_UPLOAD_BLOCKED_EXTENSIONS', '.exe,.bat,.sh,.cmd,.msi,.vbs').split(',')
    if ext.strip()
]
FILE_UPLOAD_SCAN_COMMAND = os.getenv('FILE_UPLOAD_SCAN_COMMAND', '').strip() or None

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# Object Storage (Vultr S3 compatible)
VULTR_ACCESS_KEY = os.getenv('VULTR_ACCESS_KEY')
VULTR_SECRET_KEY = os.getenv('VULTR_SECRET_KEY')
VULTR_BUCKET_NAME = os.getenv('VULTR_BUCKET_NAME')
VULTR_S3_ENDPOINT = os.getenv('VULTR_S3_ENDPOINT')
VULTR_S3_REGION = os.getenv('VULTR_S3_REGION', 'sgp1')

if all([VULTR_ACCESS_KEY, VULTR_SECRET_KEY, VULTR_BUCKET_NAME, VULTR_S3_ENDPOINT]):
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

    AWS_ACCESS_KEY_ID = VULTR_ACCESS_KEY
    AWS_SECRET_ACCESS_KEY = VULTR_SECRET_KEY
    AWS_STORAGE_BUCKET_NAME = VULTR_BUCKET_NAME
    AWS_S3_ENDPOINT_URL = VULTR_S3_ENDPOINT
    AWS_S3_REGION_NAME = VULTR_S3_REGION
    AWS_DEFAULT_ACL = os.getenv('VULTR_DEFAULT_ACL', 'public-read')
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
    AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}

    parsed_endpoint = urlparse(VULTR_S3_ENDPOINT)
    endpoint_host = parsed_endpoint.netloc or parsed_endpoint.path
    AWS_S3_CUSTOM_DOMAIN = os.getenv(
        'VULTR_S3_CUSTOM_DOMAIN',
        f'{VULTR_BUCKET_NAME}.{endpoint_host}' if endpoint_host else None,
    )
