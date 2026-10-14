"""Tests for co-editing: the shared document behind a team's answers and title."""
import base64
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import override_settings
from django.utils import timezone
from pycrdt import Doc, Text

from apps.live.consumers import LiveRoomConsumer
from apps.submissions import coedit
from apps.submissions.autosubmit import auto_submit_due
from apps.submissions.models import Submission
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


@override_settings(SUBMISSION_COEDITING_ENABLED=True)
class CoeditTestCase(ChecklistTestCase):
    def setUp(self):
        super().setUp()
        coedit.store().clear()
        self.addCleanup(coedit.store().clear)
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

    def test_an_over_limit_answer_is_not_saved_and_the_last_valid_one_stays(self):
        self._entry_with("Short.")
        question = self.questions[0]
        question.max_words = 3
        question.save()
        client = Client(self.room)
        coedit.apply(self.student, self.room, client.replace(self.field, "one two three four five"))

        coedit.save(self.room)

        self.assertEqual(self._entry().answers[self.key], "Short.")
        self.assertEqual(Client(self.room).text(self.field), "one two three four five")

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


def _consumer(user, room):
    consumer = LiveRoomConsumer()
    consumer.room = f"live.submission.{room}"
    consumer.room_id = room
    consumer.document = coedit
    consumer.scope = {"user": user}
    consumer.user = {"id": user.id, "name": user.first_name}
    consumer._doc_window = (0.0, 0)
    consumer._doc_save = None
    consumer._doc_edited = False
    consumer.channel_layer = AsyncMock()
    consumer.channel_name = "ada-channel"
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

        with patch("apps.live.consumers.DOC_SAVE_DELAY", 0):
            async def run():
                await consumer.receive_json({"type": "doc-update", "update": _b64(update)})
                await consumer._doc_save

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
