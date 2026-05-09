"""Celery application for the BIOTech Futures backend.

Single Celery app shared by every Django app. Brokers and result backends are
read from Django settings (``CELERY_BROKER_URL`` / ``CELERY_RESULT_BACKEND``)
which in turn fall back to ``REDIS_URL``. Tasks are auto-discovered from any
``apps/*/tasks.py`` module.

Importing this module is cheap — it just constructs the ``Celery`` instance.
The actual broker connection is opened lazily when the first task is sent.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("biotech")

# Pull every ``CELERY_*`` setting from Django so configuration lives in one
# place (config/settings.py) rather than scattered across env vars and code.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Look for ``tasks.py`` in every installed Django app.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):  # pragma: no cover - smoke task for ops
    """Echo the request context. Useful for verifying broker connectivity."""
    print(f"Request: {self.request!r}")
