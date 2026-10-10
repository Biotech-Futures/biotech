"""Unit tests for ``apps.common.matching_modes``.

This module is the single source of truth for the ``mode`` parameter that the
student and mentor algorithms share, so these tests pin:

* the vocabulary is exactly ``balanced``/``strict``/``coverage`` - the same
  three values the frontend ``MentorMatchMode`` union promises,
* the ``MatchMode`` literal and the ``MATCHING_MODES`` tuple cannot drift
  apart (they are two spellings of one contract), and
* a known mode passes through ``resolve_match_mode`` untouched while an
  unknown or missing one falls back to ``balanced`` instead of raising -
  which is what both endpoints rely on when ``?mode=`` is a query string.

Whether an unknown mode actually *runs* balanced inside the algorithms is
checked one layer out, in
``tests.apps.admin.test_matching_mode_entrypoints``.
"""

from typing import get_args

from django.test import SimpleTestCase

from apps.common.matching_modes import (
    DEFAULT_MATCH_MODE,
    MATCHING_MODES,
    MatchMode,
    resolve_match_mode,
)


class MatchModeVocabularyTests(SimpleTestCase):
    def test_the_three_modes_are_the_documented_ones(self):
        self.assertEqual(MATCHING_MODES, ("balanced", "strict", "coverage"))

    def test_default_mode_is_a_known_mode(self):
        self.assertEqual(DEFAULT_MATCH_MODE, "balanced")
        self.assertIn(DEFAULT_MATCH_MODE, MATCHING_MODES)

    def test_literal_and_tuple_cannot_drift(self):
        # Both spell the same contract: if one gains a mode the other must too,
        # otherwise a value can be valid for the type and rejected by the
        # resolver (or vice versa).
        self.assertEqual(get_args(MatchMode), MATCHING_MODES)


class ResolveMatchModeTests(SimpleTestCase):
    def test_known_modes_pass_through(self):
        for mode in MATCHING_MODES:
            with self.subTest(mode=mode):
                self.assertEqual(resolve_match_mode(mode), mode)

    def test_unknown_modes_fall_back_to_balanced(self):
        for raw in (
            None,
            "",
            "bogus",
            "BALANCED",
            "Strict",
            " strict",
            "strict ",
            "balanced-strict",
            "1",
        ):
            with self.subTest(raw=raw):
                self.assertEqual(resolve_match_mode(raw), "balanced")

    def test_result_is_always_a_known_mode(self):
        for raw in (None, "", "bogus", *MATCHING_MODES):
            with self.subTest(raw=raw):
                self.assertIn(resolve_match_mode(raw), MATCHING_MODES)
