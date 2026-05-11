"""Contract coverage tests for the chat API.

Locks behaviour described in ``.claude/plans/chat-api-frontend.md`` that
existed coverage didn't already pin: PATCH end-to-end (RBAC + edit
flags + ``message.edited`` broadcast), POST validation edges (missing
both text and resources, invalid resource id, resource-only post),
GET pagination edges (limit clamping, empty list, default limit),
401/403/404 distinctions, and WebSocket close-code coverage for the
unauthenticated and no-access paths.
"""
from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

try:
    from asgiref.sync import async_to_sync
    from channels.testing import WebsocketCommunicator

    from config.asgi import application
    HAS_CHANNELS_TESTING = True
except ImportError:
    HAS_CHANNELS_TESTING = False

from apps.chat.models import Messages
from apps.common.storage import get_chat_storage
from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles, Resources
from apps.users.models import AdminScope
from tests.apps._helpers import StorageCleanupMixin, assert_public_message_shape


CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


class _ChatFixture(StorageCleanupMixin, TestCase):
    """Common world for contract tests. Mirrors the topology used by
    ChatFeatureTests but kept local so this file stays self-contained."""

    storage_attr = "chat_storage"
    storage_keys_attr = "created_chat_storage_keys"

    def setUp(self):
        User = get_user_model()

        self.student = User.objects.create_user(email="student@test.com", password="pw")
        self.peer = User.objects.create_user(email="peer@test.com", password="pw")
        self.mentor = User.objects.create_user(email="mentor@test.com", password="pw")
        self.supervisor = User.objects.create_user(email="supervisor@test.com", password="pw")
        self.admin = User.objects.create_user(email="admin@test.com", password="pw")
        self.track_admin = User.objects.create_user(email="track_admin@test.com", password="pw")
        self.outsider = User.objects.create_user(email="outsider@test.com", password="pw")

        self.role_student = Roles.objects.create(role_name="student")
        self.role_mentor = Roles.objects.create(role_name="mentor")
        self.role_supervisor = Roles.objects.create(role_name="supervisor")
        self.role_admin = Roles.objects.create(role_name="admin")

        now = timezone.now()
        future = now + timedelta(days=365)
        for u, r in [
            (self.student, self.role_student),
            (self.peer, self.role_student),
            (self.mentor, self.role_mentor),
            (self.supervisor, self.role_supervisor),
            (self.admin, self.role_admin),
        ]:
            RoleAssignmentHistory.objects.create(user=u, role=r, valid_from=now, valid_to=future)

        self.country = Countries.objects.create(country_name="Australia")
        self.state = CountryStates.objects.create(country=self.country, state_name="NSW")
        self.track = Tracks.objects.create(track_name="AUS-NSW", state=self.state)
        self.other_state = CountryStates.objects.create(country=self.country, state_name="VIC")
        self.other_track = Tracks.objects.create(track_name="AUS-VIC", state=self.other_state)

        self.group = Groups.objects.create(group_name="G1", track=self.track)
        self.other_group = Groups.objects.create(group_name="G-VIC", track=self.other_track)

        GroupMembership.objects.create(user=self.student, group=self.group)
        GroupMembership.objects.create(user=self.peer, group=self.group)
        GroupMembership.objects.create(user=self.mentor, group=self.group, membership_role="mentor")
        GroupMembership.objects.create(user=self.supervisor, group=self.group, membership_role="supervisor")

        AdminScope.objects.create(user=self.admin, is_global=True)
        AdminScope.objects.create(user=self.track_admin, track=self.track, is_global=False)

        self.res1 = Resources.objects.create(
            name="R1", description="d1", uploaded_by=self.admin,
            uploaded_at=timezone.now() - timedelta(minutes=1),
        )

        self.client_student = APIClient(); self.client_student.force_authenticate(user=self.student)
        self.client_peer = APIClient(); self.client_peer.force_authenticate(user=self.peer)
        self.client_mentor = APIClient(); self.client_mentor.force_authenticate(user=self.mentor)
        self.client_supervisor = APIClient(); self.client_supervisor.force_authenticate(user=self.supervisor)
        self.client_admin = APIClient(); self.client_admin.force_authenticate(user=self.admin)
        self.client_track_admin = APIClient(); self.client_track_admin.force_authenticate(user=self.track_admin)
        self.client_outsider = APIClient(); self.client_outsider.force_authenticate(user=self.outsider)
        self.client_anon = APIClient()

        self.chat_storage = get_chat_storage()
        self.created_chat_storage_keys = []

    def _list_url(self, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-list", kwargs={"group_pk": gid})

    def _detail_url(self, mid, group_id=None):
        gid = group_id or self.group.id
        return reverse("group-messages-detail", kwargs={"group_pk": gid, "pk": mid})


class PatchMessageContractTests(_ChatFixture):
    """``PATCH /chat/groups/{gid}/messages/{id}/`` — RBAC, edit flags,
    soft-deleted lookup, ``message.edited`` broadcast."""

    def _patch(self, client, msg, body=None):
        return client.patch(
            self._detail_url(msg.id),
            body or {"message_text": "fixed typo"},
            format="json",
        )

    def test_patch_sets_edited_at_and_flips_is_edited_and_returns_public_shape(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="oops")
        resp = self._patch(self.client_student, msg)
        self.assertEqual(resp.status_code, 200, resp.content)
        assert_public_message_shape(self, resp.data)
        self.assertEqual(resp.data["message_text"], "fixed typo")
        self.assertTrue(resp.data["is_edited"])
        self.assertIsNotNone(resp.data["edited_at"])
        msg.refresh_from_db()
        self.assertIsNotNone(msg.edited_at)
        self.assertEqual(msg.message_text, "fixed typo")

    def test_patch_allowed_for_sender_within_window(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="old")
        resp = self._patch(self.client_student, msg)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_patch_forbidden_for_sender_after_window(self):
        msg = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="too old",
            sent_at=timezone.now() - timedelta(minutes=11),
        )
        resp = self._patch(self.client_student, msg)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_patch_forbidden_for_non_sender_peer(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="x")
        resp = self._patch(self.client_peer, msg)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_patch_forbidden_for_mentor_without_admin_scope(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="x")
        resp = self._patch(self.client_mentor, msg)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_patch_forbidden_for_supervisor_without_admin_scope(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="x")
        resp = self._patch(self.client_supervisor, msg)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_patch_allowed_for_global_admin_anywhere(self):
        msg = Messages.objects.create(
            group=self.other_group, sender_user=self.student, message_text="old"
        )
        url = reverse("group-messages-detail", kwargs={"group_pk": self.other_group.id, "pk": msg.id})
        resp = self.client_admin.patch(url, {"message_text": "moderated"}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        msg.refresh_from_db()
        self.assertEqual(msg.message_text, "moderated")
        self.assertIsNotNone(msg.edited_at)

    def test_patch_allowed_for_track_admin_within_track(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="old")
        resp = self._patch(self.client_track_admin, msg)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_patch_forbidden_for_track_admin_outside_track(self):
        msg = Messages.objects.create(group=self.other_group, sender_user=self.student, message_text="old")
        url = reverse("group-messages-detail", kwargs={"group_pk": self.other_group.id, "pk": msg.id})
        resp = self.client_track_admin.patch(url, {"message_text": "x"}, format="json")
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_patch_404_for_soft_deleted_message(self):
        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="hide",
            deleted_at=timezone.now(),
        )
        resp = self._patch(self.client_admin, msg)
        # Soft-deleted messages are filtered out of get_queryset, so the
        # lookup is 404, not 200 — contract says "404 if soft-deleted by id".
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_patch_unauthenticated_returns_401(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="x")
        resp = self.client_anon.patch(
            self._detail_url(msg.id), {"message_text": "y"}, format="json"
        )
        self.assertEqual(resp.status_code, 401, resp.content)

    @patch("apps.chat.views.get_channel_layer")
    def test_patch_broadcasts_message_edited_envelope(self, mock_get_channel_layer):
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = fake_layer

        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="old"
        )
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client_student.patch(
                self._detail_url(msg.id),
                {"message_text": "new"},
                format="json",
            )
        self.assertEqual(resp.status_code, 200, resp.content)

        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        self.assertEqual(payload["event"], "message.edited")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message"]["id"], msg.id)
        self.assertEqual(payload["message"]["message_text"], "new")
        # Legacy aliases included on broadcast shape.
        self.assertEqual(payload["message"]["text"], "new")
        self.assertEqual(payload["message"]["sender_id"], self.student.id)
        self.assertEqual(payload["message"]["resource_ids"], [])
        self.assertTrue(payload["message"]["is_edited"])
        self.assertFalse(payload["message"]["is_deleted"])

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_patch_response_carries_moderated_text(self):
        from apps.chat.utils import reset_pattern_cache
        reset_pattern_cache()
        try:
            msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="clean")
            resp = self.client_student.patch(
                self._detail_url(msg.id), {"message_text": "ugh shithole"}, format="json"
            )
            self.assertEqual(resp.status_code, 200, resp.content)
            self.assertEqual(resp.data["message_text"], "ugh ***")
        finally:
            reset_pattern_cache()


