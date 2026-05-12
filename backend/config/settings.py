from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(value):
    value = str(value).strip().lower()
    if value in {"1", "true", "t", "yes", "y", "on", "debug"}:
        return True
    if value in {"0", "false", "f", "no", "n", "off", "release", "prod", "production", ""}:
        return False
    raise ValueError(f"Invalid truth value: {value}")

SECRET_KEY = config("DJANGO_SECRET_KEY", default="dev-only-not-for-production")
DEBUG = config("DEBUG", default="true", cast=env_bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

INSTALLED_APPS = [
    'daphne',
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    'apps.admin.apps.AdminConfig',
    'apps.users',
    'apps.groups',
    'apps.chat',
    'apps.resources',
    'apps.announcements',
    'apps.audit',
    'apps.dashboard',
    'apps.events',
    'apps.user_sessions',
    'apps.matching_runtime',
    'apps.tasks',
    'apps.workshops',
    'apps.certificates',
    'apps.services',
    'matching',
    'drf_spectacular',
    'rest_framework',
    'django_filters',
    'drf_spectacular_sidecar',
    'corsheaders',
    'channels',
    'storages',
]

# Azure Blob Storage
AZURE_ACCOUNT_NAME = config("AZURE_ACCOUNT_NAME", default="")
AZURE_ACCOUNT_KEY = config("AZURE_ACCOUNT_KEY", default="")
AZURE_CONTAINER = config("AZURE_CONTAINER", default="media")
AZURE_CONNECTION_STRING = config(
    "AZURE_CONNECTION_STRING",
    default=config("AZURE_STORAGE_CONNECTION_STRING", default=""),
)
AZURE_RESOURCE_CONTAINER = config("AZURE_RESOURCE_CONTAINER", default=AZURE_CONTAINER or "resources")
AZURE_CHAT_CONTAINER = config("AZURE_CHAT_CONTAINER", default="chat")
AZURE_URL_EXPIRATION_SECS = config("AZURE_URL_EXPIRATION_SECS", default=3600, cast=int)
AZURE_CUSTOM_DOMAIN = config(
    "AZURE_CUSTOM_DOMAIN",
    default=f"{AZURE_ACCOUNT_NAME}.blob.core.windows.net" if AZURE_ACCOUNT_NAME else "",
)

# Azure Blob is the only supported file backend.
USE_AZURE_BLOB_STORAGE = True
DEFAULT_FILE_STORAGE = "storages.backends.azure_storage.AzureStorage"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

RESOURCE_FILE_MAX_UPLOAD_SIZE = config(
    "RESOURCE_FILE_MAX_UPLOAD_SIZE",
    default=25 * 1024 * 1024,
    cast=int,
)
CHAT_ATTACHMENT_MAX_UPLOAD_SIZE = config(
    "CHAT_ATTACHMENT_MAX_UPLOAD_SIZE",
    default=10 * 1024 * 1024,
    cast=int,
)
RESOURCE_FILE_ALLOWED_EXTENSIONS = tuple(
    str(value).strip().lower().lstrip(".")
    for value in config(
        "RESOURCE_FILE_ALLOWED_EXTENSIONS",
        default="pdf,txt,csv,png,jpg,jpeg,gif,webp,doc,docx,xls,xlsx,ppt,pptx",
        cast=Csv(),
    )
    if str(value).strip()
)
RESOURCE_FILE_ALLOWED_MIME_TYPES = tuple(
    str(value).strip().lower()
    for value in config(
        "RESOURCE_FILE_ALLOWED_MIME_TYPES",
        default=(
            "application/pdf,text/plain,text/csv,image/png,image/jpeg,image/gif,image/webp,"
            "application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
            "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
            "application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        cast=Csv(),
    )
    if str(value).strip()
)
CHAT_ATTACHMENT_ALLOWED_EXTENSIONS = tuple(
    str(value).strip().lower().lstrip(".")
    for value in config(
        "CHAT_ATTACHMENT_ALLOWED_EXTENSIONS",
        default="pdf,txt,csv,png,jpg,jpeg,gif,webp,doc,docx,xls,xlsx,ppt,pptx",
        cast=Csv(),
    )
    if str(value).strip()
)
CHAT_ATTACHMENT_ALLOWED_MIME_TYPES = tuple(
    str(value).strip().lower()
    for value in config(
        "CHAT_ATTACHMENT_ALLOWED_MIME_TYPES",
        default=(
            "application/pdf,text/plain,text/csv,image/png,image/jpeg,image/gif,image/webp,"
            "application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
            "application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,"
            "application/vnd.ms-powerpoint,application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
        cast=Csv(),
    )
    if str(value).strip()
)

AUTH_USER_MODEL = 'users.User'

# REST Framework with Django Session Authentication
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'EXCEPTION_HANDLER': 'config.exception_handler.custom_exception_handler',
}



SPECTACULAR_SETTINGS = {
    'TITLE': 'BIOTech Futures Mentoring Platform API',
    'DESCRIPTION': 'API Documentation for the New BIOTech Futures Mentoring Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.user_sessions.middleware.SessionTrackingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database — local PostgreSQL for development
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="postgres"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default=""),
        "HOST": config("DB_HOST", default="127.0.0.1"),
        "PORT": config("DB_PORT", default="5432"),
        "OPTIONS": {
            "sslmode": "require",
            "connect_timeout": 5,
        },
        "CONN_MAX_AGE": 0,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Email
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="sandbox.smtp.mailtrap.io")
EMAIL_PORT = config("EMAIL_PORT", default=2525, cast=int)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default="true", cast=env_bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

REDIS_URL = config("REDIS_URL", default="")

if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
                "capacity": 1500,
                "expiry": 60,
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[{asctime}] {levelname} {name} :: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "config": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    cast=Csv()
)

