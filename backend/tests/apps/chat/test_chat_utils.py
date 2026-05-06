"""Unit tests for ``apps.chat.utils.sanitize_text`` and the consumer's
defensive guards.

``sanitize_text`` is a pure helper, so these tests deliberately do not
touch the database, channels, or DRF — being independently testable is
the whole point of moving the rule out of the view layer (SRP).
"""

from django.test import SimpleTestCase, override_settings

from apps.chat.utils import (
    DEFAULT_BLACKLIST,
    sanitize_text,
    reset_pattern_cache,
)


@override_settings(
    CHAT_SANITIZER_BLACKLIST=["shit*", "fuck*", "cunt*", "bitch*"],
    CHAT_SANITIZER_REPLACEMENT="***",
)
class SanitizeTextStemTests(SimpleTestCase):
    def setUp(self):
        reset_pattern_cache()

    def tearDown(self):
        reset_pattern_cache()

    # ---- type-contract guarantees ------------------------------------

    def test_none_is_coerced_to_empty_string(self):
        self.assertEqual(sanitize_text(None), "")

    def test_non_string_raises_type_error(self):
        with self.assertRaises(TypeError):
            sanitize_text(123)
        with self.assertRaises(TypeError):
            sanitize_text(["bullshit"])
        with self.assertRaises(TypeError):
            sanitize_text({"text": "hi"})

    def test_empty_string_passes_through(self):
        self.assertEqual(sanitize_text(""), "")

    def test_clean_text_is_unchanged(self):
        msg = "Hello world, how is your day?"
        self.assertEqual(sanitize_text(msg), msg)

    # ---- direct profanity --------------------------------------------

    def test_exact_word_is_replaced(self):
        self.assertEqual(sanitize_text("shit"), "***")
        self.assertEqual(sanitize_text("fuck"), "***")

    def test_replacement_inside_sentence_keeps_surroundings(self):
        self.assertEqual(sanitize_text("oh shit that broke"), "oh *** that broke")

    def test_trailing_punctuation_is_preserved(self):
        # The host-word eater is letters+digits only, so trailing ``!`` /
        # ``,`` / ``.`` survives.
        self.assertEqual(sanitize_text("oh, shit!"), "oh, ***!")

    # ---- substring containment (the user's headline examples) --------

    def test_substring_bullshit_is_replaced(self):
        self.assertEqual(sanitize_text("bullshit"), "***")

    def test_substring_shithole_is_replaced(self):
        self.assertEqual(sanitize_text("shithole"), "***")

    def test_substring_fucker_is_replaced(self):
        self.assertEqual(sanitize_text("fucker"), "***")

    def test_substring_brainfuck_is_replaced(self):
        self.assertEqual(sanitize_text("brainfuck"), "***")

    def test_motherfucker_is_replaced_whole(self):
        # The host-word eater swallows the surrounding letters so the whole
        # token disappears, not just the stem.
        self.assertEqual(sanitize_text("you motherfucker"), "you ***")

    def test_clusterfuck_is_replaced_whole(self):
        self.assertEqual(sanitize_text("clusterfuck"), "***")

    # ---- leetspeak ---------------------------------------------------

    def test_leet_bull5h1t(self):
        self.assertEqual(sanitize_text("bull5h1t"), "***")

    def test_leet_5hlthole(self):
        # ``l`` standing in for ``i`` (visual swap).
        self.assertEqual(sanitize_text("5hlthole"), "***")

    def test_leet_with_punctuation(self):
        self.assertEqual(sanitize_text("sh!t"), "***")

    def test_leet_dollar_sign_for_s(self):
        self.assertEqual(sanitize_text("$hit"), "***")

    def test_partial_censor_with_asterisk(self):
        # ``f*ck`` should still match because the asterisk is a valid
        # leet stand-in for any letter slot.
        self.assertEqual(sanitize_text("f*ck"), "***")
        self.assertEqual(sanitize_text("sh*t"), "***")

    def test_repeated_letters(self):
        # The letter classes are ``+`` quantified so ``shiiiit`` and
        # ``fuuuck`` collapse onto the same stem.
        self.assertEqual(sanitize_text("shiiiit"), "***")
        self.assertEqual(sanitize_text("fuuuck"), "***")

    # ---- spaced-out profanity ----------------------------------------

    def test_spaced_letters(self):
        self.assertEqual(sanitize_text("s h i t happens"), "*** happens")

    def test_dotted_letters(self):
        self.assertEqual(sanitize_text("s.h.i.t"), "***")

    # ---- multiple matches in one message -----------------------------

    def test_multiple_matches_are_all_replaced(self):
        result = sanitize_text("shit and bullshit and brainfuck")
        self.assertEqual(result, "*** and *** and ***")


