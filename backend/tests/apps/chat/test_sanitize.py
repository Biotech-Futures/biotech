"""Unit tests for ``apps.chat.utils.sanitize_text``.

Pure-Python tests — no DB, no Channels, no DRF. The whole point of putting the
function in ``utils.py`` is to exercise the sanitisation logic in isolation.
"""

import unittest

from apps.chat.utils import (
    DEFAULT_BLACKLIST,
    DEFAULT_REPLACEMENT,
    sanitize_text,
)


class SanitizeTextTests(unittest.TestCase):
    def test_empty_string_returned_unchanged(self):
        self.assertEqual(sanitize_text(""), "")

    def test_none_coerced_to_empty_string(self):
        self.assertEqual(sanitize_text(None), "")

    def test_clean_text_returned_unchanged(self):
        self.assertEqual(
            sanitize_text("hello world, how are you?"),
            "hello world, how are you?",
        )

    def test_non_string_raises_typeerror(self):
        # Reviewer: signature claims str, must actually enforce it.
        with self.assertRaises(TypeError):
            sanitize_text(123)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            sanitize_text(["hi"])  # type: ignore[arg-type]

    def test_default_replacement_token(self):
        self.assertEqual(DEFAULT_REPLACEMENT, "***")

    def test_single_swear_replaced(self):
        self.assertEqual(
            sanitize_text("this is shit"),
            f"this is {DEFAULT_REPLACEMENT}",
        )

    def test_case_insensitive(self):
        self.assertEqual(sanitize_text("Shit ShIt SHIT"), "*** *** ***")

    def test_multiple_swears_in_one_message(self):
        self.assertEqual(
            sanitize_text("what the hell is this shit"),
            "what the *** is this ***",
        )

    def test_punctuation_around_swear_preserved(self):
        self.assertEqual(sanitize_text("oh, shit!"), "oh, ***!")
        self.assertEqual(sanitize_text("(hell)"), "(***)")

    def test_whole_word_entries_are_scunthorpe_safe(self):
        # Whole-word entries (hell, damn, ass, ...) keep their letter-boundary
        # protection so they don't false-positive on common English words.
        # Stems (fuck*, shit*, ...) intentionally DO match anywhere — see
        # ``StemMatchingTests`` below.
        self.assertEqual(sanitize_text("classic"), "classic")  # no "ass" boundary
        self.assertEqual(sanitize_text("damnation"), "damnation")
        self.assertEqual(sanitize_text("hellish"), "hellish")
        self.assertEqual(sanitize_text("hello world"), "hello world")
        self.assertEqual(sanitize_text("passive learning"), "passive learning")
        self.assertEqual(sanitize_text("Massachusetts"), "Massachusetts")
        self.assertEqual(sanitize_text("embarrass"), "embarrass")

    def test_stem_replaces_whole_host_word_in_one_pass(self):
        # ``fucking`` is not its own entry — the ``fuck*`` stem catches it and
        # the host-word gobbler eats the ``ing`` suffix in the same match.
        self.assertEqual(sanitize_text("you are fucking late"), "you are *** late")

    def test_custom_blacklist_overrides_default(self):
        self.assertEqual(
            sanitize_text("bananas are great", blacklist=["bananas"]),
            "*** are great",
        )
        # When a custom blacklist is supplied, the default words pass through.
        self.assertEqual(
            sanitize_text("hell yeah bananas", blacklist=["bananas"]),
            "hell yeah ***",
        )

    def test_empty_blacklist_returns_text_unchanged(self):
        self.assertEqual(
            sanitize_text("hell shit damn", blacklist=[]),
            "hell shit damn",
        )

    def test_custom_replacement_token(self):
        self.assertEqual(
            sanitize_text("oh shit", replacement="[REDACTED]"),
            "oh [REDACTED]",
        )

    def test_unicode_text_preserved(self):
        self.assertEqual(sanitize_text("你好 hell 世界"), "你好 *** 世界")


