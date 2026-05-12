"""Tests for the link-preview unfurl pipeline.

Covers the two spec cases:

1. ``test_dispatch_on_url`` — POST a chat message containing a real URL,
   assert that ``dispatch_og`` is invoked with ``(message_id, url)`` *after*
   the request transaction commits.

2. ``test_og_extraction_worker`` — drive ``fetch_og_data`` directly with an
   HTML fixture (HTTP / Redis / channel layer mocked), assert the
   ``MessagePreview`` row is written and a ``message.preview_ready``
   envelope is fanned out over the channel layer.

Supporting tests cover the no-URL short-circuit, the Redis cache-hit path,
fetch failure handling, and the URL-extraction helper.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from rest_framework.test import APIClient

from apps.chat.models import MessagePreview, Messages
from apps.chat.og_extractor import (
    cache_key_for,
    extract_urls,
    has_url,
    parse_og_metadata,
)
from apps.chat.tasks import fetch_og_data
from apps.groups.models import (
    Countries,
    CountryStates,
    GroupMembership,
    Groups,
    Tracks,
)
from apps.resources.models import RoleAssignmentHistory, Roles
from django.contrib.auth import get_user_model
from django.urls import reverse


CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


class _FakeRedis:
    """In-memory stand-in for the Redis client used by tasks.

    Only ``get`` / ``setex`` are exercised by the worker; everything else is a
    no-op. Storing bytes mirrors what ``redis-py`` would return so the JSON
    round-trip in ``tasks._read_cached`` matches production behaviour.
    """

    def __init__(self, initial: dict[str, bytes] | None = None) -> None:
        self.store: dict[str, bytes] = dict(initial or {})
        self.setex_calls: list[tuple[str, int, bytes]] = []

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: bytes | str):
        if isinstance(value, str):
            value = value.encode("utf-8")
        self.store[key] = value
        self.setex_calls.append((key, ttl, value))
        return True


def _build_chat_fixtures(test):
    """Build the minimum users + group needed to POST a message.

    Pulled out of the test classes so each TestCase keeps its setUp small —
    the ``ChatFeatureTests`` setUp in ``test_chat.py`` is the heavyweight
    fixture; we only need the bare minimum to drive the message create path.
    """
    User = get_user_model()
    test.student = User.objects.create_user(email="lp_student@test.com", password="pw")

    test.role_student = Roles.objects.create(role_name="student")
    now = timezone.now()
    future = now.replace(year=2099)
    RoleAssignmentHistory.objects.create(
        user=test.student,
        role=test.role_student,
        valid_from=now,
        valid_to=future,
    )

    test.country = Countries.objects.create(country_name="Australia")
    test.state = CountryStates.objects.create(
        country=test.country, state_name="NSW"
    )
    test.track = Tracks.objects.create(track_name="AUS-NSW", state=test.state)

    test.group = Groups.objects.create(group_name="LP-G1", track=test.track)
    GroupMembership.objects.create(user=test.student, group=test.group)

    test.client_student = APIClient()
    test.client_student.force_authenticate(user=test.student)


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class LinkPreviewDispatchTests(TestCase):
    """Verifies the view-side fire-and-forget contract."""

    def setUp(self):
        _build_chat_fixtures(self)

    def _list_url(self):
        return reverse(
            "group-messages-list", kwargs={"group_pk": self.group.id}
        )

    def test_dispatch_on_url(self):
        """POST a message containing https:// — assert the dispatcher fires.

        We patch ``apps.chat.views.dispatch_og`` (the *imported* binding) so
        no thread is actually spawned. The dispatcher is what the view layer
        calls; whether it threads, queues, or runs inline is an internal
        detail tested elsewhere.
        """
        url = "https://example.com/article/42"
        payload = {
            "message_text": f"Check this out: {url}",
            "resources": [],
        }

        with patch("apps.chat.views.dispatch_og") as mock_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client_student.post(
                    self._list_url(), payload, format="json"
                )

            self.assertEqual(resp.status_code, 201, resp.content)
            mock_dispatch.assert_called_once()
            args, kwargs = mock_dispatch.call_args
            self.assertEqual(args[0], resp.data["id"])
            self.assertEqual(args[1], url)

    def test_no_dispatch_without_url(self):
        """Plain text messages must not enqueue any unfurl work."""
        with patch("apps.chat.views.dispatch_og") as mock_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client_student.post(
                    self._list_url(),
                    {"message_text": "no link here", "resources": []},
                    format="json",
                )
            self.assertEqual(resp.status_code, 201, resp.content)
            mock_dispatch.assert_not_called()

    def test_dispatch_only_after_commit(self):
        """If the request transaction is rolled back, no dispatch occurs.

        Without ``execute=True`` ``captureOnCommitCallbacks`` *captures* but
        does not run the on_commit callbacks, so we can assert the queue
        snapshot before deciding whether to flush.
        """
        with patch("apps.chat.views.dispatch_og") as mock_dispatch:
            with self.captureOnCommitCallbacks(execute=False):
                resp = self.client_student.post(
                    self._list_url(),
                    {
                        "message_text": "https://example.com/x",
                        "resources": [],
                    },
                    format="json",
                )
                self.assertEqual(resp.status_code, 201, resp.content)
                mock_dispatch.assert_not_called()

    # ---- edit-path symmetry with create ----

    def _detail_url(self, mid):
        return reverse(
            "group-messages-detail",
            kwargs={"group_pk": self.group.id, "pk": mid},
        )

    def test_edit_adds_url_dispatches_preview(self):
        """An edit that introduces a URL must fire the worker — symmetric
        with the create path; otherwise FE users who fix a typo by adding
        a link would never see the unfurl."""
        message = Messages.objects.create(
            group=self.group, sender_user=self.student, message_text="hi"
        )
        with patch("apps.chat.views.dispatch_og") as mock_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client_student.patch(
                    self._detail_url(message.id),
                    {"message_text": "hi https://example.com/new"},
                    format="json",
                )
            self.assertEqual(resp.status_code, 200, resp.content)
            mock_dispatch.assert_called_once_with(message.id, "https://example.com/new")

    def test_edit_removes_last_url_clears_stale_preview(self):
        """If the edit strips out the only URL, the stale preview row
        must be deleted so list/detail and the broadcast surface
        ``preview:null`` — no zombie cards."""
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="see https://example.com/post",
        )
        MessagePreview.objects.create(
            message=message,
            url="https://example.com/post",
            title="Cached title",
            description="d",
            image_url="https://example.com/i.png",
        )

        with patch("apps.chat.views.dispatch_og") as mock_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client_student.patch(
                    self._detail_url(message.id),
                    {"message_text": "no link anymore"},
                    format="json",
                )
            self.assertEqual(resp.status_code, 200, resp.content)
            mock_dispatch.assert_not_called()

        self.assertFalse(
            MessagePreview.objects.filter(message_id=message.id).exists()
        )
        # REST response also surfaces the cleared state.
        self.assertIsNone(resp.data["preview"])

    def test_edit_keeping_url_does_not_clear_existing_preview(self):
        """Editing surrounding text while the URL stays must NOT drop the
        preview row — the dispatcher's ``update_or_create`` will refresh
        it if the worker finds something new, but in the meantime the
        cached card stays visible."""
        message = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="check https://example.com/post",
        )
        MessagePreview.objects.create(
            message=message,
            url="https://example.com/post",
            title="t",
            description="d",
            image_url="",
        )

        with patch("apps.chat.views.dispatch_og") as mock_dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                resp = self.client_student.patch(
                    self._detail_url(message.id),
                    {"message_text": "please check https://example.com/post"},
                    format="json",
                )
            self.assertEqual(resp.status_code, 200, resp.content)
            mock_dispatch.assert_called_once()

        self.assertTrue(
            MessagePreview.objects.filter(message_id=message.id).exists()
        )


@override_settings(CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS)
class FetchOGDataWorkerTests(TestCase):
    """Drive the worker function directly with an HTML fixture."""

    HTML_FIXTURE = b"""
    <html>
      <head>
        <title>Fallback Title</title>
        <meta property="og:title" content="Hello OG">
        <meta property="og:description" content="A short description.">
        <meta property="og:image" content="/static/cover.png">
      </head>
      <body><p>body</p></body>
    </html>
    """.strip()

    def setUp(self):
        _build_chat_fixtures(self)
        self.message = Messages.objects.create(
            group=self.group,
            sender_user=self.student,
            message_text="see https://example.com/post",
        )

    def _make_response(self, body: bytes, status_code: int = 200, content_type: str = "text/html; charset=utf-8", final_url: str = "https://example.com/post"):
        """Build a fake ``requests.Response``-shaped context manager.

        Only the surface area the worker uses is implemented: ``status_code``,
        ``headers``, ``encoding``, ``url``, ``raw.read``. Returning a
        context-manager mock matches ``with requests.get(...) as resp:``.
        """
        resp = MagicMock()
        resp.status_code = status_code
        resp.headers = {"Content-Type": content_type}
        resp.encoding = "utf-8"
        resp.url = final_url
        raw = MagicMock()
        raw.read.return_value = body
        resp.raw = raw
        ctx = MagicMock()
        ctx.__enter__.return_value = resp
        ctx.__exit__.return_value = False
        return ctx

    def test_og_extraction_worker(self):
        """Worker writes preview row + emits ``message.preview_ready``.

        The HTTP transport, the channel layer, and the Redis client are all
        mocked at module boundaries:

        - ``requests.get`` → returns our HTML fixture, no socket touched.
        - ``get_redis``     → in-memory store so we can assert the cache
                              write happened with the right TTL.
        - ``get_channel_layer`` → captures ``group_send`` so we can inspect
                              the broadcast envelope without a live consumer.
        """
        fake_redis = _FakeRedis()
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()

        url = "https://example.com/post"

        with patch(
            "apps.chat.tasks.requests.get",
            return_value=self._make_response(self.HTML_FIXTURE),
        ) as mock_get, patch(
            "apps.chat.tasks.get_redis", return_value=fake_redis
        ), patch(
            "apps.chat.tasks.get_channel_layer", return_value=fake_layer
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = fetch_og_data(self.message.id, url)

        self.assertEqual(result["status"], "fetched")
        mock_get.assert_called_once()

        # --- DB write ---------------------------------------------------
        preview = MessagePreview.objects.get(message=self.message)
        self.assertEqual(preview.url, url)
        self.assertEqual(preview.title, "Hello OG")
        self.assertEqual(preview.description, "A short description.")
        # Relative og:image is resolved against the final response URL so
        # the front end can render without knowing the origin.
        self.assertEqual(preview.image_url, "https://example.com/static/cover.png")

        # --- Redis cache write ------------------------------------------
        self.assertEqual(len(fake_redis.setex_calls), 1)
        key, ttl, value = fake_redis.setex_calls[0]
        self.assertEqual(key, cache_key_for(url))
        self.assertEqual(ttl, 60 * 60 * 24)
        self.assertEqual(
            json.loads(value),
            {
                "title": "Hello OG",
                "desc": "A short description.",
                "img": "https://example.com/static/cover.png",
            },
        )

        # --- WebSocket broadcast ----------------------------------------
        fake_layer.group_send.assert_called_once()
        group_name, envelope = fake_layer.group_send.call_args.args
        self.assertEqual(group_name, f"group_{self.group.id}")
        self.assertEqual(envelope["type"], "chat.message")
        payload = envelope["payload"]
        # Envelope must match the chat taxonomy contract:
        # event+type duplicated, group_id present, message_id at top level.
        self.assertEqual(payload["event"], "message.preview_ready")
        self.assertEqual(payload["type"], "message.preview_ready")
        self.assertEqual(payload["group_id"], self.group.id)
        self.assertEqual(payload["message_id"], self.message.id)
        self.assertEqual(
            payload["preview"],
            {
                "title": "Hello OG",
                "desc": "A short description.",
                "img": "https://example.com/static/cover.png",
            },
        )

    def test_cache_hit_skips_http_fetch(self):
        """If Redis already has a payload for the URL, we must not refetch.

        Models the spec'd "globally previewed in the last 24h" behaviour:
        the cache is keyed by ``md5(url)``, so two users posting the same
        link only cost one outbound request.
        """
        url = "https://example.com/post"
        cached_payload = {"title": "T", "desc": "D", "img": "I"}
        fake_redis = _FakeRedis(
            initial={cache_key_for(url): json.dumps(cached_payload).encode("utf-8")}
        )
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()

        with patch(
            "apps.chat.tasks.requests.get"
        ) as mock_get, patch(
            "apps.chat.tasks.get_redis", return_value=fake_redis
        ), patch(
            "apps.chat.tasks.get_channel_layer", return_value=fake_layer
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = fetch_og_data(self.message.id, url)

        self.assertEqual(result["status"], "cache_hit")
        mock_get.assert_not_called()
        fake_layer.group_send.assert_called_once()

        preview = MessagePreview.objects.get(message=self.message)
        self.assertEqual(preview.title, "T")
        self.assertEqual(preview.description, "D")
        self.assertEqual(preview.image_url, "I")

    def test_fetch_failure_does_not_persist(self):
        """A non-2xx response must not write a half-baked preview row.

        The user simply doesn't get a preview — better than showing
        ``title=""`` ghosts in the chat UI.
        """
        fake_redis = _FakeRedis()
        fake_layer = MagicMock()
        fake_layer.group_send = AsyncMock()

        with patch(
            "apps.chat.tasks.requests.get",
            return_value=self._make_response(b"nope", status_code=500),
        ), patch(
            "apps.chat.tasks.get_redis", return_value=fake_redis
        ), patch(
            "apps.chat.tasks.get_channel_layer", return_value=fake_layer
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = fetch_og_data(self.message.id, "https://example.com/post")

        self.assertEqual(result["status"], "fetch_failed")
        self.assertFalse(
            MessagePreview.objects.filter(message=self.message).exists()
        )
        fake_layer.group_send.assert_not_called()
        self.assertEqual(fake_redis.setex_calls, [])


class OGExtractorUnitTests(TestCase):
    """Pure-function checks on the URL regex and OG parser."""

    def test_extract_urls_finds_https(self):
        urls = extract_urls("hi see https://example.com/foo and https://b.io")
        self.assertEqual(urls, ["https://example.com/foo", "https://b.io"])

    def test_extract_urls_strips_trailing_punctuation(self):
        self.assertEqual(
            extract_urls("see https://example.com/foo, please."),
            ["https://example.com/foo"],
        )

    def test_extract_urls_dedupes(self):
        text = "https://x.com same https://x.com"
        self.assertEqual(extract_urls(text), ["https://x.com"])

    def test_extract_urls_ignores_non_http_schemes(self):
        # ftp://, javascript:, file:// would be SSRF foot-guns.
        self.assertEqual(extract_urls("ftp://x file:///etc/passwd"), [])

    def test_has_url_short_circuits(self):
        self.assertTrue(has_url("hi http://x.io"))
        self.assertFalse(has_url("plain text"))
        self.assertFalse(has_url(""))
        self.assertFalse(has_url(None))

    def test_cache_key_is_md5_namespaced(self):
        key = cache_key_for("https://example.com")
        self.assertTrue(key.startswith("cache:og:"))
        # md5 hex digest length
        self.assertEqual(len(key), len("cache:og:") + 32)

    def test_parse_og_metadata_prefers_og_then_twitter_then_title(self):
        html = """
        <html><head>
          <title>Plain</title>
          <meta name="twitter:title" content="Twitter T">
          <meta property="og:title" content="OG T">
        </head></html>
        """
        meta = parse_og_metadata(html, base_url="https://x.io/")
        self.assertEqual(meta["title"], "OG T")

    def test_parse_og_metadata_resolves_relative_image(self):
        html = '<html><head><meta property="og:image" content="/i.png"></head></html>'
        meta = parse_og_metadata(html, base_url="https://x.io/a/b")
        self.assertEqual(meta["img"], "https://x.io/i.png")

    def test_parse_og_metadata_handles_empty_html(self):
        self.assertEqual(
            parse_og_metadata("", base_url="https://x.io/"),
            {"title": "", "desc": "", "img": ""},
        )
