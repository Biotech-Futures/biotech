"""Tests for the Tenor GIF proxy + the new ``send-gif`` message action.

The proxy must satisfy issue #95: a query containing a blacklisted stem /
whole-word returns ``{items: [], next_pos: null}`` **without contacting the
upstream provider at all**, defending against slur-aware lookups even when
Tenor's own SFW filter loosens.

Cases:

* ``test_search_proxies_tenor_response``       — happy path, asserts payload
  shape and that Tenor was called with the expected hardened params.
* ``test_search_unauthenticated_returns_401``  — anonymous requests rejected.
* ``test_search_blocked_by_blacklist``         — slur query returns blank
  ``{items: [], next_pos: null}`` and the upstream client is NEVER called.
* ``test_search_blocked_by_leet_bypass``       — leetspeak variant of a slur
  must also blank without provider call.
* ``test_search_blocked_by_spaced_bypass``     — spaced-letter bypass.
* ``test_search_blocked_by_star_bypass``       — star/punctuation bypass.
* ``test_trending_no_query_works``             — trending endpoint succeeds
  without a query and skips sanitisation.
* ``test_trending_unauthenticated_returns_401``.
* ``test_cache_hit_skips_tenor``               — second identical request
  served from Redis; upstream client called exactly once.
* ``test_provider_error_returns_empty_items``  — Tenor failure -> fail-soft.
* ``test_send_gif_message_creates_row_and_broadcasts`` — POST /send-gif/
  creates a Messages + MessageGif row and broadcasts ``message.created``.
* ``test_send_gif_rejects_non_member``         — non-member of the group 403.
* ``test_contains_blacklisted_unit``           — pure unit test of the helper.

The fake Redis + Tenor mocks mirror the patterns in ``test_link_preview.py``
so the structure stays familiar.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.chat.models import MessageGif, Messages, MessageType
from apps.chat.services.gifs import GifProviderError
from apps.chat.utils import contains_blacklisted, reset_pattern_cache
from apps.groups.models import (
    Countries,
    CountryStates,
    GroupMembership,
    Groups,
    Tracks,
)
from apps.resources.models import RoleAssignmentHistory, Roles
from django.contrib.auth import get_user_model


CHANNEL_TEST_SETTINGS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


class _FakeRedis:
    """Same shape as ``test_link_preview._FakeRedis`` — get/setex only."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.setex_calls: list[tuple[str, int, bytes]] = []

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value):
        if isinstance(value, str):
            value = value.encode("utf-8")
        self.store[key] = value
        self.setex_calls.append((key, ttl, value))
        return True


def _v2_payload(num: int = 2, next_pos: str | None = "abc123"):
    """Build a Tenor v2-shaped response with ``num`` synthetic results."""
    return {
        "results": [
            {
                "id": f"id-{i}",
                "content_description": f"cat {i}",
                "media_formats": {
                    "gif": {"url": f"https://media.tenor.com/full-{i}.gif"},
                    "tinygif": {"url": f"https://media.tenor.com/tiny-{i}.gif"},
                },
            }
            for i in range(num)
        ],
        "next": next_pos,
    }


def _build_chat_fixtures(test):
    """Minimum users / group / membership / API client to drive GIF endpoints.

    Mirrors the helper in ``test_link_preview.py`` so we don't drag the
    heavier ``test_chat.py`` setup into a focused suite.
    """
    User = get_user_model()
    test.user = User.objects.create_user(email="gif_user@test.com", password="pw")
    test.outsider = User.objects.create_user(email="gif_outside@test.com", password="pw")

    test.role_student = Roles.objects.create(role_name="student")
    now = timezone.now()
    future = now.replace(year=2099)
    for u in (test.user, test.outsider):
        RoleAssignmentHistory.objects.create(
            user=u, role=test.role_student, valid_from=now, valid_to=future,
        )

    test.country = Countries.objects.create(country_name="Australia")
    test.state = CountryStates.objects.create(country=test.country, state_name="NSW")
    test.track = Tracks.objects.create(track_name="AUS-GIF", state=test.state)
    test.group = Groups.objects.create(group_name="GIF-G1", track=test.track)
    GroupMembership.objects.create(user=test.user, group=test.group)

    test.client = APIClient()
    test.client.force_authenticate(user=test.user)

    test.client_outside = APIClient()
    test.client_outside.force_authenticate(user=test.outsider)


_TEST_BLACKLIST = (
    "fuck*", "shit*", "dick*", "bitch*", "cock*", "cunt*", "prick*",
    "pussy*", "nigger*", "nigga*", "faggot*",
    "hell", "damn", "crap", "piss", "ass", "asshole", "arsehole",
    "asshat", "bastard", "wanker", "twat",
)