class BypassResistanceTests(unittest.TestCase):
    """Bypass attempts that the reviewer flagged as escapable in the original."""

    def test_leetspeak_digit_substitution(self):
        for variant in ["sh1t", "5h1t", "5h17", "$h1t", "shi7"]:
            with self.subTest(variant=variant):
                self.assertEqual(sanitize_text(variant), DEFAULT_REPLACEMENT)

    def test_leetspeak_symbol_substitution(self):
        for variant in ["sh!t", "$hit", "fuc|<".replace("|<", "k"), "@sshole", "h3ll"]:
            with self.subTest(variant=variant):
                self.assertEqual(sanitize_text(variant), DEFAULT_REPLACEMENT)

    def test_censoring_stars(self):
        for variant in ["f*ck", "sh*t", "b*tch", "h*ll"]:
            with self.subTest(variant=variant):
                self.assertEqual(sanitize_text(variant), DEFAULT_REPLACEMENT)

    def test_punctuation_injection(self):
        for variant in ["s.h.i.t", "s*h*i*t", "f.u.c.k", "h-e-l-l"]:
            with self.subTest(variant=variant):
                self.assertEqual(sanitize_text(variant), DEFAULT_REPLACEMENT)

    def test_spaced_profanity(self):
        # Up to MAX_GAP_BETWEEN_LETTERS=2 non-word chars between letters.
        self.assertEqual(sanitize_text("s h i t"), "***")
        self.assertEqual(sanitize_text("h e l l"), "***")

    def test_repeated_letters_collapsed(self):
        self.assertEqual(sanitize_text("shiiit"), "***")
        self.assertEqual(sanitize_text("fuuuck"), "***")
        self.assertEqual(sanitize_text("hellllo"), "hellllo")  # NOT a match — boundary

    def test_bypass_in_sentence_context(self):
        self.assertEqual(
            sanitize_text("this is sh1t and that is f*ck"),
            "this is *** and that is ***",
        )

    def test_huge_gaps_dont_match(self):
        # 3+ gap chars between letters should NOT match — prevents false
        # positives on text that just happens to contain the letters in order.
        self.assertEqual(
            sanitize_text("she is happy in this town"),  # s...h...i...t... (gaps too large)
            "she is happy in this town",
        )


class StemMatchingTests(unittest.TestCase):
    """Stems (entries with a trailing ``*``) match anywhere inside a word.

    A single ``fuck*`` entry catches every variant: ``fucker``, ``fucking``,
    ``motherfucker``, ``brainfuck``, ``clusterfuck``, ``f*ck``, etc. — no need
    to enumerate compounds. This is the regression test for the design
    decision "don't hardcode every compound in utils.py".
    """

    def test_shit_stem_catches_compounds(self):
        self.assertEqual(sanitize_text("that's bullshit"), "that's ***")
        self.assertEqual(sanitize_text("this shithole town"), "this *** town")
        self.assertEqual(sanitize_text("a real shitstorm"), "a real ***")
        self.assertEqual(sanitize_text("shithead"), "***")
        self.assertEqual(sanitize_text("horseshit"), "***")
        self.assertEqual(sanitize_text("complete shitshow"), "complete ***")

    def test_fuck_stem_catches_compounds(self):
        self.assertEqual(sanitize_text("brainfuck programming"), "*** programming")
        self.assertEqual(sanitize_text("motherfucker"), "***")
        self.assertEqual(sanitize_text("clusterfuck"), "***")
        self.assertEqual(sanitize_text("fuckface"), "***")
        self.assertEqual(sanitize_text("fucking late"), "*** late")
        self.assertEqual(sanitize_text("fucked up"), "*** up")

    def test_dick_stem_catches_compounds(self):
        self.assertEqual(sanitize_text("don't be a dickhead"), "don't be a ***")
        self.assertEqual(sanitize_text("dickface"), "***")

    def test_bitch_stem_catches_compounds(self):
        self.assertEqual(sanitize_text("stop bitching"), "stop ***")
        self.assertEqual(sanitize_text("bitchy mood"), "*** mood")

    def test_stem_eats_whole_host_word(self):
        # The replacement consumes the surrounding letters too, so we get
        # "***" not "mother***er" or "***ake".
        self.assertEqual(sanitize_text("motherfucker"), "***")
        self.assertEqual(sanitize_text("bullshit"), "***")
        self.assertEqual(sanitize_text("brainfuck"), "***")

    def test_stem_with_leetspeak(self):
        # The user-cited variants from the review thread. Letter/digit leet
        # in the stem AND in the surrounding host word both work.
        self.assertEqual(sanitize_text("bull5h1t"), "***")
        self.assertEqual(sanitize_text("5hlthole"), "***")  # l standing in for i
        self.assertEqual(sanitize_text("m0therfucker"), "***")
        self.assertEqual(sanitize_text("br1nfuck"), "***")  # digit-leet prefix

    def test_stem_with_spacing(self):
        # The up-to-2-char gap policy applies *inside* the stem itself
        # (between adjacent letters of the canonical word).
        self.assertEqual(sanitize_text("oh s h i t"), "oh ***")
        self.assertEqual(sanitize_text("oh sh.it"), "oh ***")
        self.assertEqual(sanitize_text("oh sh i t"), "oh ***")

    def test_stem_separated_from_host_word_is_partial(self):
        # When the stem is glued onto a host word with NO separator the whole
        # thing is replaced (host-word gobbler eats the surrounding letters).
        # When a separator (``.``, ``-``, ``_``, space) sits between the
        # prefix and the stem, the prefix word fragment is preserved — the
        # gobbler intentionally does not cross separators so trailing
        # punctuation in ``oh, shit!`` survives.
        self.assertEqual(sanitize_text("bullshit"), "***")        # glued
        self.assertEqual(sanitize_text("bull.shit"), "bull.***")  # split by .
        self.assertEqual(sanitize_text("bull shit"), "bull ***")  # split by space
        self.assertEqual(sanitize_text("shit-hole"), "***-hole")  # suffix split

    def test_stems_do_not_match_unrelated_words(self):
        # Most English words don't contain f-u-c-k or s-h-i-t in order, so
        # stems rarely false-positive. Confirm a few common ones.
        self.assertEqual(sanitize_text("brainstorm meeting"), "brainstorm meeting")
        self.assertEqual(sanitize_text("asset management"), "asset management")
        self.assertEqual(sanitize_text("perfect attendance"), "perfect attendance")
        self.assertEqual(sanitize_text("focus group"), "focus group")
        self.assertEqual(sanitize_text("ship arrived"), "ship arrived")
        self.assertEqual(sanitize_text("shift workers"), "shift workers")

    def test_documented_false_positives_are_accepted_tradeoff(self):
        # These are the known false positives noted in utils.py module
        # docstring. Locking them in as a test makes the tradeoff visible —
        # if a future refactor changes this behaviour the test fails loudly
        # and forces the reviewer to update the docstring too.
        self.assertEqual(sanitize_text("shitake mushrooms"), "*** mushrooms")
        self.assertEqual(sanitize_text("Scunthorpe is a town"), "*** is a town")
        self.assertEqual(sanitize_text("peacock feathers"), "*** feathers")


