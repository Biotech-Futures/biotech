from django.test import SimpleTestCase, override_settings

from apps.tasks.tasks import debug_echo
from config.celery import app


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
)
class DebugEchoTaskTests(SimpleTestCase):
    def test_debug_echo_is_autodiscovered(self):
        app.autodiscover_tasks(force=True)

        self.assertIn("tasks.debug_echo", app.tasks)

    def test_debug_echo_returns_payload(self):
        result = debug_echo.delay("hello")

        self.assertEqual(result.get(), {"echo": "hello"})