CORS_ALLOW_CREDENTIALS = True

SESSION_COOKIE_NAME = 'sessionid'
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_DOMAIN = None
SESSION_SAVE_EVERY_REQUEST = False

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    cast=Csv()
)

FRONTEND_BASE_URL = config(
    "FRONTEND_BASE_URL", default="http://localhost:5173"
).rstrip("/")

ADMIN_FRONTEND_BASE_URL = config(
    "ADMIN_FRONTEND_BASE_URL", default="https://mentoringadmin.biotechfutures.org"
).rstrip("/")

# Magic link still uses hash routing while the others use path routing —
# unify in a follow-up once the SPA serves /auth/callback without a hash.
MAGIC_LINK_REDIRECT_URL             = f"{FRONTEND_BASE_URL}/#/auth/callback"
ADMIN_MAGIC_LINK_REDIRECT_URL       = f"{ADMIN_FRONTEND_BASE_URL}/auth/callback"
PASSWORD_RESET_REDIRECT_URL         = f"{FRONTEND_BASE_URL}/auth/reset-password"
ADMIN_PASSWORD_RESET_REDIRECT_URL   = f"{ADMIN_FRONTEND_BASE_URL}/auth/reset-password"

# Django's admin LoginView reads LOGIN_REDIRECT_URL after a successful login
# when no ?next= is present. Keep it on a Django-side URL so an engineer who
# types /admin/login/ directly lands on the admin dashboard, not the SPA.
LOGIN_REDIRECT_URL = "/admin/"

PASSWORD_RESET_TOKEN_EXPIRY_MINUTES = config(
    "PASSWORD_RESET_TOKEN_EXPIRY_MINUTES", default=30, cast=int,
)
BACKEND_URL = config("BACKEND_URL", default="http://localhost:8000")

# --- Chat sanitiser ----------------------------------------------------------
# Sanitisation policy is sourced from environment variables so moderation
# changes do not require a code deploy. See apps/chat/utils.py for the full
# stem / whole-word grammar.
#
#   CHAT_SANITIZER_BLACKLIST    comma-separated entries. Each entry is one of:
#                                 - a stem (trailing ``*``), e.g. ``fuck*`` —
#                                   substring match with leet/spacing
#                                   tolerance; catches ``fucker``, ``brainfuck``,
#                                   ``f*ck``, ``fuuuck`` automatically.
#                                 - a whole-word, e.g. ``hell`` — letter-
#                                   boundary anchored, used for short letter
#                                   sequences that occur as substrings of
#                                   innocent words (``hello``, ``passive``).
#   CHAT_SANITIZER_REPLACEMENT  replacement token, "***" by default.
CHAT_SANITIZER_BLACKLIST = config(
    "CHAT_SANITIZER_BLACKLIST",
    default=(
        # Stems (trailing "*" -> substring + leet-tolerant match).
        "fuck*,shit*,dick*,bitch*,cock*,cunt*,prick*,"
        "pussy*,nigger*,nigga*,faggot*,"
        # Whole-words (no trailing "*" -> letter-boundary anchored).
        "hell,damn,crap,piss,ass,asshole,arsehole,asshat,bastard,wanker,twat"
    ),
    cast=Csv(),
)

CHAT_SANITIZER_REPLACEMENT = config("CHAT_SANITIZER_REPLACEMENT", default="***")
TENOR_API_KEY = config("TENOR_API_KEY", default="")