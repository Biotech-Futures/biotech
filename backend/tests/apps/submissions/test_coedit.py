"""Tests for co-editing: the shared document behind a team's answers and title."""
import base64
from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import override_settings
from django.utils import timezone
from pycrdt import Doc, Map, Text

from apps.live import shared_documents
from apps.live.consumers import LiveRoomConsumer
from apps.submissions import coedit
from apps.submissions.autosubmit import auto_submit_due
from apps.submissions.models import Submission, SubmissionQuestion
from apps.users.models import AdminScope, User

from .seed_data import CONFIRMED_CHECKLIST
from .test_poster_checklist import ChecklistTestCase, _poster


class Client:
    """A page's copy of the shared document, synced the way the browser syncs."""

    def __init__(self, room: int):
        self.room = room
        self.doc = Doc()
        self.doc.apply_update(coedit.state_since(room, None)[0])

    def text(self, field: str) -> str:
        return str(self.doc.get(field, type=Text))

    def generation(self) -> str:
        return self.doc.get(coedit.GENERATION_ROOT, type=Map).get(coedit.GENERATION_KEY)

    def type(self, field: str, at: int, value: str) -> bytes:
        before = self.doc.get_state()
        self.doc.get(field, type=Text).insert(at, value)
        return self.doc.get_update(before)

    def replace(self, field: str, value: str) -> bytes:
        before = self.doc.get_state()
        text = self.doc.get(field, type=Text)
        with self.doc.transaction():
            del text[:]
            text.insert(0, value)
        return self.doc.get_update(before)


@contextmanager
def unreachable(error=None):
    """Every read of the shared documents fails, as when Redis cannot be reached."""
    error = error or ConnectionError
    store = coedit.store()
    with patch.object(store, "read", side_effect=error), patch.object(store, "snapshot", side_effect=error), patch.object(
        store, "read_since", side_effect=error
    ):
        yield


@override_settings(SUBMISSION_COEDITING_ENABLED=True)
class CoeditTestCase(ChecklistTestCase):
    def setUp(self):
        super().setUp()
        coedit.store().clear()
        self.addCleanup(coedit.store().clear)
        coedit._copies.clear()
        self.addCleanup(coedit._copies.clear)
        coedit.forget_fields()
        shared_documents._waiting_saves.clear()
        self.addCleanup(shared_documents._waiting_saves.clear)
        self.key = self.questions[0].key
        self.field = coedit.answer_field(self.key)
        self.admin = User.objects.create_user(email="admin@test.local", password="x", first_name="Ada")
        AdminScope.objects.create(user=self.admin)
        self.room = self.group.id

    def _entry_with(self, answer="Saved answer.", title="Saved title"):
        submission, _ = Submission.objects.get_or_create(group=self.group)
        submission.answers = {q.key: answer for q in self.questions}
        submission.project_title = title
        submission.save()
        return submission


