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

# Only honor X-Forwarded-For for rate-limit keys (apps/services/views.py
# `_client_ip`) when the app sits behind a trusted reverse proxy / CDN that
# overwrites the header — Azure Front Door, App Service ingress, ALB, etc.
# Direct exposure means the header is attacker-controlled, so the secure
# default is False; production sets TRUST_FORWARDED_FOR=true explicitly.
TRUST_FORWARDED_FOR = config("TRUST_FORWARDED_FOR", default="false", cast=env_bool)

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
RESOURCE_INLINE_HTML_MAX_BYTES = config(
    "RESOURCE_INLINE_HTML_MAX_BYTES",
    default=2 * 1024 * 1024,
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
CHAT_REACTION_EMOJIS = tuple(
    str(value).strip()
    for value in config(
        "CHAT_REACTION_EMOJIS",
        default="\U0001F44D,❤️,\U0001F389",
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
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'event_bulk_invite': '30/min',
    },
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'BIOTech Futures Mentoring Platform API',
    'DESCRIPTION': 'API Documentation for the New BIOTech Futures Mentoring Platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # Restrict the generated schema to canonical ``/api/v1/...`` paths. Legacy
    # ``/<app>/...`` and in-app ``v1/`` aliases still resolve at runtime — they
    # just don't show up in OpenAPI. Removes operationId-collision warnings
    # caused by dual-mounting the same view at multiple URLs. See
    # ``config/spectacular_hooks.py`` for the filter.
    'PREPROCESSING_HOOKS': [
        'config.spectacular_hooks.filter_v1_only',
    ],
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # GZip must sit above middleware that touches response content.
    "django.middleware.gzip.GZipMiddleware",
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
        # Persistent connections — avoids a TLS handshake (100-300ms on Azure
        # Postgres) on every request. 300s is a safe default below worker idle
        # timeouts; each gunicorn worker keeps one warm connection per request
        # path. Total idle conns ≈ worker_count, well within Burstable caps.
        "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=300, cast=int),
        # Drop dead connections at the start of each request instead of
        # raising OperationalError. Pairs with CONN_MAX_AGE — Azure Postgres
        # idles connections out under load and reconnect-on-demand keeps the
        # site usable instead of cascading to 500s until the workers restart.
        "CONN_HEALTH_CHECKS": True,
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
    # ``RedisPubSubChannelLayer`` uses Redis pub/sub instead of the legacy
    # MULTI/pipeline-based ``RedisChannelLayer``. Azure Cache for Redis
    # Enterprise (and any clustered Redis) rejects MULTI pipelines whose keys
    # land on different cluster slots with CROSSSLOT. The pubsub layer only
    # PUBLISH/SUBSCRIBEs against single keys per command, so it works on
    # both clustered and standalone Redis. Same wire protocol for consumers,
    # no app-side changes needed.
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.pubsub.RedisPubSubChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }

# Use Redis as the cache backend so rate-limit counters are shared across
# all workers and survive restarts. Falls back to LocMemCache when REDIS_URL
# is not set (local dev without Redis).

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
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

# Azure App Service terminates TLS at the frontend and forwards plain HTTP to the
# app, so request.is_secure()/request.scheme are wrong unless we trust the proxy's
# X-Forwarded-Proto. Without this, DRF's reverse(request=request) builds http:// URLs
# (download_url, access_url) and the browser blocks them as mixed content.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_NAME = 'sessionid'
SESSION_COOKIE_AGE = 86400
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_DOMAIN = None
SESSION_SAVE_EVERY_REQUEST = False

# Cached auth backend skips the User.objects.get() in
# AuthenticationMiddleware on every request — see apps/users/backends.py.
# Sessions stay on the DB backend because the password-reset flow scans
# django_session to revoke all of a user's sessions; moving sessions to
# Redis would silently break that security guarantee. Revisit once we
# have a Redis-aware session-flush helper.
AUTHENTICATION_BACKENDS = [
    "apps.users.backends.CachedModelBackend",
]

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    cast=Csv()
)

# Public base URLs of the SPAs. Used to build the user-visible links in
# password-reset and magic-link emails (apps/services/auth_service). MUST
# be set explicitly in any non-DEBUG deploy — a missing env var would
# otherwise silently email reset/magic links pointing at
# http://localhost:5173 (or, worse for ADMIN_FRONTEND_BASE_URL, at the
# production admin portal from a staging deploy), breaking login and
# leaking infra info. In DEBUG (local dev) we keep the localhost default
# for FRONTEND_BASE_URL so `runserver` works out of the box; the admin
# portal has no public dev URL so it falls back to the canonical prod
# host only under DEBUG.
_FRONTEND_BASE_URL_RAW = config("FRONTEND_BASE_URL", default="")
if not _FRONTEND_BASE_URL_RAW:
    if DEBUG:
        _FRONTEND_BASE_URL_RAW = "http://localhost:5173"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "FRONTEND_BASE_URL must be set (e.g. https://mentoring.biotechfutures.org) "
            "outside DEBUG. Password-reset and magic-link emails are built from it."
        )
FRONTEND_BASE_URL = _FRONTEND_BASE_URL_RAW.rstrip("/")

