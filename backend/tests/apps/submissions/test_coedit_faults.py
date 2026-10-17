"""Fault and race tests for co-editing: refused requests, failed saves, and edits landing at once."""
import base64
import os
import socket
import threading
import time
import unittest
from datetime import timedelta
from unittest.mock import patch

from asgiref.sync import async_to_sync
from django.utils import timezone
from pycrdt import Doc, Map, Text

from apps.live.shared_documents import _save_after_pause
from apps.submissions import coedit
from apps.submissions.autosubmit import auto_submit_due
from apps.submissions.models import Submission, SubmissionQuestion

from .seed_data import CONFIRMED_CHECKLIST
from .test_coedit import Client, CoeditTestCase, _b64, _consumer, unreachable
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

        with unreachable(Broken):
            async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": "", "update": ""})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})

    def test_a_failed_save_is_logged_and_the_next_save_catches_up(self):
        self._entry_with("Draft")
        coedit.apply(self.student, self.room, Client(self.room).type(self.field, 5, " more"))
        consumer = _consumer(self.student, self.room)

        with (
            patch("apps.live.shared_documents.DOC_SAVE_DELAY", 0),
            unreachable(Broken),
            self.assertLogs("apps.live.shared_documents", "ERROR"),
        ):
            async_to_sync(_save_after_pause)(coedit, self.room, consumer.room)
        self.assertEqual(self._entry().answers[self.key], "Draft")

        coedit.save(self.room)
        self.assertEqual(self._entry().answers[self.key], "Draft more")

    def test_flush_reports_a_failure_instead_of_raising(self):
        self._entry_with()
        Client(self.room)

        with unreachable(Broken), self.assertLogs("apps.submissions.coedit", "ERROR"):
            self.assertFalse(coedit.flush(self.room))

    def test_a_flush_request_answers_not_ok_when_saving_fails(self):
        self._entry_with()
        Client(self.room)
        consumer = _consumer(self.student, self.room)

        with unreachable(Broken), self.assertLogs("apps.submissions.coedit", "ERROR"):
            async_to_sync(consumer.receive_json)({"type": "doc-flush", "id": 3})

        consumer.send_json.assert_awaited_with({"type": "doc-flushed", "id": 3, "ok": False})

    def _ready_to_submit(self):
        self._upload(self.student, _poster())
        self._entry_with("Saved draft")
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")

    def test_submit_still_goes_in_with_the_saved_answers_when_the_document_is_unreachable(self):
        self._ready_to_submit()
        Client(self.room)

        with unreachable(Broken), self.assertLogs("apps.submissions.coedit", "ERROR"):
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
            unreachable(Broken),
            patch("apps.submissions.autosubmit.current_cohort", return_value=2026),
            self.assertLogs("apps.submissions.coedit", "ERROR"),
        ):
            result = auto_submit_due()

        self.assertEqual(result["submitted"], ["BTF7"])


class UnresponsiveRedisTests(unittest.TestCase):
    def test_a_redis_that_stops_answering_fails_the_call_instead_of_hanging(self):
        # Accepts the connection but never replies, as a stalled Redis does.
        silent = socket.socket()
        silent.bind(("127.0.0.1", 0))
        silent.listen()
        self.addCleanup(silent.close)
        with patch.object(coedit, "REDIS_TIMEOUT_SECONDS", 0.2):
            store = coedit._RedisStore(f"redis://127.0.0.1:{silent.getsockname()[1]}/0")

        started = time.monotonic()
        with self.assertRaises(Exception):
            store.read(1)

        self.assertLess(time.monotonic() - started, 2)