class SettingsIntegrationTests(unittest.TestCase):
    """Verify the settings hook works (using direct override, no Django needed)."""

    def test_default_blacklist_constant_is_a_tuple(self):
        # Sanity check: the module-level default is the documented contract.
        # Stems carry the trailing ``*`` marker; whole-words don't.
        self.assertIsInstance(DEFAULT_BLACKLIST, tuple)
        self.assertIn("hell", DEFAULT_BLACKLIST)
        self.assertIn("fuck*", DEFAULT_BLACKLIST)
        self.assertIn("shit*", DEFAULT_BLACKLIST)
        # No bare "fuck" / "shit" — those are stems now.
        self.assertNotIn("fuck", DEFAULT_BLACKLIST)
        self.assertNotIn("shit", DEFAULT_BLACKLIST)


# ---------------------------------------------------------------------------
# Django-aware tests for the env/settings override path.
# These import ``override_settings`` so they MUST be a Django TestCase, not a
# bare unittest.TestCase. The rest of this module is intentionally Django-free
# so the pure logic stays trivially unit-testable.
# ---------------------------------------------------------------------------

from django.test import SimpleTestCase, override_settings  # noqa: E402


class SanitizerSettingsOverrideTests(SimpleTestCase):
    """Verify ``CHAT_SANITIZER_*`` settings actually drive runtime behaviour.

    This is the regression test for "blacklist must be configurable via env
    without code changes". If someone refactors ``utils.py`` to hard-code the
    list again, these tests fail loudly.
    """

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["bananas", "pineapple"],
        CHAT_SANITIZER_REPLACEMENT="[FRUIT]",
    )
    def test_settings_blacklist_and_replacement_are_used(self):
        # Custom blacklist words ARE filtered.
        self.assertEqual(sanitize_text("I love bananas"), "I love [FRUIT]")
        self.assertEqual(
            sanitize_text("pineapple on pizza"), "[FRUIT] on pizza"
        )
        # Default words are NOT filtered when the settings override is active —
        # the override fully replaces, it does not extend.
        self.assertEqual(sanitize_text("damn this hell"), "damn this hell")

    @override_settings(CHAT_SANITIZER_BLACKLIST=[])
    def test_empty_blacklist_in_settings_disables_filter(self):
        self.assertEqual(
            sanitize_text("hell shit damn"), "hell shit damn"
        )

    @override_settings(
        CHAT_SANITIZER_BLACKLIST=["secret"],
        CHAT_SANITIZER_REPLACEMENT="###",
    )
    def test_settings_override_still_handles_leetspeak_and_spacing(self):
        # The leetspeak/spacing logic comes from the regex builder, not the
        # blacklist, so a custom-blacklisted word should also pick up these
        # bypass-resistance behaviours.
        self.assertEqual(sanitize_text("s3cret"), "###")
        self.assertEqual(sanitize_text("s.e.c.r.e.t"), "###")
        self.assertEqual(sanitize_text("s e c r e t"), "###")

    @override_settings(CHAT_SANITIZER_BLACKLIST=["banana"])
    def test_explicit_arg_still_overrides_settings(self):
        # The function-level ``blacklist=`` argument must win over settings —
        # this is what unit tests rely on for isolation.
        self.assertEqual(
            sanitize_text("I love bananas", blacklist=["pizza"]),
            "I love bananas",
        )


if __name__ == "__main__":
    unittest.main()
