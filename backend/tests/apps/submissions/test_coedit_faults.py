"""Fault and race tests for co-editing: refused requests, failed saves, and edits landing at once."""
import os
import threading
import unittest
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.utils import timezone
from pycrdt import Doc, Text

from apps.submissions import coedit
from apps.submissions.autosubmit import auto_submit_due
from apps.submissions.models import Submission

from .seed_data import CONFIRMED_CHECKLIST
from .test_coedit import Client, CoeditTestCase, _b64, _consumer
from .test_poster_checklist import _poster


class Broken(Exception):
    """Stands in for Redis being unreachable."""


class StoreFaultTests(CoeditTestCase):
    def test_a_failure_while_applying_an_edit_tells_the_page_to_retry(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        update = Client(self.room).type(self.field, 5, "!")

        with patch.object(coedit.store(), "append", side_effect=Broken):
            async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(update)})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})
        consumer.channel_layer.group_send.assert_not_awaited()
        self.assertEqual(Client(self.room).text(self.field), "Draft")

    def test_the_retried_edit_is_kept_once_the_store_is_back(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        page = Client(self.room)
        update = page.type(self.field, 5, "!")
        with patch.object(coedit.store(), "append", side_effect=Broken):
            async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(update)})

        # The page offers its whole copy again, as it does after a refusal.
        async_to_sync(consumer.receive_json)(
            {"type": "doc-sync", "vector": _b64(page.doc.get_state()), "update": _b64(page.doc.get_update())}
        )

        reply = consumer.send_json.await_args.args[0]
        self.assertFalse(reply["full"])
        self.assertEqual(Client(self.room).text(self.field), "Draft!")

    def test_a_failure_while_syncing_tells_the_page_to_retry(self):
        self._entry_with()
        consumer = _consumer(self.student, self.room)

        with patch.object(coedit.store(), "read", side_effect=Broken):
            async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": "", "update": ""})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})

    def test_a_failed_save_is_logged_and_the_next_save_catches_up(self):
        self._entry_with("Draft")
        coedit.apply(self.student, self.room, Client(self.room).type(self.field, 5, " more"))
        consumer = _consumer(self.student, self.room)

        with patch.object(coedit.store(), "read", side_effect=Broken), self.assertLogs("apps.live.consumers", "ERROR"):
            async_to_sync(consumer._save_document)()
        self.assertEqual(self._entry().answers[self.key], "Draft")

        coedit.save(self.room)
        self.assertEqual(self._entry().answers[self.key], "Draft more")

    def test_flush_reports_a_failure_instead_of_raising(self):
        self._entry_with()
        Client(self.room)

        with patch.object(coedit.store(), "read", side_effect=Broken), self.assertLogs("apps.submissions.coedit", "ERROR"):
            self.assertFalse(coedit.flush(self.room))

    def test_a_flush_request_answers_not_ok_when_saving_fails(self):
        self._entry_with()
        Client(self.room)
        consumer = _consumer(self.student, self.room)

        with patch.object(coedit.store(), "read", side_effect=Broken), self.assertLogs("apps.submissions.coedit", "ERROR"):
            async_to_sync(consumer.receive_json)({"type": "doc-flush", "id": 3})

        consumer.send_json.assert_awaited_with({"type": "doc-flushed", "id": 3, "ok": False})

    def _ready_to_submit(self):
        self._upload(self.student, _poster())
        self._entry_with("Saved draft")
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")

    def test_submit_still_goes_in_with_the_saved_answers_when_the_document_is_unreachable(self):
        self._ready_to_submit()
        Client(self.room)

        with patch.object(coedit.store(), "read", side_effect=Broken), self.assertLogs("apps.submissions.coedit", "ERROR"):
            response = self._client(self.student).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._entry().submitted_answers[self.key], "Saved draft")

    def test_auto_submit_still_runs_when_the_document_is_unreachable(self):
        self._ready_to_submit()
        Client(self.room)
        Submission.objects.filter(group=self.group).update(cohort=2026)
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()

        with (
            patch.object(coedit.store(), "read", side_effect=Broken),
            patch("apps.submissions.autosubmit.current_cohort", return_value=2026),
            self.assertLogs("apps.submissions.coedit", "ERROR"),
        ):
            result = auto_submit_due()

        self.assertEqual(result["submitted"], ["BTF7"])