class SharedDocumentTests(CoeditTestCase):
    def test_the_document_starts_from_the_saved_entry(self):
        self._entry_with()

        client = Client(self.room)

        self.assertEqual(client.text(self.field), "Saved answer.")
        self.assertEqual(client.text(coedit.TITLE_FIELD), "Saved title")

    def test_two_teammates_typing_in_one_answer_both_keep_their_words(self):
        self._entry_with("hello world")
        ada, ben = Client(self.room), Client(self.room)

        self.assertTrue(coedit.apply(self.student, self.room, ada.type(self.field, 5, ", big")))
        self.assertTrue(coedit.apply(self.student, self.room, ben.type(self.field, 11, "!")))

        self.assertEqual(Client(self.room).text(self.field), "hello, big world!")

    def test_the_same_update_twice_changes_nothing(self):
        self._entry_with("hello")
        client = Client(self.room)
        update = client.type(self.field, 5, "!")

        coedit.apply(self.student, self.room, update)
        coedit.apply(self.student, self.room, update)

        self.assertEqual(Client(self.room).text(self.field), "hello!")

    def test_admins_edit_privately_instead(self):
        self._entry_with()

        self.assertFalse(coedit.apply(self.admin, self.room, Client(self.room).type(self.field, 0, "x")))

    def test_nothing_is_accepted_after_the_deadline(self):
        self._entry_with()
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()

        self.assertFalse(coedit.apply(self.student, self.room, Client(self.room).type(self.field, 0, "x")))

    def test_nothing_is_accepted_on_a_submitted_entry(self):
        entry = self._entry_with()
        entry.snapshot(self.student)
        entry.save()

        self.assertFalse(coedit.apply(self.student, self.room, Client(self.room).type(self.field, 0, "x")))

    @override_settings(SUBMISSION_COEDITING_ENABLED=False)
    def test_nothing_is_accepted_while_switched_off(self):
        self.assertFalse(coedit.apply(self.student, self.room, b"\x00"))

    def test_a_malformed_update_is_refused(self):
        self._entry_with()

        self.assertFalse(coedit.apply(self.student, self.room, b"not an update"))

    def test_an_answer_past_the_size_cap_is_refused(self):
        self._entry_with("")
        client = Client(self.room)

        refused = coedit.apply(self.student, self.room, client.type(self.field, 0, "x" * (coedit.MAX_FIELD_CHARS + 1)))

        self.assertFalse(refused)
        self.assertEqual(Client(self.room).text(self.field), "")

    def test_an_unexpected_field_is_refused(self):
        self._entry_with()
        stray = Doc()
        stray["anything"] = Text("x")

        self.assertFalse(coedit.apply(self.student, self.room, stray.get_update()))

    def test_many_updates_are_merged_into_one_base_without_losing_text(self):
        self._entry_with("")
        client = Client(self.room)

        for i in range(coedit.COMPACT_AFTER + 5):
            coedit.apply(self.student, self.room, client.type(self.field, i, "a"))

        base, updates, _ = coedit.store().read(self.room)
        self.assertLess(len(updates), coedit.COMPACT_AFTER)
        self.assertEqual(Client(self.room).text(self.field), "a" * (coedit.COMPACT_AFTER + 5))


class SavingTests(CoeditTestCase):
    def test_the_server_saves_the_merged_text(self):
        self._entry_with("Draft")
        client = Client(self.room)
        coedit.apply(self.student, self.room, client.type(self.field, 5, " two"))
        coedit.apply(self.student, self.room, client.replace(coedit.TITLE_FIELD, "New title"))

        self.assertTrue(coedit.save(self.room))

        entry = self._entry()
        self.assertEqual(entry.answers[self.key], "Draft two")
        self.assertEqual(entry.project_title, "New title")

    def _limit_first_question(self, words=3):
        question = self.questions[0]
        question.max_words = words
        question.save()

    def test_an_over_limit_answer_is_saved_as_typed(self):
        self._entry_with("Short.")
        self._limit_first_question()
        client = Client(self.room)
        coedit.apply(self.student, self.room, client.replace(self.field, "one two three four five"))

        coedit.save(self.room)

        self.assertEqual(self._entry().answers[self.key], "one two three four five")

    def test_a_submitted_entry_is_never_written(self):
        self._entry_with("Draft")
        client = Client(self.room)
        coedit.apply(self.student, self.room, client.type(self.field, 5, " more"))
        entry = self._entry()
        entry.snapshot(self.student)
        entry.save()

        self.assertFalse(coedit.save(self.room))
        self.assertEqual(self._entry().answers[self.key], "Draft")

    def test_a_change_made_outside_the_document_wins_and_rebuilds_it(self):
        self._entry_with("Draft")
        Client(self.room)
        Submission.objects.filter(group=self.group).update(answers={self.key: "Changed elsewhere."})

        with patch.object(coedit, "broadcast_reset") as reset, self.captureOnCommitCallbacks(execute=True):
            self.assertFalse(coedit.save(self.room))

        reset.assert_called_once_with(self.room)
        self.assertEqual(Client(self.room).text(self.field), "Changed elsewhere.")

    def test_flush_is_a_no_op_while_switched_off(self):
        with override_settings(SUBMISSION_COEDITING_ENABLED=False):
            self.assertTrue(coedit.flush(self.room))


