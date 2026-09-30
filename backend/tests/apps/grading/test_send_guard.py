"""The bulk emails' runner: every item of a run is sent once, shared across
its workers, and the run's progress is kept for the page."""
from django.test import TestCase, override_settings

from apps.grading.models import EmailSendRun
from apps.grading.services.send_guard import AlreadySending, Work, run_state, start_run
from apps.users.models import User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendRunTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(email="admin@example.com", password="pw12345!")
        self.sent = []

    def _item(self, name, people, whole=True):
        def send(connection, cache):
            # Each worker's items share its connection and cache.
            cache.setdefault("items", []).append(name)
            self.sent.append((name, connection))
            return (people if whole else 1), whole
        return Work(people, send)

    def test_every_item_is_sent_once_and_the_progress_kept(self):
        work = [self._item(f"team{n}", 3) for n in range(5)] + [self._item("short", 2, whole=False)]
        start_run("test_email", self.actor, work)
        self.assertEqual(sorted(name for name, _ in self.sent), sorted([f"team{n}" for n in range(5)] + ["short"]))
        state = run_state("test_email")
        self.assertFalse(state["sending"])
        # A team not emailed in full isn't counted as emailed; it's a failure.
        self.assertEqual(
            {k: state["run"][k] for k in ("due", "emailed", "failed", "error")},
            {"due": 17, "emailed": 15, "failed": 1, "error": ""},
        )
        run = EmailSendRun.objects.get(key="test_email")
        self.assertEqual(run.started_by, self.actor)
        self.assertIsNotNone(run.finished_at)

    def test_items_are_shared_across_workers_each_with_its_own_connection(self):
        from apps.grading.services import send_guard

        work = [self._item(f"team{n}", 1) for n in range(7)]
        send_guard._take("test_email", due=7)
        send_guard._run("test_email", work, workers=3, threaded=False)
        self.assertEqual(len(self.sent), 7)
        # Three workers: seven items over three connections.
        self.assertEqual(len({id(connection) for _, connection in self.sent}), 3)
        self.assertEqual(EmailSendRun.objects.get(key="test_email").emailed, 7)

    def test_one_run_at_a_time(self):
        EmailSendRun.objects.create(key="test_email", held_until="2999-01-01T00:00:00Z")
        with self.assertRaises(AlreadySending):
            start_run("test_email", self.actor, [self._item("team", 1)])
        self.assertEqual(self.sent, [])