class RejectedRequestTests(CoeditTestCase):
    def test_edits_from_before_a_rebuild_cannot_corrupt_the_rebuilt_document(self):
        self._entry_with("Draft")
        stale = Client(self.room)
        Submission.objects.filter(group=self.group).update(answers={self.key: "Changed elsewhere."})
        with patch.object(coedit, "broadcast_reset"), self.captureOnCommitCallbacks(execute=True):
            coedit.save(self.room)

        coedit.apply(self.student, self.room, stale.replace(self.field, "Stale overwrite"))

        self.assertNotIn("Stale overwrite", Client(self.room).text(self.field).replace("Changed elsewhere.", ""))
        self.assertIn("Changed elsewhere.", Client(self.room).text(self.field))

    def test_a_refused_edit_leaves_the_document_and_the_entry_untouched(self):
        self._entry_with("Draft")
        page = Client(self.room)

        self.assertFalse(coedit.apply(self.student, self.room, page.type(self.field, 0, "x" * (coedit.MAX_FIELD_CHARS + 1))))
        coedit.save(self.room)

        self.assertEqual(Client(self.room).text(self.field), "Draft")
        self.assertEqual(self._entry().answers[self.key], "Draft")

    def test_the_deadline_passing_mid_typing_refuses_the_next_edit_only(self):
        self._entry_with("Draft")
        page = Client(self.room)
        self.assertTrue(coedit.apply(self.student, self.room, page.type(self.field, 5, " one")))
        self.deadline.closes_at = timezone.now() - timedelta(minutes=1)
        self.deadline.save()

        self.assertFalse(coedit.apply(self.student, self.room, page.type(self.field, 9, " two")))
        coedit.save(self.room)

        self.assertEqual(self._entry().answers[self.key], "Draft one")


class RaceTests(CoeditTestCase):
    """Edits and saves landing at once. The checks that read the database run on the test's thread."""

    def test_many_teammates_typing_at_the_same_instant_all_keep_their_words(self):
        self._entry_with("")
        pages = [Client(self.room) for _ in range(10)]
        updates = [page.type(self.field, 0, f"[{i}]") for i, page in enumerate(pages)]
        barrier = threading.Barrier(len(updates))
        fields = coedit._fields()

        def send(update):
            barrier.wait()
            coedit.apply(self.student, self.room, update)

        with patch.object(coedit, "can_edit", return_value=True), patch.object(coedit, "_fields", return_value=fields):
            threads = [threading.Thread(target=send, args=(update,)) for update in updates]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]

        text = Client(self.room).text(self.field)
        self.assertEqual(sorted(text.replace("][", "]|[").split("|")), sorted(f"[{i}]" for i in range(10)))

    def test_an_edit_landing_during_a_save_is_never_lost(self):
        self._entry_with("Draft")
        page = Client(self.room)
        real_load = coedit._load
        later = page.type(self.field, 5, " late")

        def load_then_edit(room):
            loaded = real_load(room)
            # A teammate's edit lands after the save has read the document.
            coedit.store().append(room, later)
            return loaded

        with patch.object(coedit, "_load", side_effect=load_then_edit):
            coedit.save(self.room)
        self.assertEqual(self._entry().answers[self.key], "Draft")

        coedit.flush(self.room)
        self.assertEqual(self._entry().answers[self.key], "Draft late")

    def test_submit_takes_typing_that_arrives_just_before_it(self):
        self._upload(self.student, _poster())
        self._entry_with("Draft")
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")
        page = Client(self.room)
        # Typed, not yet saved by any pause: only Submit's own save writes it.
        coedit.apply(self.student, self.room, page.type(self.field, 5, " final words"))

        self._client(self.student).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(self._entry().submitted_answers[self.key], "Draft final words")

    def test_compaction_never_drops_an_update_it_did_not_merge(self):
        store = coedit.store()
        store.create(self.room, coedit._build({self.field: ""}), "digest")
        page = Doc()
        page.apply_update(store.read(self.room)[0])
        text = page.get(self.field, type=Text)

        def edit(value):
            before = page.get_state()
            text.insert(0, value)
            store.append(self.room, page.get_update(before))

        def merged_base(base, updates):
            return coedit._doc_from(base, updates).get_update()

        edit("a")
        base, snapshot, _ = store.read(self.room)
        edit("b")  # lands after the snapshot was read
        store.compact(self.room, snapshot, merged_base(base, snapshot))
        # A second worker compacting from the same, now stale, snapshot changes nothing.
        store.compact(self.room, snapshot, merged_base(base, snapshot))

        self.assertEqual(Client(self.room).text(self.field), "ba")

    def test_compaction_with_edits_pouring_in_keeps_every_edit(self):
        self._entry_with("")
        fields = coedit._fields()
        pages = [Client(self.room) for _ in range(4)]

        def type_many(index, page):
            for n in range(80):
                coedit.apply(self.student, self.room, page.type(self.field, 0, f"{index}"))

        with patch.object(coedit, "can_edit", return_value=True), patch.object(coedit, "_fields", return_value=fields):
            threads = [threading.Thread(target=type_many, args=(i, page)) for i, page in enumerate(pages)]
            [thread.start() for thread in threads]
            [thread.join() for thread in threads]

        text = Client(self.room).text(self.field)
        self.assertEqual(sorted(text), sorted("0123" * 80))


