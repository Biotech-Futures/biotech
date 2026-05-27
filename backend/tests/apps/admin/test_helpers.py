"""Tests for pure helper functions used across admin services — no DB required."""
from django.test import SimpleTestCase

from apps.admin.services.announcement import _sanitize_error, _strip_html, _build_excerpt
from apps.admin.services.user import normalize_interest_descriptions
from apps.admin.services.match import _safe_int, _without_none, _map_interests_by_user_id
from apps.admin.services.mentor_match import _group_interests_by_key
from apps.admin.services.resource import slugify_role, normalize_role_ids, build_storage_key, extract_file_name_from_storage_key
from apps.admin.services.event import _to_event_id, _resolve_event_format

# ─── normalize_interest_descriptions ──────────────────────────────────────────

class NormalizeInterestDescriptionsTests(SimpleTestCase):

    def test_none_or_empty(self):
        self.assertEqual(normalize_interest_descriptions(None), [])
        self.assertEqual(normalize_interest_descriptions([]), [])

    def test_trims_whitespace(self):
        result = normalize_interest_descriptions(["  AI  ", "  ML  "])
        self.assertEqual(result, ["AI", "ML"])

    def test_removes_empty_after_trim(self):
        result = normalize_interest_descriptions(["AI", "", "  ", "ML"])
        self.assertEqual(result, ["AI", "ML"])

    def test_deduplicates_preserving_order(self):
        result = normalize_interest_descriptions(["AI", "ML", "AI", "ML"])
        self.assertEqual(result, ["AI", "ML"])

    def test_mixed_case_not_deduplicated(self):
        result = normalize_interest_descriptions(["AI", "ai"])
        self.assertEqual(result, ["AI", "ai"])


# ─── _sanitize_error ──────────────────────────────────────────────────────────

class SanitizeErrorTests(SimpleTestCase):

    def test_normal_error(self):
        result = _sanitize_error(ValueError("something broke"))
        self.assertEqual(result, "ValueError: something broke")

    def test_empty_message(self):
        result = _sanitize_error(RuntimeError())
        self.assertEqual(result, "RuntimeError")

    def test_strips_crlf(self):
        result = _sanitize_error(ValueError("line1\r\nline2\nline3\r"))
        self.assertNotIn("\r", result)
        self.assertNotIn("\n", result)
        self.assertIn("line1", result)
        self.assertIn("line2", result)
        self.assertIn("line3", result)

    def test_truncates_long_body(self):
        body = "x" * 250
        result = _sanitize_error(ValueError(body))
        self.assertIn("ValueError: ", result)
        self.assertIn("…", result)
        self.assertTrue(len(result) < 260)

    def test_short_body_not_truncated(self):
        result = _sanitize_error(ValueError("short error"))
        self.assertEqual(result, "ValueError: short error")

    def test_strips_and_truncates(self):
        body = "a\n" * 300
        result = _sanitize_error(ValueError(body))
        self.assertNotIn("\n", result)
        self.assertIn("…", result)


# ─── _strip_html ──────────────────────────────────────────────────────────────

class StripHtmlTests(SimpleTestCase):

    def test_plain_text(self):
        self.assertEqual(_strip_html("hello world"), "hello world")

    def test_removes_tags(self):
        self.assertEqual(_strip_html("<p>hello</p>"), "hello")

    def test_removes_nested_tags(self):
        self.assertEqual(
            _strip_html("<div><p><b>bold</b> text</p></div>"),
            "bold text",
        )

    def test_normalizes_whitespace(self):
        self.assertEqual(_strip_html("<p>hello    \n\nworld</p>"), "hello world")

    def test_empty_input(self):
        self.assertEqual(_strip_html(""), "")


# ─── _build_excerpt ───────────────────────────────────────────────────────────

class BuildExcerptTests(SimpleTestCase):

    def test_short_html(self):
        result = _build_excerpt("<p>short text</p>", max_chars=200)
        self.assertEqual(result, "short text")

    def test_long_html_truncated(self):
        long_text = "a" * 300
        result = _build_excerpt(f"<p>{long_text}</p>", max_chars=200)
        self.assertEqual(len(result), 201)  # 200 chars + "…"
        self.assertTrue(result.endswith("…"))

    def test_custom_max_chars(self):
        result = _build_excerpt("hello world", max_chars=5)
        self.assertEqual(result, "hello…")

    def test_empty_html(self):
        self.assertEqual(_build_excerpt(""), "")

    def test_html_only(self):
        self.assertEqual(_build_excerpt("<br/><hr/>"), "")


# ─── _safe_int ────────────────────────────────────────────────────────────────

class SafeIntTests(SimpleTestCase):

    def test_valid_int(self):
        self.assertEqual(_safe_int("5"), 5)

    def test_none(self):
        self.assertIsNone(_safe_int(None))

    def test_empty_string(self):
        self.assertIsNone(_safe_int(""))

    def test_invalid_string(self):
        self.assertIsNone(_safe_int("abc"))

    def test_float_string(self):
        self.assertIsNone(_safe_int("3.14"))


# ─── _without_none ────────────────────────────────────────────────────────────

class WithoutNoneTests(SimpleTestCase):

    def test_removes_none_values(self):
        result = _without_none({"a": 1, "b": None, "c": "hello"})
        self.assertEqual(result, {"a": 1, "c": "hello"})

    def test_all_none(self):
        self.assertEqual(_without_none({"a": None, "b": None}), {})

    def test_no_none(self):
        self.assertEqual(_without_none({"a": 1, "b": 2}), {"a": 1, "b": 2})

    def test_false_is_kept(self):
        result = _without_none({"a": 0, "b": False, "c": None})
        self.assertEqual(result, {"a": 0, "b": False})


