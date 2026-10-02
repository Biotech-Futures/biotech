"""The bulk emails' runner: every item of a run is sent, shared across its
workers, those that missed someone tried once more at the end, and the
run's progress, and who it missed, kept for the page."""
from unittest import mock

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
            missed = labels[reached:] if reached is not None else []
            return [{"who": who, "reason": "address refused"} for who in missed]
        return Work(labels, send)

    def test_every_item_is_sent_and_the_progress_kept(self):
        work = [self._item(f"BTF{n}", 3) for n in range(5)] + [self._item("BTF9", 2, reached=1)]
        start_run("test_email", self.actor, work)
        # The one that missed someone is tried twice.
        self.assertEqual(
            sorted(team for team, _ in self.sent), sorted([f"BTF{n}" for n in range(5)] + ["BTF9", "BTF9"]),
        )
        state = run_state("test_email")
        self.assertFalse(state["sending"])
        # A team not emailed in full is a failure, and who it missed is named.
        self.assertEqual(
            {k: state["run"][k] for k in ("due", "emailed", "failed", "error", "missed")},
            {"due": 17, "emailed": 16, "failed": 1, "error": "",
             "missed": [{"who": "(BTF9) Person 1", "reason": "address refused"}]},
        )
        run = EmailSendRun.objects.get(key="test_email")
        self.assertEqual(run.started_by, self.actor)
        self.assertIsNotNone(run.finished_at)

    def test_once_all_are_tried_it_waits_then_tries_those_that_failed(self):
        missed_once = {"BTF2"}

        def send(connection, cache):
            # Ben misses it the first time only.
            self.sent.append(("BTF2", connection))
            if "BTF2" in missed_once:
                missed_once.clear()
                return [{"who": "(BTF2) Ben", "reason": "mail server busy"}]
            return []

        work = [self._item("BTF1", 2), Work(["(BTF2) Amy", "(BTF2) Ben"], send), self._item("BTF3", 1)]
        with override_settings(BULK_EMAIL_RETRY_SECONDS=5), \
                mock.patch("apps.management.services.send_guard.time.sleep") as sleep:
            start_run("test_email", self.actor, work)
        # Every team first, then a wait, then only the one that failed.
        self.assertEqual([team for team, _ in self.sent], ["BTF1", "BTF2", "BTF3", "BTF2"])
        sleep.assert_called_once_with(5)
        run = run_state("test_email")["run"]
        self.assertEqual((run["due"], run["emailed"], run["failed"], run["missed"]), (5, 5, 0, []))

    def test_no_wait_when_nothing_failed(self):
        with mock.patch("apps.management.services.send_guard.time.sleep") as sleep:
            start_run("test_email", self.actor, [self._item("BTF1", 2)])
        sleep.assert_not_called()

    def test_who_the_second_try_still_misses_is_listed_with_its_reason(self):
        tries = []

        def send(connection, cache):
            tries.append(1)
            reason = "mail server busy" if len(tries) == 1 else "sending limit reached"
            return [{"who": "(BTF1) Ben", "reason": reason}]

        start_run("test_email", self.actor, [Work(["(BTF1) Amy", "(BTF1) Ben"], send)])
        run = run_state("test_email")["run"]
        self.assertEqual(
            (run["emailed"], run["failed"], run["missed"]),
            (1, 1, [{"who": "(BTF1) Ben", "reason": "sending limit reached"}]),
        )

    def test_an_unreachable_server_is_tried_again_before_giving_up(self):
        opens = []

        def open_fails_once(connection):
            opens.append(1)
            if len(opens) == 1:
                raise OSError("unreachable")

        with mock.patch("django.core.mail.backends.locmem.EmailBackend.open", autospec=True,
                        side_effect=open_fails_once), \
                self.assertLogs("apps.management.services.send_guard", level="ERROR"):
            start_run("test_email", self.actor, [self._item("BTF1", 2)])
        run = run_state("test_email")["run"]
        self.assertEqual((run["emailed"], run["failed"], run["error"], run["missed"]), (2, 0, "", []))

    def test_a_new_run_starts_its_list_afresh(self):
        start_run("test_email", self.actor, [self._item("BTF1", 2, reached=0)])
        self.assertEqual(
            [m["who"] for m in run_state("test_email")["run"]["missed"]], ["(BTF1) Person 0", "(BTF1) Person 1"],
        )
        start_run("test_email", self.actor, [self._item("BTF1", 2)])
        self.assertEqual(run_state("test_email")["run"]["missed"], [])

    def test_a_run_from_before_reasons_were_kept_lists_names_only(self):
        EmailSendRun.objects.create(
            key="test_email", started_at="2026-10-01T00:00:00Z", due=2, emailed=1, failed=1, missed=["(BTF1) Amy"],
        )
        self.assertEqual(run_state("test_email")["run"]["missed"], [{"who": "(BTF1) Amy", "reason": ""}])

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