class EndpointTests(CoeditTestCase):
    def test_the_page_is_told_co_editing_is_on(self):
        self.assertTrue(self._client(self.student).get(self._url("group-submission")).data["coediting"])

    def test_a_team_cannot_save_answers_around_the_document(self):
        response = self._client(self.student).put(
            self._url("group-submission"), {"answers": {self.key: "Stale page."}}, format="json"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "coediting_active")

    def _save_without_live(self, answers=None, **extra):
        body = {"answers": answers or {self.key: "Typed offline."}, "live_unavailable": True, **extra}
        return self._client(self.student).put(self._url("group-submission"), body, format="json")

    def test_a_page_without_the_live_connection_saves_into_the_document(self):
        self._entry_with("Draft")
        other = self.questions[1].key
        Client(self.room)

        with patch.object(coedit, "broadcast_update") as broadcast:
            response = self._save_without_live({self.key: "Typed offline."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["submission"]["answers"][self.key], "Typed offline.")
        broadcast.assert_called_once()
        self.assertEqual(Client(self.room).text(self.field), "Typed offline.")
        self.assertEqual(Client(self.room).text(coedit.answer_field(other)), "Draft")
        self.assertEqual(self._entry().answers[self.key], "Typed offline.")

    def test_a_teammates_live_save_afterwards_keeps_it_and_rebuilds_nothing(self):
        self._entry_with("Draft")
        page = Client(self.room)
        self._save_without_live({self.key: "Typed offline."})
        other = coedit.answer_field(self.questions[1].key)
        page.doc.apply_update(coedit.state_since(self.room, page.doc.get_state())[0])
        coedit.apply(self.student, self.room, page.type(other, 5, " and more"))

        with patch.object(coedit, "broadcast_reset") as reset:
            self.assertTrue(coedit.save(self.room))

        reset.assert_not_called()
        self.assertEqual(self._entry().answers[self.key], "Typed offline.")
        self.assertEqual(self._entry().answers[self.questions[1].key], "Draft and more")

    def test_an_over_limit_answer_is_saved_as_typed_without_the_live_connection_too(self):
        self._entry_with("Draft")
        SubmissionQuestion.objects.filter(key=self.key).update(max_words=3)

        response = self._save_without_live({self.key: "one two three four five"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._entry().answers[self.key], "one two three four five")

    def test_the_marker_cannot_lift_the_limit_when_co_editing_is_off(self):
        self._entry_with("Draft")
        SubmissionQuestion.objects.filter(key=self.key).update(max_words=3)

        with override_settings(SUBMISSION_COEDITING_ENABLED=False):
            response = self._save_without_live({self.key: "one two three four five"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self._entry().answers[self.key], "Draft")

    def test_the_title_saves_the_same_way(self):
        self._entry_with("Draft")

        self._client(self.student).put(
            self._url("group-submission"), {"project_title": "Offline title", "live_unavailable": True}, format="json"
        )

        self.assertEqual(Client(self.room).text(coedit.TITLE_FIELD), "Offline title")
        self.assertEqual(self._entry().project_title, "Offline title")

    def test_the_text_still_saves_when_the_document_is_out_of_reach(self):
        self._entry_with("Draft")
        Client(self.room)

        with unreachable(), self.assertLogs("apps.submissions.coedit", "ERROR"):
            response = self._save_without_live({self.key: "Typed offline."})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._entry().answers[self.key], "Typed offline.")
        # Once the document can be read again, the next save finds the entry newer and takes it.
        with patch.object(coedit, "broadcast_reset"), self.captureOnCommitCallbacks(execute=True):
            coedit.save(self.room)
        self.assertEqual(Client(self.room).text(self.field), "Typed offline.")

    def test_a_submitted_entry_refuses_a_save_without_the_live_connection_too(self):
        self._entry_with("Draft")
        Submission.objects.filter(group=self.group).update(submitted_at=timezone.now())

        response = self._save_without_live()

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "submission_locked")
        self.assertEqual(self._entry().answers[self.key], "Draft")

    def test_a_team_still_saves_the_link_and_ticks_as_before(self):
        response = self._client(self.student).put(
            self._url("group-submission"), {"prototype_url": "https://example.com/demo"}, format="json"
        )

        self.assertEqual(response.status_code, 200)

    def test_an_admins_save_goes_into_the_document_and_stays(self):
        self._entry_with("Draft")
        Client(self.room)

        with patch.object(coedit, "broadcast_update") as broadcast:
            self._client(self.admin).put(
                self._url("group-submission"), {"answers": {self.key: "Fixed by the programme."}}, format="json"
            )

        broadcast.assert_called_once()
        self.assertEqual(Client(self.room).text(self.field), "Fixed by the programme.")
        self.assertTrue(coedit.save(self.room))
        self.assertEqual(self._entry().answers[self.key], "Fixed by the programme.")

    def test_submit_takes_the_documents_latest_text(self):
        self._upload(self.student, _poster())
        self._entry_with("Draft")
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")
        client = Client(self.room)
        coedit.apply(self.student, self.room, client.type(self.field, 5, " final"))

        response = self._client(self.student).post(self._url("group-submission-submit"), {}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._entry().submitted_answers[self.key], "Draft final")

    def _ready_to_submit(self):
        self._upload(self.student, _poster())
        self._entry_with("Draft")
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")

    def test_submit_refuses_an_answer_over_its_limit_for_teams_and_admins(self):
        self._ready_to_submit()
        question = self.questions[0]
        question.max_words = 3
        question.save()
        coedit.apply(self.student, self.room, Client(self.room).replace(self.field, "one two three four five"))

        for user in (self.student, self.admin):
            with self.subTest(user=user.email):
                response = self._client(user).post(self._url("group-submission-submit"), {}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["code"], "answers_over_limit")
        self.assertFalse(self._entry().is_submitted)

    def test_auto_submit_leaves_a_draft_with_an_over_limit_answer(self):
        self._ready_to_submit()
        for question in self.questions:
            coedit.apply(self.student, self.room, Client(self.room).replace(coedit.answer_field(question.key), "word " * 5))
        question = self.questions[0]
        question.max_words = 3
        question.save()
        Submission.objects.filter(group=self.group).update(cohort=2026)
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()

        with patch("apps.submissions.autosubmit.current_cohort", return_value=2026):
            result = auto_submit_due()

        self.assertEqual(result["submitted"], [])
        self.assertFalse(self._entry().is_submitted)

    def test_auto_submit_takes_the_documents_latest_text(self):
        self._upload(self.student, _poster())
        self._entry_with("")
        self._client(self.student).put(self._url("group-submission"), {"poster_checklist": CONFIRMED_CHECKLIST}, format="json")
        client = Client(self.room)
        for question in self.questions:
            coedit.apply(self.student, self.room, client.replace(coedit.answer_field(question.key), "Typed live."))
        coedit.apply(self.student, self.room, client.replace(coedit.TITLE_FIELD, "Live title"))
        Submission.objects.filter(group=self.group).update(cohort=2026)
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()

        with patch("apps.submissions.autosubmit.current_cohort", return_value=2026):
            result = auto_submit_due()

        self.assertEqual(result["submitted"], ["BTF7"])
        self.assertEqual(self._entry().submitted_answers[self.key], "Typed live.")


def _consumer(user, room, channel="ada-channel"):
    consumer = LiveRoomConsumer()
    consumer.room = f"live.submission.{room}"
    consumer.room_id = room
    consumer.scope = {"user": user}
    consumer.user = {"id": user.id, "name": user.first_name}
    consumer._start_relays()
    consumer._start_document(coedit)
    consumer.channel_layer = AsyncMock()
    consumer.channel_name = channel
    consumer.send_json = AsyncMock()
    return consumer


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode()


class LiveMessageTests(CoeditTestCase):
    def test_a_page_syncing_gets_the_document_and_whether_it_may_edit(self):
        self._entry_with()
        consumer = _consumer(self.student, self.room)

        async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": "", "update": ""})

        reply = consumer.send_json.await_args.args[0]
        self.assertEqual(reply["type"], "doc-state")
        self.assertTrue(reply["editable"])
        self.assertTrue(reply["vector"])
        page = Doc()
        page.apply_update(base64.b64decode(reply["update"]))
        self.assertEqual(str(page.get(self.field, type=Text)), "Saved answer.")

    def test_an_update_reaches_the_rest_of_the_room_and_is_saved_after_a_pause(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        update = Client(self.room).type(self.field, 5, "!")

        with patch("apps.live.shared_documents.DOC_SAVE_DELAY", 0):
            async def run():
                await consumer.receive_json({"type": "doc-update", "update": _b64(update)})
                await shared_documents._waiting_saves[consumer.room]

            async_to_sync(run)()

        room, event = consumer.channel_layer.group_send.await_args.args
        self.assertEqual(event["type"], "room.doc")
        self.assertEqual(event["sender"], "ada-channel")
        self.assertEqual(self._entry().answers[self.key], "Draft!")

    def test_a_refused_update_tells_the_page_to_start_again(self):
        self._entry_with()
        consumer = _consumer(self.admin, self.room)

        async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(Client(self.room).type(self.field, 0, "x"))})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})
        consumer.channel_layer.group_send.assert_not_awaited()

    def test_refused_local_changes_on_sync_are_answered_with_the_full_document(self):
        self._entry_with()
        self.deadline.closes_at = timezone.now() - timedelta(days=1)
        self.deadline.save()
        consumer = _consumer(self.student, self.room)
        page = Client(self.room)
        local = page.type(self.field, 0, "offline ")

        async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": _b64(page.doc.get_state()), "update": _b64(local)})

        reply = consumer.send_json.await_args.args[0]
        self.assertTrue(reply["full"])
        self.assertFalse(reply["editable"])

    def test_a_flood_of_updates_is_refused_rather_than_dropped(self):
        self._entry_with("")
        consumer = _consumer(self.student, self.room)
        client = Client(self.room)

        async def flood():
            for i in range(35):
                await consumer.receive_json({"type": "doc-update", "update": _b64(client.type(self.field, i, "a"))})

        async_to_sync(flood)()

        self.assertIn({"type": "doc-reject"}, [call.args[0] for call in consumer.send_json.await_args_list])

    def test_a_flush_answers_once_the_text_is_saved(self):
        self._entry_with("Draft")
        coedit.apply(self.student, self.room, Client(self.room).type(self.field, 5, "!"))
        consumer = _consumer(self.student, self.room)

        async_to_sync(consumer.receive_json)({"type": "doc-flush", "id": 7})

        consumer.send_json.assert_awaited_with({"type": "doc-flushed", "id": 7, "ok": True})
        self.assertEqual(self._entry().answers[self.key], "Draft!")

    def test_doc_messages_are_ignored_while_switched_off(self):
        consumer = _consumer(self.student, self.room)

        with override_settings(SUBMISSION_COEDITING_ENABLED=False):
            async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": "", "update": ""})

        consumer.send_json.assert_not_awaited()

    def test_garbage_base64_is_refused(self):
        consumer = _consumer(self.student, self.room)

        async_to_sync(consumer.receive_json)({"type": "doc-update", "update": "%%%not base64"})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})