class PostMessageValidationTests(_ChatFixture):
    """Contract: POST must include text OR ≥1 resource; ``resource_id``
    references are validated; sender/text-only and resources-only both
    work; the moderated text round-trips back in the 201."""

    def test_post_with_neither_text_nor_resources_is_400(self):
        resp = self.client_student.post(
            self._list_url(),
            {"message_text": "", "resources": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_post_with_blank_text_and_no_resources_is_400(self):
        resp = self.client_student.post(
            self._list_url(),
            {"message_text": "   "},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_post_with_resources_only_succeeds(self):
        resp = self.client_student.post(
            self._list_url(),
            {"resources": [{"resource_id": self.res1.id}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        assert_public_message_shape(self, resp.data)
        self.assertEqual(resp.data["message_text"], "")
        self.assertEqual([r["resource_id"] for r in resp.data["resources"]], [self.res1.id])

    def test_post_with_invalid_resource_id_is_400(self):
        bogus = self.res1.id + 99999
        resp = self.client_student.post(
            self._list_url(),
            {"message_text": "hi", "resources": [{"resource_id": bogus}]},
            format="json",
        )
        self.assertEqual(resp.status_code, 400, resp.content)

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["shit*"],
        CHAT_SANITIZER_REPLACEMENT="***",
    )
    def test_post_response_returns_moderated_text(self):
        from apps.chat.utils import reset_pattern_cache
        reset_pattern_cache()
        try:
            resp = self.client_student.post(
                self._list_url(),
                {"message_text": "this is bullshit", "resources": []},
                format="json",
            )
            self.assertEqual(resp.status_code, 201, resp.content)
            self.assertEqual(resp.data["message_text"], "this is ***")
        finally:
            reset_pattern_cache()

    def test_post_unauthenticated_returns_401(self):
        resp = self.client_anon.post(
            self._list_url(), {"message_text": "hi"}, format="json"
        )
        self.assertEqual(resp.status_code, 401, resp.content)

    def test_post_outsider_returns_403(self):
        resp = self.client_outsider.post(
            self._list_url(), {"message_text": "hi"}, format="json"
        )
        self.assertEqual(resp.status_code, 403, resp.content)


class ListMessagesContractTests(_ChatFixture):
    """``GET /chat/groups/{gid}/messages/`` — limit clamping, ordering,
    empty-list response, soft-delete exclusion, auth gates."""

    def test_list_returns_next_after_null_when_empty(self):
        resp = self.client_student.get(self._list_url())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data["items"], [])
        self.assertIsNone(resp.data["next_after"])

    def test_list_next_after_is_id_of_newest_item(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="m1")
        m2 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m2")
        resp = self.client_student.get(self._list_url())
        self.assertEqual(resp.status_code, 200)
        # Newest-first; the first item is m2.
        self.assertEqual(resp.data["items"][0]["id"], m2.id)
        self.assertEqual(resp.data["next_after"], m2.id)

    def test_list_default_limit_is_50(self):
        # 51 messages → only 50 returned even without ?limit=.
        # Build with explicit, monotonically-increasing sent_at so the
        # ``-sent_at, -id`` ordering is deterministic regardless of
        # millisecond ties in ``default=timezone.now``.
        base = timezone.now() - timedelta(minutes=51)
        created = []
        for i in range(51):
            created.append(Messages.objects.create(
                group=self.group, sender_user=self.student,
                message_text=f"m{i}",
                sent_at=base + timedelta(seconds=i),
            ))
        resp = self.client_student.get(self._list_url())
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data["items"]), 50)
        # Newest item is the one created last.
        self.assertEqual(resp.data["items"][0]["id"], created[-1].id)

    def test_list_limit_above_100_is_clamped_to_100(self):
        base = timezone.now() - timedelta(minutes=101)
        for i in range(101):
            Messages.objects.create(
                group=self.group, sender_user=self.student,
                message_text=f"m{i}",
                sent_at=base + timedelta(seconds=i),
            )
        resp = self.client_student.get(self._list_url() + "?limit=500")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["items"]), 100)

    def test_list_limit_zero_is_clamped_to_one(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="m")
        resp = self.client_student.get(self._list_url() + "?limit=0")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data["items"]), 1)

    def test_list_nonnumeric_limit_falls_back_to_default(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="m")
        resp = self.client_student.get(self._list_url() + "?limit=banana")
        self.assertEqual(resp.status_code, 200)
        # Non-numeric falls back to the default (50), so the single message comes through.
        self.assertEqual(len(resp.data["items"]), 1)

    def test_list_after_pointing_to_unknown_id_is_ignored(self):
        m1 = Messages.objects.create(group=self.group, sender_user=self.student, message_text="m1")
        resp = self.client_student.get(self._list_url() + "?after=999999")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual([it["id"] for it in resp.data["items"]], [m1.id])

    def test_list_unauthenticated_returns_401(self):
        resp = self.client_anon.get(self._list_url())
        self.assertEqual(resp.status_code, 401, resp.content)

    def test_list_outsider_returns_403(self):
        resp = self.client_outsider.get(self._list_url())
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_global_admin_can_list_any_group(self):
        url = self._list_url(self.other_group.id)
        Messages.objects.create(group=self.other_group, sender_user=self.student, message_text="x")
        resp = self.client_admin.get(url)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(len(resp.data["items"]), 1)

    def test_track_admin_can_list_within_track_only(self):
        Messages.objects.create(group=self.group, sender_user=self.student, message_text="x")
        Messages.objects.create(group=self.other_group, sender_user=self.student, message_text="y")
        ok = self.client_track_admin.get(self._list_url())
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(len(ok.data["items"]), 1)

        nope = self.client_track_admin.get(self._list_url(self.other_group.id))
        self.assertEqual(nope.status_code, 403, nope.content)