class LostDocumentTests(CoeditTestCase):
    """Redis restarted empty, evicted the room, or let it expire, while a page still held its copy."""

    def _page_after_the_document_was_lost(self):
        self._entry_with("Draft")
        page = Client(self.room)
        coedit.store().clear()
        page.type(self.field, 5, " more")
        return page

    def test_a_page_resending_its_copy_cannot_double_the_answer(self):
        page = self._page_after_the_document_was_lost()

        accepted = coedit.apply(self.student, self.room, page.doc.get_update(), generation=page.generation())
        coedit.save(self.room)

        self.assertFalse(accepted)
        self.assertEqual(Client(self.room).text(self.field), "Draft")
        self.assertEqual(self._entry().answers[self.key], "Draft")

    def test_each_rebuild_gets_a_new_label(self):
        page = self._page_after_the_document_was_lost()

        self.assertNotEqual(Client(self.room).generation(), page.generation())

    def test_a_page_of_an_earlier_build_is_sent_the_whole_current_copy(self):
        page = self._page_after_the_document_was_lost()
        consumer = _consumer(self.student, self.room)

        async_to_sync(consumer.receive_json)({
            "type": "doc-sync", "vector": _b64(page.doc.get_state()), "update": _b64(page.doc.get_update()),
            "generation": page.generation(),
        })

        reply = consumer.send_json.await_args.args[0]
        self.assertTrue(reply["full"])
        fresh = Doc()
        fresh.apply_update(base64.b64decode(reply["update"]))
        self.assertEqual(str(fresh.get(self.field, type=Text)), "Draft")
        self.assertEqual(Client(self.room).text(self.field), "Draft")

    def test_an_update_from_an_earlier_build_is_refused(self):
        page = self._page_after_the_document_was_lost()
        consumer = _consumer(self.student, self.room)
        Client(self.room)

        async_to_sync(consumer.receive_json)({
            "type": "doc-update", "update": _b64(page.type(self.field, 10, "!")), "generation": page.generation(),
        })

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})
        self.assertEqual(Client(self.room).text(self.field), "Draft")

    def test_a_page_of_the_current_build_syncs_as_usual(self):
        self._entry_with("Draft")
        page = Client(self.room)
        consumer = _consumer(self.student, self.room)
        local = page.type(self.field, 5, "!")

        async_to_sync(consumer.receive_json)({
            "type": "doc-sync", "vector": _b64(page.doc.get_state()), "update": _b64(local), "generation": page.generation(),
        })

        self.assertFalse(consumer.send_json.await_args.args[0]["full"])
        self.assertEqual(Client(self.room).text(self.field), "Draft!")

    def test_an_edit_cannot_change_the_label(self):
        self._entry_with("Draft")
        page = Client(self.room)
        before = page.doc.get_state()
        page.doc.get(coedit.GENERATION_ROOT, type=Map)[coedit.GENERATION_KEY] = "forged"

        self.assertFalse(coedit.apply(self.student, self.room, page.doc.get_update(before)))
        self.assertNotEqual(Client(self.room).generation(), "forged")

    def test_a_malformed_label_is_refused(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)

        async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": "", "update": "", "generation": ["x"]})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})


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

    def test_typing_between_two_overlapping_saves_is_kept(self):
        self._entry_with("Draft")
        page = Client(self.room)
        coedit.apply(self.student, self.room, page.type(self.field, 5, " one"))
        real_atomic, raced = coedit.transaction.atomic, []

        def another_save_first(*args, **kwargs):
            if not raced:
                raced.append(True)
                # Another worker's save commits, then a teammate types, while this save waits for the lock.
                coedit.save(self.room)
                coedit.apply(self.student, self.room, page.type(self.field, 9, " two"))
            return real_atomic(*args, **kwargs)

        with patch.object(coedit.transaction, "atomic", side_effect=another_save_first), patch.object(coedit, "broadcast_reset") as reset:
            self.assertTrue(coedit.save(self.room))

        reset.assert_not_called()
        self.assertEqual(Client(self.room).text(self.field), "Draft one two")
        self.assertEqual(self._entry().answers[self.key], "Draft one two")



def _claims_in_turn(test, store, room):
    """The first edit claims the room's save, later ones do not, and after a release the next one does."""
    claims = [store.append(room, b"\x00\x00", 10)[1] for _ in range(3)]
    store.release_save(room)
    claims.append(store.append(room, b"\x00\x00", 10)[1])
    claims.append(store.append(room, b"\x00\x00")[1])
    test.assertEqual(claims, [True, False, False, True, False])