class TeamSaveTests(CoeditTestCase):
    def _update(self, consumer, update):
        return consumer.receive_json({"type": "doc-update", "update": _b64(update)})

    def test_teammates_typing_at_once_share_one_save(self):
        self._entry_with("Draft")
        ada, ben = _consumer(self.student, self.room, "ada"), _consumer(self.student, self.room, "ben")
        page = Client(self.room)

        with patch("apps.live.shared_documents.DOC_SAVE_DELAY", 0.2), patch.object(coedit, "save", wraps=coedit.save) as save:
            async def run():
                await self._update(ada, page.type(self.field, 5, " one"))
                await self._update(ben, page.type(self.field, 9, " two"))
                await shared_documents._waiting_saves[ada.room]

            async_to_sync(run)()

        self.assertEqual(save.call_count, 1)
        self.assertEqual(self._entry().answers[self.key], "Draft one two")

    def test_no_save_is_scheduled_while_another_worker_holds_the_teams_save(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        coedit.store().claim_save(self.room, 10)

        async_to_sync(self._update)(consumer, Client(self.room).type(self.field, 5, "!"))

        self.assertNotIn(consumer.room, shared_documents._waiting_saves)
        self.assertEqual(Client(self.room).text(self.field), "Draft!")

    def test_typing_after_a_save_begins_gets_a_save_of_its_own(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        page = Client(self.room)

        with patch("apps.live.shared_documents.DOC_SAVE_DELAY", 0.05):
            async def run():
                await self._update(consumer, page.type(self.field, 5, " one"))
                first = shared_documents._waiting_saves[consumer.room]
                await first
                await self._update(consumer, page.type(self.field, 9, " two"))
                second = shared_documents._waiting_saves[consumer.room]
                self.assertIsNot(first, second)
                await second

            async_to_sync(run)()

        self.assertEqual(self._entry().answers[self.key], "Draft one two")

    def test_the_save_still_runs_after_the_typist_leaves(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        update = Client(self.room).type(self.field, 5, "!")

        with patch("apps.live.shared_documents.DOC_SAVE_DELAY", 0.05):
            async def run():
                await self._update(consumer, update)
                await consumer.disconnect(1000)
                await shared_documents._waiting_saves[consumer.room]

            async_to_sync(run)()

        self.assertEqual(self._entry().answers[self.key], "Draft!")


class RememberedPermissionTests(CoeditTestCase):
    def test_a_burst_of_edits_asks_whether_the_typist_may_edit_once(self):
        self._entry_with("")
        consumer = _consumer(self.student, self.room)
        page = Client(self.room)

        with patch.object(coedit, "can_edit", wraps=coedit.can_edit) as can_edit:
            async def run():
                for i in range(5):
                    await consumer.receive_json({"type": "doc-update", "update": _b64(page.type(self.field, i, str(i)))})

            async_to_sync(run)()

        self.assertEqual(can_edit.call_count, 1)
        self.assertEqual(Client(self.room).text(self.field), "01234")

    def test_the_answer_is_asked_again_once_it_is_a_few_seconds_old(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        page = Client(self.room)
        async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(page.type(self.field, 5, " one"))})
        self.deadline.closes_at = timezone.now() - timedelta(minutes=1)
        self.deadline.save()

        # Within the few seconds, the remembered answer still stands.
        async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(page.type(self.field, 9, " two"))})
        with patch("apps.live.shared_documents.DOC_PERMISSION_SECONDS", 0):
            async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(page.type(self.field, 13, " three"))})

        consumer.send_json.assert_awaited_with({"type": "doc-reject"})
        self.assertEqual(Client(self.room).text(self.field), "Draft one two")

    def test_a_resync_always_asks_afresh(self):
        self._entry_with("Draft")
        consumer = _consumer(self.student, self.room)
        async_to_sync(consumer.receive_json)({"type": "doc-update", "update": _b64(Client(self.room).type(self.field, 5, "!"))})
        self.deadline.closes_at = timezone.now() - timedelta(minutes=1)
        self.deadline.save()

        async_to_sync(consumer.receive_json)({"type": "doc-sync", "vector": "", "update": ""})

        self.assertFalse(consumer.send_json.await_args.args[0]["editable"])
