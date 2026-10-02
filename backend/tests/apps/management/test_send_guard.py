"""The bulk emails' runner: sends wait their turn in one queue, every item
of a run is sent, shared across its workers, those that missed someone tried
once more at the end, and the run's progress, and who it missed, kept for
the page."""
from datetime import timedelta
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.management.models import EmailSendRun, QueuedEmailSend
from apps.management.services import send_guard
from apps.management.services.send_guard import QUEUE_KEY, Work, run_state
from apps.users.models import User

LOCMEM = "django.core.mail.backends.locmem.EmailBackend"


@override_settings(EMAIL_BACKEND=LOCMEM)
class SendRunTests(TestCase):
    def setUp(self):
        self.actor = User.objects.create_user(email="admin@example.com", password="pw12345!")
        self.sent = []
        # Each test's own emails, gone after it.
        builders = mock.patch.dict(send_guard.BUILDERS)
        builders.start()
        self.addCleanup(builders.stop)
        self.works: dict[str, list] = {}

    def _press(self, key, work, options=None):
        """Press Send on ``key``'s email, whose send is ``work``: queued, and
        sent at once (inline under test settings) when nothing is ahead."""
        self.works.setdefault(key, []).append(work)
        send_guard.BUILDERS[key] = lambda actor, opts: self.works[key].pop(0)
        send_guard.queue_send(key, self.actor, options)

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
        self._press("test_email", work)
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
            self._press("test_email", work)
        # Every team first, then a wait, then only the one that failed.
        self.assertEqual([team for team, _ in self.sent], ["BTF1", "BTF2", "BTF3", "BTF2"])
        sleep.assert_called_once_with(5)
        run = run_state("test_email")["run"]
        self.assertEqual((run["due"], run["emailed"], run["failed"], run["missed"]), (5, 5, 0, []))

    def test_no_wait_when_nothing_failed(self):
        with mock.patch("apps.management.services.send_guard.time.sleep") as sleep:
            self._press("test_email", [self._item("BTF1", 2)])
        sleep.assert_not_called()

    def test_who_the_second_try_still_misses_is_listed_with_its_reason(self):
        tries = []

        def send(connection, cache):
            tries.append(1)
            reason = "mail server busy" if len(tries) == 1 else "sending limit reached"
            return [{"who": "(BTF1) Ben", "reason": reason}]

        self._press("test_email", [Work(["(BTF1) Amy", "(BTF1) Ben"], send)])
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
            self._press("test_email", [self._item("BTF1", 2)])
        run = run_state("test_email")["run"]
        self.assertEqual((run["emailed"], run["failed"], run["error"], run["missed"]), (2, 0, "", []))

    def test_a_new_run_starts_its_list_afresh(self):
        self._press("test_email", [self._item("BTF1", 2, reached=0)])
        self.assertEqual(
            [m["who"] for m in run_state("test_email")["run"]["missed"]], ["(BTF1) Person 0", "(BTF1) Person 1"],
        )
        self._press("test_email", [self._item("BTF1", 2)])
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

    def test_a_send_pressed_while_another_is_going_waits_its_turn(self):
        # Another email is sending.
        EmailSendRun.objects.create(key="other_email", held_until=timezone.now() + timedelta(minutes=4))
        self._press("test_email", [self._item("BTF1", 2)])
        state = run_state("test_email")
        self.assertEqual((state["sending"], state["queued"], state["run"]), (False, 1, None))
        self.assertEqual(state["ahead"], ["other_email"])
        self.assertEqual(self.sent, [])
        # Once that finishes, the page's next check starts it.
        EmailSendRun.objects.filter(key="other_email").update(held_until=None, finished_at=timezone.now())
        state = run_state("test_email")
        self.assertEqual((state["queued"], state["run"]["emailed"]), (0, 2))

    def test_queued_sends_go_in_the_order_pressed_a_few_seconds_apart(self):
        # The queue is busy sending: these wait, the same email twice too.
        send_guard._take(QUEUE_KEY)
        self._press("test_a", [self._item("A1", 1)])
        self._press("test_b", [self._item("B1", 1)])
        self._press("test_a", [self._item("A2", 1)])
        self.assertEqual(self.sent, [])
        self.assertEqual(QueuedEmailSend.objects.filter(key="test_a").count(), 2)
        # The page names what's ahead of each email's first send.
        self.assertEqual((run_state("test_a")["ahead"], run_state("test_b")["ahead"]), ([], ["test_a"]))
        send_guard._let_go()
        with override_settings(BULK_EMAIL_QUEUE_GAP_SECONDS=5), \
                mock.patch("apps.management.services.send_guard.time.sleep") as sleep:
            send_guard._kick()
        self.assertEqual([team for team, _ in self.sent], ["A1", "B1", "A2"])
        # A few seconds before each one after the first.
        self.assertEqual(sleep.call_count, 2)
        for call in sleep.call_args_list:
            self.assertAlmostEqual(call.args[0], 5, delta=1)
        self.assertFalse(QueuedEmailSend.objects.exists())

    def test_who_it_emails_is_worked_out_when_its_turn_comes(self):
        send_guard._take(QUEUE_KEY)
        builder = mock.Mock(return_value=[self._item("BTF1", 1)])
        send_guard.BUILDERS["test_email"] = builder
        send_guard.queue_send("test_email", self.actor, {"which": "missed"})
        builder.assert_not_called()
        send_guard._let_go()
        run_state("test_email")
        builder.assert_called_once_with(self.actor, {"which": "missed"})

    def test_a_send_that_cannot_be_got_ready_does_not_hold_up_the_rest(self):
        send_guard._take(QUEUE_KEY)
        send_guard.BUILDERS["test_bad"] = mock.Mock(side_effect=RuntimeError("broken"))
        send_guard.queue_send("test_bad", self.actor)
        self._press("test_email", [self._item("BTF1", 1)])
        send_guard._let_go()
        with self.assertLogs("apps.management.services.send_guard", level="ERROR"):
            send_guard._kick()
        self.assertEqual(run_state("test_bad")["run"]["error"], send_guard.NOT_READY)
        self.assertEqual(run_state("test_email")["run"]["emailed"], 1)
