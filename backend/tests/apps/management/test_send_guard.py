"""The bulk emails' runner: sends wait their turn in one queue, every item
of a run is sent, shared across its workers, those that missed someone tried
once more at the end, and the run's progress, and who it missed, kept for
the page."""
import threading
from datetime import timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
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

    def test_a_send_switched_off_while_queued_emails_nobody(self):
        from apps.services.models import SystemEmailTemplate

        work = [self._item("BTF1", 2)]
        self.works["results_team"] = [work]
        send_guard.BUILDERS["results_team"] = lambda actor, opts: self.works["results_team"].pop(0)
        QueuedEmailSend.objects.create(key="results_team", options={}, queued_by=self.actor)
        SystemEmailTemplate.objects.create(key="results_team", is_enabled=False)
        send_guard._kick()

        self.assertEqual(self.sent, [])
        run = run_state("results_team")["run"]
        self.assertEqual((run["due"], run["emailed"], run["failed"], run["missed"]), (0, 0, 0, []))
        self.assertIn("was switched off on System Emails", run["error"])
        self.assertFalse(QueuedEmailSend.objects.exists())

    def test_a_send_switched_off_part_way_stops_without_missing_anyone(self):
        from apps.services.models import SystemEmailTemplate

        first = self._item("BTF1", 2)

        def send_then_switch_off(connection, cache):
            # The email is switched off once the first team has it.
            SystemEmailTemplate.objects.create(key="results_team", is_enabled=False)
            return first.send(connection, cache)

        work = [Work(first.people, send_then_switch_off), self._item("BTF2", 3)]
        self._press("results_team", work)

        self.assertEqual([team for team, _ in self.sent], ["BTF1"])
        run = run_state("results_team")["run"]
        # The second team isn't emailed or counted as missed, so Send emails it later.
        self.assertEqual((run["due"], run["emailed"], run["failed"], run["missed"]), (5, 2, 0, []))
        self.assertIn("was switched off on System Emails", run["error"])

    def test_a_finished_run_keeps_who_it_reached_and_who_it_missed(self):
        from apps.services.models import EmailDeliveryRecipient

        addresses = ["amy@example.com", "bo@example.com", "cy@example.com"]
        labels = [f"{address} (BTF1)" for address in addresses]

        def send(connection, cache):
            # Bo's address is refused on both tries.
            return [{"who": labels[1], "reason": "address refused"}]

        self._press("test_email", [Work(labels, send, addresses)])

        rows = {
            row.email: (row.status, row.reason)
            for row in EmailDeliveryRecipient.objects.filter(metric__email_type="test_email")
        }
        self.assertEqual(rows, {
            "amy@example.com": ("delivered", ""),
            "bo@example.com": ("failed", "address refused"),
            "cy@example.com": ("delivered", ""),
        })

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

    def test_an_older_runs_entry_gets_the_address_from_the_team(self):
        from apps.groups.models import GroupMembership, Groups

        team = Groups.objects.create(group_name="BTF2")
        amy = User.objects.create_user(email="amy@example.com", first_name="Amy", last_name="Chen", password="pw12345!")
        GroupMembership.objects.create(group=team, user=amy, membership_role="student")
        EmailSendRun.objects.create(
            key="test_email", started_at="2026-10-01T00:00:00Z", due=2, emailed=0, failed=1,
            missed=[{"who": "(BTF2) Amy Chen", "reason": "address refused"}, {"who": "(BTF2) Gone", "reason": ""}],
        )
        # Someone no longer found keeps the name only.
        self.assertEqual([m["who"] for m in run_state("test_email")["run"]["missed"]], [
            "amy@example.com (BTF2, Amy Chen)", "(BTF2) Gone",
        ])

    def test_items_are_shared_across_workers_each_with_its_own_connection(self):
        work = [self._item(f"BTF{n}", 1) for n in range(7)]
        send_guard._take("test_email", due=7)
        send_guard._run("test_email", work, workers=3, threaded=False)
        self.assertEqual(len(self.sent), 7)
        # Three workers: seven items over three connections.
        self.assertEqual(len({id(connection) for _, connection in self.sent}), 3)
        self.assertEqual(EmailSendRun.objects.get(key="test_email").emailed, 7)

    # -- connections that drop out when the mail server pushes back --------------

    def _busy_on(self, team, times=1):
        """A team whose email the server pushes back on, the first ``times``
        tries; it goes after that."""
        tries = []

        def send(connection, cache):
            tries.append(1)
            self.sent.append((team, connection))
            if len(tries) <= times:
                return [{"who": f"({team}) Person 0", "reason": "mail server busy"}]
            return []
        return Work([f"({team}) Person 0"], send)

    @override_settings(BULK_EMAIL_WORKERS=3, BULK_EMAIL_MIN_WORKERS=2, BULK_EMAIL_RETRY_SECONDS=0)
    def test_pushed_back_one_connection_drops_out_at_once_and_its_email_still_goes(self):
        work = [self._item("BTF1", 1), self._item("BTF2", 1), self._busy_on("BTF3"),
                *[self._item(f"BTF{n}", 1) for n in range(4, 10)]]
        send_guard._take("test_email", due=9, started_at=timezone.now())

        with self.assertLogs("apps.management.services.send_guard", level="WARNING") as logs:
            send_guard._run("test_email", work, workers=3, threaded=False)

        self.assertIn("sending over 2 connections", " ".join(logs.output))
        # The one that pushed back sent nothing more; the other two took the rest.
        dropped = next(connection for team, connection in self.sent if team == "BTF3")
        self.assertEqual([team for team, connection in self.sent if connection is dropped], ["BTF3"])
        run = EmailSendRun.objects.get(key="test_email")
        self.assertEqual((run.emailed, run.failed, run.missed, run.connections), (9, 0, [], 2))
        self.assertTrue(run_state("test_email")["run"]["limited"])

    @override_settings(BULK_EMAIL_WORKERS=3, BULK_EMAIL_MIN_WORKERS=2, BULK_EMAIL_FEWER_MINUTES=60)
    def test_after_pushing_back_the_mailboxs_next_runs_start_with_fewer_for_a_while(self):
        self.assertEqual(send_guard.connections_for("test_email"), 3)
        send_guard._take("test_email", due=1)
        with self.assertLogs("apps.management.services.send_guard", level="WARNING"):
            send_guard._run("test_email", [self._busy_on("BTF1"), self._item("BTF2", 1)], workers=3, threaded=False)

        self.assertEqual(send_guard.connections_for("test_email"), 2)
        EmailSendRun.objects.filter(key=send_guard.queue_key(send_guard.lane("test_email"))).update(
            fewer_connections_until=timezone.now() - timedelta(minutes=1),
        )
        self.assertEqual(send_guard.connections_for("test_email"), 3)

    @override_settings(BULK_EMAIL_WORKERS=3, BULK_EMAIL_MIN_WORKERS=2, BULK_EMAIL_RETRY_SECONDS=0)
    def test_emails_starting_to_fail_drop_a_connection_but_a_refused_address_doesnt(self):
        def failing(team, reason):
            def send(connection, cache):
                self.sent.append((team, connection))
                return [{"who": f"({team}) Person 0", "reason": reason}]
            return Work([f"({team}) Person 0"], send)

        send_guard._take("test_email", due=4, started_at=timezone.now())
        send_guard._run("test_email", [failing("BTF1", "address refused"), *[self._item(f"BTF{n}", 1) for n in range(2, 5)]],
                        workers=3, threaded=False)
        self.assertEqual(EmailSendRun.objects.get(key="test_email").connections, 3)

        send_guard._take("test_email", due=4, started_at=timezone.now())
        with self.assertLogs("apps.management.services.send_guard", level="WARNING"):
            send_guard._run(
                "test_email",
                [failing("BTF5", "lost the mail server connection"), *[self._item(f"BTF{n}", 1) for n in range(6, 9)]],
                workers=3, threaded=False,
            )
        self.assertEqual(EmailSendRun.objects.get(key="test_email").connections, 2)

    @override_settings(BULK_EMAIL_WORKERS=2, BULK_EMAIL_MIN_WORKERS=2, BULK_EMAIL_RETRY_SECONDS=0)
    def test_never_fewer_than_the_minimum(self):
        send_guard._take("test_email", due=4, started_at=timezone.now())
        send_guard._run("test_email", [self._busy_on("BTF1"), *[self._item(f"BTF{n}", 1) for n in range(2, 5)]],
                        workers=2, threaded=False)

        run = EmailSendRun.objects.get(key="test_email")
        self.assertEqual((run.emailed, run.connections), (4, 2))
        self.assertFalse(run_state("test_email")["run"]["limited"])

    @override_settings(BULK_EMAIL_WORKERS=3, BULK_EMAIL_MIN_WORKERS=2)
    def test_a_connection_the_server_refuses_drops_out_before_sending(self):
        import smtplib

        opens = []

        def third_refused(connection):
            opens.append(1)
            if len(opens) == 3:
                raise smtplib.SMTPConnectError(421, b"Too many connections")

        send_guard._take("test_email", due=6)
        with mock.patch("django.core.mail.backends.locmem.EmailBackend.open", autospec=True,
                        side_effect=third_refused),                 self.assertLogs("apps.management.services.send_guard", level="WARNING"):
            send_guard._run("test_email", [self._item(f"BTF{n}", 1) for n in range(6)], workers=3, threaded=False)

        self.assertEqual(len({id(connection) for _, connection in self.sent}), 2)
        run = EmailSendRun.objects.get(key="test_email")
        self.assertEqual((run.emailed, run.connections), (6, 2))

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


