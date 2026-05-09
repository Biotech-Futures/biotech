"""Top-level package init.

Importing the Celery app here ensures ``app`` is loaded when Django starts,
so the ``@shared_task`` decorator registers tasks against the right Celery
instance. See ``config/celery.py``.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