REDIS_URL = os.environ.get("COEDIT_TEST_REDIS_URL", "")


@unittest.skipUnless(REDIS_URL, "set COEDIT_TEST_REDIS_URL to a throwaway Redis to run these")
class RedisRaceTests(unittest.TestCase):
    """The same races against a real Redis, as several server workers would meet them."""

    room = 424242

    def setUp(self):
        self.stores = [coedit._RedisStore(REDIS_URL) for _ in range(8)]
        self.stores[0]._redis.delete(*self.stores[0]._keys(self.room))
        self.addCleanup(lambda: self.stores[0]._redis.delete(*self.stores[0]._keys(self.room)))

    def _text(self):
        base, updates, _ = self.stores[0].read(self.room)
        doc = Doc()
        doc.apply_update(base)
        for update in updates:
            doc.apply_update(update)
        return str(doc.get("answer:q1", type=Text))

    def test_workers_building_the_document_at_once_store_it_once(self):
        barrier = threading.Barrier(len(self.stores))

        def build(store):
            barrier.wait()
            store.create(self.room, coedit._build({"answer:q1": "Saved."}), "digest")

        threads = [threading.Thread(target=build, args=(s,)) for s in self.stores]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

        self.assertEqual(self._text(), "Saved.")

    def test_workers_appending_and_compacting_at_once_keep_every_edit(self):
        self.stores[0].create(self.room, coedit._build({"answer:q1": ""}), "digest")
        base, _, _ = self.stores[0].read(self.room)

        def type_many(index, store):
            page = Doc()
            page.apply_update(base)
            text = page.get("answer:q1", type=Text)
            for n in range(60):
                before = page.get_state()
                text.insert(0, str(index))
                store.append(self.room, page.get_update(before))
                if n % 20 == 19:
                    # Each worker compacts what it has read, as apply() does past the threshold.
                    current, updates, _ = store.read(self.room)
                    merged = Doc()
                    merged.apply_update(current)
                    for update in updates:
                        merged.apply_update(update)
                    store.compact(self.room, updates, merged.get_update())

        threads = [threading.Thread(target=type_many, args=(i, s)) for i, s in enumerate(self.stores)]
        [thread.start() for thread in threads]
        [thread.join() for thread in threads]

        self.assertEqual(sorted(self._text()), sorted("01234567" * 60))
