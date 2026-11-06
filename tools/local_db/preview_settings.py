"""Local-only Analytics/AI demo runtime; never used by a deployment."""
from django_settings import *  # noqa: F403
import os
from pathlib import Path

ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'backend', 'testserver']
CORS_ALLOWED_ORIGINS = ['http://127.0.0.1:5187', 'http://localhost:5187']
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = '/runtime/mail'
MEDIA_ROOT = '/runtime/media'
SCHEDULER_ENABLED = False
EMAIL_PRECHECK_ENABLED = False
EMAIL_CHECK_ON_EDIT = False
AUTH_EMAIL_DISPATCH_SYNC = True
BULK_EMAIL_DISPATCH_SYNC = True
OPENAI_API_KEY = ''
if os.environ.get('OPENAI_API_KEY_FILE'):
    OPENAI_API_KEY = Path(os.environ['OPENAI_API_KEY_FILE']).read_text().strip()
