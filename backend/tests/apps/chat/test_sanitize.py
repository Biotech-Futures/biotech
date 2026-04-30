"""Unit tests for ``apps.chat.utils.sanitize_text``.

These are pure-Python tests with no DB, no Channels, no DRF — they exercise
the sanitisation function in isolation, which is the SRP win that the chat
``utils.py`` module is meant to enable.
"""

import unittest

from apps.chat.utils import REPLACEMENT, sanitize_text


class SanitizeTextTests(unittest.TestCase):
    def test_empty_string_returned_unchanged(self):
        self.assertEqual(sanitize_text(""), "")

    def test_clean_text_returned_unchanged(self):
        self.assertEqual(
            sanitize_text("hello world, how are you?"),
            "hello world, how are you?",
        )

    def test_non_string_returned_unchanged(self):
        # The function is defensive on type so callers don't have to be.
        self.assertIsNone(sanitize_text(None))  # type: ignore[arg-type]
        self.assertEqual(sanitize_text(123), 123)  # type: ignore[arg-type]

    def test_single_swear_replaced_with_asterisks(self):
        self.assertEqual(sanitize_text("this is shit"), f"this is {REPLACEMENT}")

    def test_replacement_token_is_three_asterisks(self):
        self.assertEqual(REPLACEMENT, "***")

    def test_case_insensitive_replacement(self):
        self.assertEqual(sanitize_text("Shit ShIt SHIT"), "*** *** ***")

    def test_multiple_swears_in_one_message(self):
        self.assertEqual(
            sanitize_text("what the hell is this shit"),
            "what the *** is this ***",
        )

    def test_punctuation_around_swear_preserved(self):
        # Word boundaries should treat trailing punctuation as outside the match
        # so the surrounding characters are kept intact.
        self.assertEqual(sanitize_text("oh, shit!"), "oh, ***!")
        self.assertEqual(sanitize_text("(hell)"), "(***)")

    def test_substrings_inside_other_words_are_not_censored(self):
        # Avoid the Scunthorpe problem — only whole words should be censored.
        self.assertEqual(sanitize_text("classic"), "classic")
        self.assertEqual(sanitize_text("shitake mushrooms"), "shitake mushrooms")
        self.assertEqual(sanitize_text("damnation"), "damnation")

    def test_longer_blacklist_entries_take_precedence(self):
        # "fucking" must be matched before "fuck" so the whole word is replaced
        # rather than leaving "***ing" behind.
        self.assertEqual(sanitize_text("you are fucking late"), "you are *** late")

    def test_custom_blacklist_overrides_default(self):
        self.assertEqual(
            sanitize_text("bananas are great", blacklist=["bananas"]),
            "*** are great",
        )
        # When a custom blacklist is supplied, default words are NOT censored.
        self.assertEqual(
            sanitize_text("hell yeah bananas", blacklist=["bananas"]),
            "hell yeah ***",
        )

    def test_empty_blacklist_returns_text_unchanged(self):
        self.assertEqual(
            sanitize_text("hell shit damn", blacklist=[]),
            "hell shit damn",
        )

    def test_unicode_text_is_preserved(self):
        # Sanitisation must not break non-ASCII surrounding text.
        self.assertEqual(sanitize_text("你好 hell 世界"), "你好 *** 世界")


if __name__ == "__main__":
    unittest.main()