# What the stand-in jobs below were given, in the order they ran.
JOB_RUNS: list = []


def _stand_in_job(actor, options):
    """A job that only notes it ran, and says what it sent."""
    JOB_RUNS.append(options["name"])
    return {"sent": options.get("sent", 0), "failed": options.get("failed", 0)}


@override_settings(EMAIL_BACKEND=LOCMEM)
class QueuedJobTests(TestCase):
    """Announcements and the scheduled emails queue as jobs: each runs its own
    send in its turn, in the queue of the mailbox its email goes from."""

    def setUp(self):
        self.actor = User.objects.create_user(email="admin@example.com", password="pw12345!")
        JOB_RUNS.clear()
        stand_in = "tests.apps.management.test_send_guard:_stand_in_job"
        # The RSVP reminders go from info@, the digest from connect@.
        jobs = mock.patch.dict(send_guard.JOBS, {"rsvp_reminder": stand_in, "unread_messages": stand_in})
        jobs.start()
        self.addCleanup(jobs.stop)

    def test_a_job_runs_in_its_turn_and_its_run_is_noted(self):
        send_guard.queue_job("rsvp_reminder", self.actor, {"name": "rsvp", "sent": 3, "failed": 1})

        self.assertEqual(JOB_RUNS, ["rsvp"])
        run = EmailSendRun.objects.get(key="rsvp_reminder")
        self.assertEqual((run.emailed, run.failed, run.error, run.held_until), (3, 1, "", None))
        self.assertEqual(run.started_by, self.actor)
        self.assertFalse(QueuedEmailSend.objects.exists())

    def test_a_job_waits_while_its_mailbox_sends_and_comes_once(self):
        send_guard._take(QUEUE_KEY)
        send_guard.queue_job("rsvp_reminder", options={"name": "rsvp"})
        # The same one again while it still waits: not queued twice.
        send_guard.queue_job("rsvp_reminder", options={"name": "rsvp"})
        self.assertEqual(JOB_RUNS, [])
        self.assertEqual(QueuedEmailSend.objects.filter(key="rsvp_reminder").count(), 1)

        send_guard._let_go()
        send_guard._kick()
        self.assertEqual(JOB_RUNS, ["rsvp"])

    def test_a_job_waits_behind_a_bulk_email_from_the_same_mailbox(self):
        # Results going from info@: the RSVP reminders wait, as Management's emails do.
        EmailSendRun.objects.create(key="results_team", held_until=timezone.now() + timedelta(minutes=5))
        send_guard.queue_job("rsvp_reminder", options={"name": "rsvp"})
        self.assertEqual(JOB_RUNS, [])
        self.assertEqual(run_state("results_team")["queued"], 0)

        EmailSendRun.objects.filter(key="results_team").update(held_until=None, finished_at=timezone.now())
        send_guard._kick()
        self.assertEqual(JOB_RUNS, ["rsvp"])

    def test_another_mailbox_does_not_wait(self):
        # info@'s queue is busy: the digest, from connect@, goes anyway.
        send_guard._take(QUEUE_KEY)
        send_guard.queue_job("rsvp_reminder", options={"name": "rsvp"})
        send_guard.queue_job("unread_messages", options={"name": "digest"})

        self.assertEqual(JOB_RUNS, ["digest"])
        self.assertEqual(list(QueuedEmailSend.objects.values_list("key", flat=True)), ["rsvp_reminder"])
        self.assertEqual(send_guard.queue_key("connect"), f"{QUEUE_KEY}:connect")


class KeepHeldTests(SimpleTestCase):
    def test_a_jobs_hold_keeper_closes_its_connection_and_ends_cleanly(self):
        # It runs on its own thread while a job sends; it once failed on its
        # way out (a name it doesn't have), logging an error after every job.
        stop = threading.Event()
        stop.set()
        with mock.patch.object(send_guard, "db_connection") as connection:
            send_guard._keep_held("announcement", stop)
        connection.close.assert_called_once()