_ADMIN_FRONTEND_BASE_URL_RAW = config("ADMIN_FRONTEND_BASE_URL", default="")
if not _ADMIN_FRONTEND_BASE_URL_RAW:
    if DEBUG:
        _ADMIN_FRONTEND_BASE_URL_RAW = "https://mentoringadmin.biotechfutures.org"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "ADMIN_FRONTEND_BASE_URL must be set (e.g. https://mentoringadmin.biotechfutures.org) "
            "outside DEBUG. Admin password-reset and magic-link emails are built from it."
        )
ADMIN_FRONTEND_BASE_URL = _ADMIN_FRONTEND_BASE_URL_RAW.rstrip("/")

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

# Public base URL of this backend. Used to build the magic-link href in OTP
# emails (apps/services/auth_service.send_login_code). MUST be set explicitly
# in any non-DEBUG deploy — otherwise a missing env var would silently email
# magic links pointing at http://localhost:8000, breaking login and leaking
# infra info. In DEBUG (local dev) we keep the localhost default so
# `runserver` works out of the box.
_BACKEND_URL_RAW = config("BACKEND_URL", default="")
if not _BACKEND_URL_RAW:
    if DEBUG:
        _BACKEND_URL_RAW = "http://localhost:8000"
    else:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured(
            "BACKEND_URL must be set (e.g. https://api.biotechfutures.org) "
            "outside DEBUG. Magic-link emails are built from it."
        )
BACKEND_URL = _BACKEND_URL_RAW.rstrip("/")

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

# Shared secret for POST /api/v1/events/admin/send-rsvp-reminders/. The legacy
# /events/v1/admin/send-rsvp-reminders/ route also resolves for existing
# schedulers. The endpoint returns 503 if it's unset, so a misconfigured deploy
# fails loud instead of silently exposing an unauthenticated trigger.
RSVP_REMINDER_TOKEN = config("RSVP_REMINDER_TOKEN", default="")

# Shared secret for POST /api/v1/updjoinperms (and the legacy /users/updjoinperms
# alias). The upstream join-permission consent form sends this token in the
# ``X-Join-Permission-Token`` header. Same fail-loud contract as
# ``RSVP_REMINDER_TOKEN``: empty value => 503 from the endpoint, so a
# misconfigured deploy can't silently expose an unauthenticated webhook.
JOIN_PERMISSION_WEBHOOK_TOKEN = config("JOIN_PERMISSION_WEBHOOK_TOKEN", default="")

# RSVP reminder windows. Hourly dispatcher scans events HOURS_AHEAD to
# HOURS_AHEAD + WINDOW_HOURS away — defaults match the standard 24h/1h
# capture per kind under an hourly trigger.
RSVP_REMINDER_24H_HOURS_AHEAD = config(
    "RSVP_REMINDER_24H_HOURS_AHEAD", default=24, cast=int
)
RSVP_REMINDER_24H_WINDOW_HOURS = config(
    "RSVP_REMINDER_24H_WINDOW_HOURS", default=1, cast=int
)
RSVP_REMINDER_1H_HOURS_AHEAD = config(
    "RSVP_REMINDER_1H_HOURS_AHEAD", default=1, cast=int
)
RSVP_REMINDER_1H_WINDOW_HOURS = config(
    "RSVP_REMINDER_1H_WINDOW_HOURS", default=1, cast=int
)

# --- Link previews -----------------------------------------------------------
# OG metadata cache lives in Redis under ``cache:og:<md5(url)>``. The 24h TTL
# matches the requirement to dedupe a globally-previewed URL across users.
#
# Unfurling runs in-process on a daemon thread spawned from the request handler
# after ``transaction.on_commit`` — no Celery/broker required. See
# ``apps/chat/tasks.py`` for the dispatcher and ``apps/chat/og_extractor.py``
# for the parser.
LINK_PREVIEW_CACHE_TTL_SECONDS = config(
    "LINK_PREVIEW_CACHE_TTL_SECONDS", default=60 * 60 * 24, cast=int,
)
# Hard cap on outbound HTTP fetch — keeps a slow target site from pinning a
# worker thread for too long. Connection timeout is intentionally tighter than
# the read timeout so unreachable hosts fail fast.
LINK_PREVIEW_FETCH_CONNECT_TIMEOUT = config(
    "LINK_PREVIEW_FETCH_CONNECT_TIMEOUT", default=3.0, cast=float,
)
LINK_PREVIEW_FETCH_READ_TIMEOUT = config(
    "LINK_PREVIEW_FETCH_READ_TIMEOUT", default=5.0, cast=float,
)
# Cap response body size before parsing. Anything larger almost certainly
# isn't an HTML page worth unfurling and would blow worker memory.
LINK_PREVIEW_MAX_BYTES = config(
    "LINK_PREVIEW_MAX_BYTES", default=512 * 1024, cast=int,
)
LINK_PREVIEW_USER_AGENT = config(
    "LINK_PREVIEW_USER_AGENT",
    default="BiotechFuturesBot/1.0 (+https://biotechfutures.org)",
)
# Synchronous dispatch (used by tests) runs the unfurl inline instead of on a
# thread, so assertions can observe the DB row and broadcast immediately.
LINK_PREVIEW_DISPATCH_SYNC = config(
    "LINK_PREVIEW_DISPATCH_SYNC", default="false", cast=env_bool,
)