class DeleteMessageContractTests(_ChatFixture):
    """Gaps in DELETE coverage: 404 for soft-deleted lookup, 401 for
    unauthenticated."""

    def test_delete_404_for_soft_deleted_message(self):
        msg = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="hide",
            deleted_at=timezone.now(),
        )
        resp = self.client_admin.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 404, resp.content)

    def test_delete_unauthenticated_returns_401(self):
        msg = Messages.objects.create(group=self.group, sender_user=self.student, message_text="x")
        resp = self.client_anon.delete(self._detail_url(msg.id))
        self.assertEqual(resp.status_code, 401, resp.content)


class AttachmentDownloadContractTests(_ChatFixture):
    """Download endpoint — 401 for unauthenticated, 404 distinction."""

    def test_download_unauthenticated_returns_401(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload_response = self.client_student.post(
            reverse("group-messages-upload", kwargs={"group_pk": self.group.id}),
            {"uploaded_file": SimpleUploadedFile("p.pdf", b"bytes", content_type="application/pdf")},
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 201, upload_response.content)
        message = Messages.objects.prefetch_related("attachments").get(pk=upload_response.data["id"])
        attachment = message.attachments.get()
        self.created_chat_storage_keys.append(attachment.storage_key)

        url = reverse(
            "group-messages-attachment-download",
            kwargs={
                "group_pk": self.group.id,
                "pk": message.id,
                "attachment_pk": attachment.id,
            },
        )
        resp = self.client_anon.get(url)
        self.assertEqual(resp.status_code, 401, resp.content)


@unittest.skipUnless(HAS_CHANNELS_TESTING, "channels.testing requires daphne")
@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class WebSocketCloseCodeTests(_ChatFixture):
    """The consumer must close with 4400 for a non-numeric group id and
    4403 for unauthenticated or no-group-access callers. The 4400 path
    is already covered by ``GroupChatConsumerDefensiveTests`` at the
    pure-async layer; here we exercise the live transport for the auth
    arms."""

    def _connect(self, *, group_id, cookie_header=None):
        headers = [cookie_header] if cookie_header else []
        communicator = WebsocketCommunicator(
            application, f"/ws/chat/groups/{group_id}/", headers=headers,
        )
        connected, code_or_subprotocol = async_to_sync(communicator.connect)()
        # On rejection, ``code_or_subprotocol`` carries the close code.
        async_to_sync(communicator.disconnect)()
        return connected, code_or_subprotocol

    def _session_cookie(self, user):
        c = Client()
        c.force_login(user)
        return c.cookies[settings.SESSION_COOKIE_NAME].value

    def _cookie_header(self, user):
        cookie = self._session_cookie(user)
        return (b"cookie", f"{settings.SESSION_COOKIE_NAME}={cookie}".encode())

    def test_ws_closes_4403_when_unauthenticated(self):
        connected, code = self._connect(group_id=self.group.id)
        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    def test_ws_closes_4403_when_outsider(self):
        header = self._cookie_header(self.outsider)
        connected, code = self._connect(group_id=self.group.id, cookie_header=header)
        self.assertFalse(connected)
        self.assertEqual(code, 4403)

    def test_ws_connects_for_group_member(self):
        header = self._cookie_header(self.student)
        connected, _ = self._connect(group_id=self.group.id, cookie_header=header)
        self.assertTrue(connected)

    def test_ws_connects_for_global_admin_in_any_group(self):
        header = self._cookie_header(self.admin)
        connected, _ = self._connect(group_id=self.other_group.id, cookie_header=header)
        self.assertTrue(connected)

    def test_ws_closes_4403_for_track_admin_outside_track(self):
        header = self._cookie_header(self.track_admin)
        connected, code = self._connect(group_id=self.other_group.id, cookie_header=header)
        self.assertFalse(connected)
        self.assertEqual(code, 4403)