@override_settings(
    CHAT_SANITIZER_BLACKLIST=["hell", "ass", "damn"],
    CHAT_SANITIZER_REPLACEMENT="***",
)
class SanitizeTextWholeWordTests(SimpleTestCase):
    """Whole-word entries (no trailing ``*``) must use letter-boundary
    anchors so they don't fire on innocent substrings."""

    def setUp(self):
        reset_pattern_cache()

    def tearDown(self):
        reset_pattern_cache()

    def test_whole_word_hell_is_replaced(self):
        self.assertEqual(sanitize_text("go to hell"), "go to ***")

    def test_hello_is_not_flagged(self):
        # The whole-word arm is ``(?<![A-Za-z])hell(?![A-Za-z])`` so
        # ``hello`` (with ``o`` after ``l``) is left alone.
        self.assertEqual(sanitize_text("hello there"), "hello there")
        self.assertEqual(sanitize_text("helmet, hellish, hellbender"), "helmet, hellish, hellbender")

    def test_ass_does_not_flag_innocuous_words(self):
        for safe in ["class", "passive", "Massachusetts", "embarrass", "compass"]:
            self.assertEqual(sanitize_text(safe), safe, safe)

    def test_ass_alone_is_replaced(self):
        self.assertEqual(sanitize_text("kick ass"), "kick ***")


class SanitizeTextDefaultsTests(SimpleTestCase):
    """Smoke tests against the shipped default blacklist (no override)."""

    def setUp(self):
        reset_pattern_cache()

    def tearDown(self):
        reset_pattern_cache()

    def test_default_blacklist_pins_combined_coverage(self):
        # Sanity-check the full combined blacklist so future edits can't
        # silently drop a stem. Stems first, then whole-words.
        for stem in [
            "fuck*", "shit*", "dick*", "bitch*", "cock*", "cunt*", "prick*",
            "pussy*", "nigger*", "nigga*", "faggot*",
        ]:
            self.assertIn(stem, DEFAULT_BLACKLIST, stem)
        for whole in [
            "hell", "damn", "crap", "piss", "ass",
            "asshole", "arsehole", "asshat", "bastard", "wanker", "twat",
        ]:
            self.assertIn(whole, DEFAULT_BLACKLIST, whole)

    def test_default_catches_user_headline_examples(self):
        for bad in [
            "bullshit", "shithole", "fucker", "brainfuck",
            "bull5h1t", "5hlthole", "sh!t", "f*ck",
        ]:
            self.assertEqual(sanitize_text(bad), "***", bad)

    def test_default_catches_combined_stems(self):
        # Words drawn from the merged list — covers the additions on top of
        # the original file (pussy / nigger / faggot stems). Stems require
        # the literal stem letters to appear in sequence (with leet/spacing
        # tolerance); they do NOT do English-aware morphology, so plurals
        # that replace letters (``pussy`` -> ``pussies``) need separate
        # blacklist entries if you want to catch them.
        for bad in [
            "pussy", "pu55y", "pussycat",  # pussy* stem (cat is a known FP)
            "nigger", "niggerface", "n1gger",  # nigger* stem
            "nigga", "niggas", "niggah", "n1gga", "n!gg4",  # nigga* stem
            "faggot", "faggots", "faggotry",  # faggot* stem
        ]:
            self.assertEqual(sanitize_text(bad), "***", bad)

    def test_default_catches_default_whole_words(self):
        # ``hell`` / ``ass`` / ``damn`` are whole-words by default — strict
        # boundary, so innocent substrings are still untouched.
        self.assertEqual(sanitize_text("damn that hurt"), "*** that hurt")
        self.assertEqual(sanitize_text("hello world"), "hello world")
        self.assertEqual(sanitize_text("class is over"), "class is over")