# ─── _map_interests_by_user_id ────────────────────────────────────────────────

class MapInterestsByUserIdTests(SimpleTestCase):

    def test_groups_interests(self):
        rows = [
            {"user_id": 1, "interest_desc": "AI"},
            {"user_id": 1, "interest_desc": "ML"},
            {"user_id": 2, "interest_desc": "Robotics"},
        ]
        result = _map_interests_by_user_id(rows)
        self.assertEqual(result, {1: ["AI", "ML"], 2: ["Robotics"]})

    def test_empty_input(self):
        self.assertEqual(_map_interests_by_user_id([]), {})


# ─── _group_interests_by_key ──────────────────────────────────────────────────

class GroupInterestsByKeyTests(SimpleTestCase):

    def test_groups_by_custom_key(self):
        rows = [
            {"group_id": 10, "interest_desc": "AI"},
            {"group_id": 10, "interest_desc": "ML"},
            {"group_id": 20, "interest_desc": "Robotics"},
        ]
        result = _group_interests_by_key(rows, "group_id", "interest_desc")
        self.assertEqual(result, {10: ["AI", "ML"], 20: ["Robotics"]})

    def test_empty_input(self):
        self.assertEqual(_group_interests_by_key([], "k", "v"), {})


# ─── slugify_role ────────────────────────────────────────────────────────────

class SlugifyRoleTests(SimpleTestCase):

    def test_lowercases(self):
        self.assertEqual(slugify_role("Admin"), "admin")

    def test_replaces_spaces_with_hyphens(self):
        self.assertEqual(slugify_role("Track Admin"), "track-admin")

    def test_removes_non_alphanumeric(self):
        self.assertEqual(slugify_role("admin!@#"), "admin")

    def test_strips_leading_trailing_hyphens(self):
        self.assertEqual(slugify_role("--admin--"), "admin")

    def test_empty_string(self):
        self.assertEqual(slugify_role(""), "")


# ─── normalize_role_ids ──────────────────────────────────────────────────────

class NormalizeRoleIdsTests(SimpleTestCase):

    def test_includes_admin_role(self):
        available = [{"id": 1, "slug": "admin"}, {"id": 2, "slug": "student"}]
        result = normalize_role_ids([2], available)
        self.assertIn(1, result)  # admin always included
        self.assertIn(2, result)

    def test_deduplicates(self):
        available = [{"id": 1, "slug": "admin"}, {"id": 2, "slug": "student"}]
        result = normalize_role_ids([2, 2], available)
        self.assertEqual(sorted(result), [1, 2])

    def test_filters_invalid_ids(self):
        available = [{"id": 1, "slug": "admin"}]
        result = normalize_role_ids([99], available)
        self.assertEqual(result, [1])

    def test_no_available_roles(self):
        result = normalize_role_ids([1, 2], [])
        self.assertEqual(result, [])

    def test_none_role_ids(self):
        available = [{"id": 1, "slug": "admin"}]
        result = normalize_role_ids(None, available)
        self.assertEqual(result, [1])


# ─── build_storage_key ──────────────────────────────────────────────────────

class BuildStorageKeyTests(SimpleTestCase):

    def test_contains_resource_id(self):
        key = build_storage_key(42, "test.pdf")
        self.assertIn("42", key)
        self.assertIn("test.pdf", key)

    def test_default_filename(self):
        key = build_storage_key(1)
        self.assertIn("resource.bin", key)

    def test_sanitizes_filename(self):
        key = build_storage_key(1, "bad/file name!.pdf")
        self.assertNotIn("!", key)
        self.assertIn(".pdf", key)


# ─── extract_file_name_from_storage_key ─────────────────────────────────────

class ExtractFileNameFromStorageKeyTests(SimpleTestCase):

    def test_typical_key(self):
        result = extract_file_name_from_storage_key("resources/1234567890-42-resume.pdf")
        self.assertEqual(result, "resume.pdf")

    def test_returns_none_for_none(self):
        self.assertIsNone(extract_file_name_from_storage_key(None))

    def test_returns_raw_if_no_dash_after_stamp(self):
        result = extract_file_name_from_storage_key("resources/file.bin")
        self.assertEqual(result, "file.bin")


# ─── _to_event_id ──────────────────────────────────────────────────────────

class ToEventIdTests(SimpleTestCase):

    def test_valid_int_string(self):
        self.assertEqual(_to_event_id("5"), 5)

    def test_zero_returns_none(self):
        self.assertIsNone(_to_event_id("0"))

    def test_negative_returns_none(self):
        self.assertIsNone(_to_event_id("-1"))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_to_event_id("abc"))

    def test_none_returns_none(self):
        self.assertIsNone(_to_event_id(None))

    def test_already_int(self):
        self.assertEqual(_to_event_id(5), 5)


# ─── _resolve_event_format ─────────────────────────────────────────────────

class ResolveEventFormatTests(SimpleTestCase):

    def test_camel_case(self):
        self.assertEqual(_resolve_event_format({"eventFormat": "online"}), "online")

    def test_snake_case(self):
        self.assertEqual(_resolve_event_format({"event_format": "in_person"}), "in_person")

    def test_camel_takes_precedence(self):
        result = _resolve_event_format({"eventFormat": "online", "event_format": "in_person"})
        self.assertEqual(result, "online")

    def test_both_missing(self):
        self.assertIsNone(_resolve_event_format({}))
