"""The bulk emails' runner: every item of a run is sent once, shared across
its workers, and the run's progress, and who it missed, kept for the page."""
from django.test import TestCase, override_settings

from apps.management.models import EmailSendRun
from apps.management.services import send_guard
from apps.management.services.send_guard import AlreadySending, Work, run_state, start_run
from apps.users.models import User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendRunTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(email="admin@example.com", password="pw12345!")
        self.sent = []

    def _item(self, team, people, reached=None):
        """A team of ``people``; all but the first ``reached`` missed, if given."""
        labels = [f"({team}) Person {n}" for n in range(people)]

        def send(connection, cache):
            # Each worker's items share its connection and cache.
            cache.setdefault("items", []).append(team)
            self.sent.append((team, connection))
            return labels[reached:] if reached is not None else []
        return Work(labels, send)

    def test_every_item_is_sent_once_and_the_progress_kept(self):
        work = [self._item(f"BTF{n}", 3) for n in range(5)] + [self._item("BTF9", 2, reached=1)]
        start_run("test_email", self.actor, work)
        self.assertEqual(sorted(team for team, _ in self.sent), sorted([f"BTF{n}" for n in range(5)] + ["BTF9"]))
        state = run_state("test_email")
        self.assertFalse(state["sending"])
        # A team not emailed in full is a failure, and who it missed is named.
        self.assertEqual(
            {k: state["run"][k] for k in ("due", "emailed", "failed", "error", "missed")},
            {"due": 17, "emailed": 16, "failed": 1, "error": "", "missed": ["(BTF9) Person 1"]},
        )
        run = EmailSendRun.objects.get(key="test_email")
        self.assertEqual(run.started_by, self.actor)
        self.assertIsNotNone(run.finished_at)

    def test_a_new_run_starts_its_list_afresh(self):
        start_run("test_email", self.actor, [self._item("BTF1", 2, reached=0)])
        self.assertEqual(run_state("test_email")["run"]["missed"], ["(BTF1) Person 0", "(BTF1) Person 1"])
        start_run("test_email", self.actor, [self._item("BTF1", 2)])
        self.assertEqual(run_state("test_email")["run"]["missed"], [])

    def test_items_are_shared_across_workers_each_with_its_own_connection(self):
        work = [self._item(f"BTF{n}", 1) for n in range(7)]
        send_guard._take("test_email", due=7)
        send_guard._run("test_email", work, workers=3, threaded=False)
        self.assertEqual(len(self.sent), 7)
        # Three workers: seven items over three connections.
        self.assertEqual(len({id(connection) for _, connection in self.sent}), 3)
        self.assertEqual(EmailSendRun.objects.get(key="test_email").emailed, 7)

    def test_one_run_at_a_time(self):
        EmailSendRun.objects.create(key="test_email", held_until="2999-01-01T00:00:00Z")
        with self.assertRaises(AlreadySending):
            start_run("test_email", self.actor, [self._item("BTF1", 1)])
        self.assertEqual(self.sent, [])