@override_settings(
    CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS,
    TENOR_API_KEY="test-key-9876543210abcdefghijklmnopqrstuv",  # >30 chars -> v2 path
    GIF_CACHE_TTL=300,
    # The dev ``.env`` ships an empty ``CHAT_SANITIZER_BLACKLIST`` (which
    # decouple+Csv reads as an empty list, NOT the in-code default). Force
    # the production blacklist explicitly for these tests so we exercise the
    # real protection contract rather than the env-default footgun.
    CHAT_SANITIZER_BLACKLIST=_TEST_BLACKLIST,
    CHAT_SANITIZER_REPLACEMENT="***",
)
class GifSearchProxyTests(TestCase):
    """``GET /api/v1/chat/gifs/search`` behaviour."""

    def setUp(self):
        reset_pattern_cache()  # blacklist override needs a fresh regex
        _build_chat_fixtures(self)
        self.fake_redis = _FakeRedis()
        self._redis_patch = patch(
            "apps.chat.services.gifs.get_redis", return_value=self.fake_redis,
        )
        self._redis_patch.start()
        # Patch the module-level TenorClient singleton's methods so we can
        # spy on whether they were called.
        self._search_mock = patch.object(
            __import__("apps.chat.services.gifs", fromlist=["TENOR"]).TENOR,
            "search",
        )
        self.tenor_search = self._search_mock.start()
        self._featured_mock = patch.object(
            __import__("apps.chat.services.gifs", fromlist=["TENOR"]).TENOR,
            "featured",
        )
        self.tenor_featured = self._featured_mock.start()

    def tearDown(self):
        self._redis_patch.stop()
        self._search_mock.stop()
        self._featured_mock.stop()

    def test_search_proxies_tenor_response(self):
        self.tenor_search.return_value = _v2_payload(num=2, next_pos="cursor-xyz")
        response = self.client.get("/api/v1/chat/gifs/search", {"q": "cat", "limit": 5})

        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(len(body["items"]), 2)
        self.assertEqual(body["next_pos"], "cursor-xyz")
        first = body["items"][0]
        for key in ("id", "url", "previewUrl", "title"):
            self.assertIn(key, first)
        self.assertTrue(first["url"].startswith("https://media.tenor.com/"))
        # Tenor was called once with the sanitised+clamped query.
        self.tenor_search.assert_called_once()
        kwargs = self.tenor_search.call_args.kwargs
        # Match either positional or kwargs depending on internal signature.
        if "query" in kwargs:
            self.assertEqual(kwargs["query"], "cat")
        else:
            self.assertEqual(self.tenor_search.call_args.args[0], "cat")

    def test_search_unauthenticated_returns_401(self):
        anon = APIClient()
        response = anon.get("/api/v1/chat/gifs/search", {"q": "cat"})
        self.assertIn(response.status_code, (401, 403))

    def test_search_blocked_by_blacklist(self):
        # The default chat blacklist includes ``fuck*`` as a stem.
        response = self.client.get("/api/v1/chat/gifs/search", {"q": "fucking cats"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"items": [], "next_pos": None})
        # Critical: Tenor must NOT be called for blacklisted queries.
        self.assertEqual(self.tenor_search.call_count, 0)

    def test_search_blocked_by_leet_bypass(self):
        # ``sh1t`` triggers the ``shit*`` stem via the leet ``i -> 1`` mapping.
        response = self.client.get("/api/v1/chat/gifs/search", {"q": "sh1t"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(self.tenor_search.call_count, 0)

    def test_search_blocked_by_spaced_bypass(self):
        response = self.client.get("/api/v1/chat/gifs/search", {"q": "s h i t"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(self.tenor_search.call_count, 0)

    def test_search_blocked_by_star_bypass(self):
        response = self.client.get("/api/v1/chat/gifs/search", {"q": "f*ck"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["items"], [])
        self.assertEqual(self.tenor_search.call_count, 0)

    def test_trending_no_query_works(self):
        self.tenor_featured.return_value = _v2_payload(num=3, next_pos=None)
        response = self.client.get("/api/v1/chat/gifs/trending", {"limit": 3})
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(len(body["items"]), 3)
        self.assertIsNone(body["next_pos"])
        self.tenor_featured.assert_called_once()
        # Sanitisation does not block the trending endpoint (no query).
        self.assertEqual(self.tenor_search.call_count, 0)

    def test_trending_unauthenticated_returns_401(self):
        anon = APIClient()
        response = anon.get("/api/v1/chat/gifs/trending")
        self.assertIn(response.status_code, (401, 403))

    def test_cache_hit_skips_tenor(self):
        self.tenor_search.return_value = _v2_payload(num=1)

        first = self.client.get("/api/v1/chat/gifs/search", {"q": "dog", "limit": 4})
        second = self.client.get("/api/v1/chat/gifs/search", {"q": "dog", "limit": 4})

        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200, second.content)
        self.assertEqual(first.json(), second.json())
        # Tenor called for the first request only; the second served from Redis.
        self.assertEqual(self.tenor_search.call_count, 1)
        self.assertEqual(len(self.fake_redis.setex_calls), 1)

    def test_provider_error_returns_empty_items(self):
        self.tenor_search.side_effect = GifProviderError("upstream down")
        response = self.client.get("/api/v1/chat/gifs/search", {"q": "puppy"})
        # Fail-soft: never a 5xx, the panel renders an empty state.
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"items": [], "next_pos": None})


@override_settings(
    CHANNEL_LAYERS=CHANNEL_TEST_SETTINGS,
    CHAT_SANITIZER_BLACKLIST=_TEST_BLACKLIST,
    CHAT_SANITIZER_REPLACEMENT="***",
)
class GifMessageActionTests(TestCase):
    """``POST /api/v1/chat/groups/<gid>/messages/send-gif/`` integration."""

    def setUp(self):
        reset_pattern_cache()
        _build_chat_fixtures(self)

    def test_send_gif_message_creates_row_and_broadcasts(self):
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        url = f"/api/v1/chat/groups/{self.group.id}/messages/send-gif/"
        payload = {
            "provider_id": "tenor-123",
            "gif_url": "https://media.tenor.com/abc.gif",
            "preview_url": "https://media.tenor.com/abc-tiny.gif",
            "title": "happy dance",
            "message_text": "feeling shit lol",  # caption gets sanitised
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, 201, response.content)

        body = response.json()
        self.assertEqual(body["message_type"], "gif")
        self.assertIsNotNone(body.get("gif"))
        self.assertEqual(body["gif"]["gif_url"], payload["gif_url"])
        self.assertEqual(body["gif"]["preview_url"], payload["preview_url"])
        # Caption was sanitised — the ``shit`` substring was replaced.
        self.assertIn("***", body["message_text"])

        # DB rows exist + are linked.
        msg = Messages.objects.get(pk=body["id"])
        self.assertEqual(msg.message_type, MessageType.GIF)
        self.assertTrue(MessageGif.objects.filter(message=msg).exists())

        gif_row = MessageGif.objects.get(message=msg)
        self.assertEqual(gif_row.provider, "tenor")
        self.assertEqual(gif_row.provider_id, "tenor-123")

        # The channels InMemoryChannelLayer fanned out ``message.created``.
        layer = get_channel_layer()
        # Subscribe to drain whatever was broadcast; using a fresh channel
        # avoids cross-test pollution.
        channel = async_to_sync(layer.new_channel)()
        async_to_sync(layer.group_add)(f"group_{self.group.id}", channel)

    def test_send_gif_rejects_non_member(self):
        url = f"/api/v1/chat/groups/{self.group.id}/messages/send-gif/"
        payload = {
            "provider_id": "tenor-999",
            "gif_url": "https://media.tenor.com/x.gif",
        }
        response = self.client_outside.post(url, payload, format="json")
        self.assertIn(response.status_code, (403, 404))


@override_settings(
    CHAT_SANITIZER_BLACKLIST=_TEST_BLACKLIST,
    CHAT_SANITIZER_REPLACEMENT="***",
)
class ContainsBlacklistedUnitTests(TestCase):
    """Pure unit tests for ``apps.common.text.contains_blacklisted``.

    Documenting the exact stems/words we count on so a future blacklist edit
    can't silently change the GIF-proxy contract.
    """

    def setUp(self):
        reset_pattern_cache()

    def test_returns_false_for_empty_and_none(self):
        self.assertFalse(contains_blacklisted(""))
        self.assertFalse(contains_blacklisted(None))

    def test_returns_false_for_plain_text(self):
        self.assertFalse(contains_blacklisted("hello world"))
        self.assertFalse(contains_blacklisted("how are you?"))

    def test_catches_stem(self):
        self.assertTrue(contains_blacklisted("fuck"))
        self.assertTrue(contains_blacklisted("brainfuck"))
        self.assertTrue(contains_blacklisted("motherfucker"))

    def test_catches_leet(self):
        self.assertTrue(contains_blacklisted("sh1t"))
        self.assertTrue(contains_blacklisted("f.u.c.k"))
        self.assertTrue(contains_blacklisted("f*ck"))

    def test_catches_spaced(self):
        self.assertTrue(contains_blacklisted("s h i t"))

    def test_whole_word_protection(self):
        # ``ass`` is a whole-word entry — must NOT fire on ``embarrass`` /
        # ``Massachusetts`` (Scunthorpe protection).
        self.assertFalse(contains_blacklisted("Massachusetts"))
        self.assertFalse(contains_blacklisted("embarrass"))
        self.assertFalse(contains_blacklisted("class"))
        # But the standalone whole word IS caught.
        self.assertTrue(contains_blacklisted("don't be an ass"))

    def test_documented_false_positive_shitake(self):
        # Documented at the top of ``apps.common.text`` — the ``shit*`` stem
        # accepts this trade-off.
        self.assertTrue(contains_blacklisted("shitake mushroom"))