class WorkerCopyTests(CoeditTestCase):
    """Each worker keeps its own copy of a room's document and reads on only from where it stopped."""

    def test_an_edit_claims_the_rooms_save_in_the_same_trip(self):
        self._entry_with("")
        Client(self.room)
        _claims_in_turn(self, coedit.store(), self.room)

    def test_an_edit_asks_the_database_nothing(self):
        self._entry_with("")
        page = Client(self.room)
        coedit.apply(self.student, self.room, page.type(self.field, 0, "a"), checked=True)

        with self.assertNumQueries(0):
            coedit.apply(self.student, self.room, page.type(self.field, 1, "b"), checked=True)

    def test_a_new_question_can_be_typed_into_at_once(self):
        self._entry_with("")
        page = Client(self.room)
        coedit.apply(self.student, self.room, page.type(self.field, 0, "a"), checked=True)
        question = SubmissionQuestion.objects.create(key="late_question", prompt="Added late?", order=99, is_active=True)

        typed = page.type(coedit.answer_field(question.key), 0, "New.")

        self.assertTrue(coedit.apply(self.student, self.room, typed, checked=True))

    def test_a_question_retired_mid_round_leaves_the_other_answers_editable(self):
        self._entry_with("Draft")
        page = Client(self.room)
        SubmissionQuestion.objects.filter(key=self.questions[1].key).update(is_active=False)
        coedit.forget_fields()

        self.assertTrue(coedit.apply(self.student, self.room, page.type(self.field, 5, "!"), checked=True))
        self.assertEqual(Client(self.room).text(self.field), "Draft!")

    def test_an_edit_still_cannot_add_a_field_of_its_own(self):
        self._entry_with("Draft")
        page = Client(self.room)

        self.assertFalse(coedit.apply(self.student, self.room, page.type("answer:made_up", 0, "x"), checked=True))

    def test_an_edit_reads_only_what_is_new(self):
        self._entry_with("")
        page = Client(self.room)

        with patch.object(coedit.store(), "snapshot", wraps=coedit.store().snapshot) as from_scratch:
            for i in range(5):
                coedit.apply(self.student, self.room, page.type(self.field, i, "x"))

        from_scratch.assert_not_called()
        self.assertEqual(Client(self.room).text(self.field), "xxxxx")

    def test_a_copy_takes_in_what_other_workers_added(self):
        self._entry_with("Draft")
        page = Client(self.room)
        coedit.apply(self.student, self.room, page.type(self.field, 5, " one"))

        # Another worker's edit reaches Redis without passing through this worker.
        coedit.store().append(self.room, page.type(self.field, 9, " two"))
        coedit.apply(self.student, self.room, page.type(self.field, 13, " three"))

        self.assertEqual(Client(self.room).text(self.field), "Draft one two three")
        coedit.save(self.room)
        self.assertEqual(self._entry().answers[self.key], "Draft one two three")

    def test_a_merge_by_another_worker_makes_copies_start_again_and_keeps_every_edit(self):
        self._entry_with("")
        page = Client(self.room)
        with patch.object(coedit, "COMPACT_AFTER", 3):
            for i in range(10):
                coedit.apply(self.student, self.room, page.type(self.field, i, str(i)))
                if i == 4:
                    # Another worker merges meanwhile, so this worker's place in the list no longer holds.
                    base, updates, _ = coedit.store().read(self.room)
                    coedit.store().compact(self.room, updates, coedit._doc_from(base, updates).get_update())

        self.assertEqual(Client(self.room).text(self.field), "0123456789")
        self.assertLess(len(coedit.store().read(self.room)[1]), 3)


REDIS_URL = os.environ.get("COEDIT_TEST_REDIS_URL", "")


@unittest.skipUnless(REDIS_URL, "set COEDIT_TEST_REDIS_URL to a throwaway Redis to run these")
class RedisRaceTests(unittest.TestCase):
    """The same races against a real Redis, as several server workers would meet them."""

    room = 424242

    def setUp(self):
        self.stores = [coedit._RedisStore(REDIS_URL) for _ in range(8)]
        keys = [*self.stores[0]._keys(self.room), self.stores[0]._epoch_key(self.room)]
        self.stores[0]._redis.delete(*keys)
        self.addCleanup(lambda: self.stores[0]._redis.delete(*keys))

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

    def test_an_edit_claims_the_rooms_save_in_the_same_trip(self):
        self.stores[0].create(self.room, coedit._build({"answer:q1": ""}), "digest")
        self.stores[0].release_save(self.room)
        self.addCleanup(lambda: self.stores[0].release_save(self.room))
        _claims_in_turn(self, self.stores[0], self.room)

    def test_reading_on_holds_only_until_the_base_is_rebuilt_or_merged(self):
        store = self.stores[0]
        store.create(self.room, coedit._build({"answer:q1": ""}), "digest")
        _, updates, _, epoch = store.snapshot(self.room)
        page = Doc()
        page.apply_update(store.read(self.room)[0])
        before = page.get_state()
        page.get("answer:q1", type=Text).insert(0, "a")
        store.append(self.room, page.get_update(before))

        self.assertEqual(len(store.read_since(self.room, epoch, len(updates))[1]), 1)
        base, merged, _ = store.read(self.room)
        store.compact(self.room, merged, coedit._doc_from(base, merged).get_update())
        self.assertIsNone(store.read_since(self.room, epoch, len(updates))[1])
        _, _, _, merged_epoch = store.snapshot(self.room)
        store.replace(self.room, coedit._build({"answer:q1": "b"}), "digest")
        self.assertIsNone(store.read_since(self.room, merged_epoch, 0)[1])

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