class SanitizeTextOverrideArgsTests(SimpleTestCase):
    """The ``blacklist`` / ``replacement`` keyword args allow callers to
    override settings on a per-call basis (handy for one-off tools)."""

    def setUp(self):
        reset_pattern_cache()

    def tearDown(self):
        reset_pattern_cache()

    def test_per_call_blacklist_override(self):
        self.assertEqual(
            sanitize_text("foo bar baz", blacklist=["foo*"], replacement="***"),
            "*** bar baz",
        )

    def test_per_call_replacement_override(self):
        self.assertEqual(
            sanitize_text("oh shit", blacklist=["shit*"], replacement="[redacted]"),
            "oh [redacted]",
        )


class GroupChatConsumerDefensiveTests(SimpleTestCase):
    """Direct unit tests for the consumer's defensive guards. We poke at
    the consumer's pure async logic without spinning up a live websocket
    transport — that keeps these tests fast and immune to async-test
    infrastructure quirks across Channels/asgiref versions."""

    def _make_consumer(self, group_id_kwarg):
        from apps.chat.management.consumers import GroupChatConsumer

        consumer = GroupChatConsumer()
        consumer.scope = {
            "type": "websocket",
            "url_route": {"kwargs": {"group_id": group_id_kwarg}},
            "user": None,
        }
        closed = {}

        async def fake_close(code=None):
            closed["code"] = code

        consumer.close = fake_close
        consumer._closed = closed
        return consumer

    def test_connect_rejects_non_numeric_group_id(self):
        import asyncio

        consumer = self._make_consumer("not-a-number")
        asyncio.run(consumer.connect())
        self.assertEqual(consumer._closed.get("code"), 4400)

    def test_connect_rejects_missing_group_id(self):
        import asyncio

        consumer = self._make_consumer(None)
        asyncio.run(consumer.connect())
        self.assertEqual(consumer._closed.get("code"), 4400)

    def test_receive_json_silently_drops_non_dict(self):
        """A list / string / number payload must not crash the consumer.
        Previously ``content.get("content")`` would raise AttributeError;
        now the consumer should bail out cleanly without sending."""
        import asyncio
        from apps.chat.management.consumers import GroupChatConsumer

        consumer = GroupChatConsumer()
        consumer.scope = {
            "type": "websocket",
            "user": type("U", (), {"id": 1})(),
        }
        consumer.group_id = 1
        consumer.room_group_name = "group_1"

        sent = []

        class FakeChannelLayer:
            async def group_send(self, name, msg):
                sent.append((name, msg))

        consumer.channel_layer = FakeChannelLayer()

        for bad_payload in [["not", "a", "dict"], "string", 42, None]:
            asyncio.run(consumer.receive_json(bad_payload))
        self.assertEqual(sent, [])

    def test_receive_json_still_broadcasts_well_formed_dict(self):
        import asyncio
        from apps.chat.management.consumers import GroupChatConsumer

        consumer = GroupChatConsumer()
        consumer.scope = {
            "type": "websocket",
            "user": type("U", (), {"id": 7})(),
        }
        consumer.group_id = 1
        consumer.room_group_name = "group_1"

        sent = []

        class FakeChannelLayer:
            async def group_send(self, name, msg):
                sent.append((name, msg))

        consumer.channel_layer = FakeChannelLayer()
        asyncio.run(consumer.receive_json({"content": "hi", "resource_ids": [1, 2]}))
        self.assertEqual(len(sent), 1)
        name, msg = sent[0]
        self.assertEqual(name, "group_1")
        self.assertEqual(msg["payload"]["message"]["text"], "hi")
        self.assertEqual(msg["payload"]["message"]["resource_ids"], [1, 2])
        self.assertEqual(msg["payload"]["message"]["sender_id"], 7)

    def test_receive_json_sanitises_text_before_broadcast(self):
        import asyncio
        from apps.chat.management.consumers import GroupChatConsumer

        consumer = GroupChatConsumer()
        consumer.scope = {
            "type": "websocket",
            "user": type("U", (), {"id": 7})(),
        }
        consumer.group_id = 1
        consumer.room_group_name = "group_1"

        sent = []

        class FakeChannelLayer:
            async def group_send(self, name, msg):
                sent.append((name, msg))

        consumer.channel_layer = FakeChannelLayer()
        with override_settings(
            CHAT_SANITIZER_BLACKLIST=["shit*"],
            CHAT_SANITIZER_REPLACEMENT="***",
        ):
            reset_pattern_cache()
            asyncio.run(consumer.receive_json({"content": "this is bullshit"}))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0][1]["payload"]["message"]["text"], "this is ***")
