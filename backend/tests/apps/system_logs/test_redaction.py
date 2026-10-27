from django.test import SimpleTestCase

from apps.system_logs.redaction import (
    REDACTED,
    clean_extra,
    scrub_path,
    scrub_text,
    strip_ansi,
    truncate,
)


class ScrubTextTests(SimpleTestCase):
    def test_redacts_url_query_strings(self):
        text = "Sent https://app.example.org/#/auth/reset-password?token=abc123def456 to someone"
        self.assertEqual(scrub_text(text), f"Sent https://app.example.org/#/auth/reset-password?{REDACTED} to someone")

    def test_redacts_magic_link_and_sas_queries(self):
        self.assertNotIn("secretvalue", scrub_text("https://api.example.org/services/magic/?token=secretvalue&email=a"))
        self.assertNotIn("sigvalue", scrub_text("https://x.blob.core.windows.net/c/f.pdf?sv=1&sig=sigvalue"))

    def test_redacts_authorization_schemes(self):
        self.assertEqual(scrub_text("sent Bearer eyJhbGciOi.payload.sig"), f"sent Bearer {REDACTED}")
        self.assertNotIn("eyJhbGciOi", scrub_text("Authorization: Bearer eyJhbGciOi.payload.sig"))

    def test_redacts_secret_name_value_pairs(self):
        scrubbed = scrub_text("login failed password=hunter2 code: 123456 sessionid='abc'")
        self.assertNotIn("hunter2", scrubbed)
        self.assertNotIn("123456", scrubbed)
        self.assertNotIn("abc", scrubbed)
        self.assertIn(f"password={REDACTED}", scrubbed)

    def test_keeps_ordinary_messages(self):
        message = "system_email.send_failed key=announcement error=SMTPServerDisconnected"
        self.assertEqual(scrub_text(message), message)

    def test_removes_nul_characters(self):
        self.assertEqual(scrub_text("a\x00b"), "ab")


class StripAnsiTests(SimpleTestCase):
    def test_removes_server_colour_codes(self):
        line = "\x1b[31;1mHTTP POST /services/verify-login-code/ 400 [5.02, 127.0.0.1:55573]\x1b[0m"
        self.assertEqual(strip_ansi(line), "HTTP POST /services/verify-login-code/ 400 [5.02, 127.0.0.1:55573]")

    def test_removes_other_escape_sequences(self):
        cases = {
            "\x1b[2K\x1b[1Gcursor moves": "cursor moves",          # CSI erase/move
            "\x9b31mbyte form\x9b0m": "byte form",                  # 8-bit CSI
            "\x1b]0;window title\x07after": "after",                # OSC, BEL-terminated
            "\x1b]8;;https://x.org\x1b\\link\x1b]8;;\x1b\\": "link",  # OSC hyperlink
            "\x1b(Bcharset": "charset",                             # two-character escape
            "stray \x1b escape": "stray  escape",
        }
        for coloured, plain in cases.items():
            with self.subTest(coloured=coloured):
                self.assertEqual(strip_ansi(coloured), plain)

    def test_keeps_newlines_and_tabs(self):
        self.assertEqual(strip_ansi("line one\n\tline two"), "line one\n\tline two")

    def test_scrub_text_strips_codes_before_redacting(self):
        # The colour code after the value must not keep the secret from
        # matching, nor survive into the stored text.
        self.assertEqual(scrub_text("\x1b[31mtoken=abc123\x1b[0m"), f"token={REDACTED}")

    def test_extra_values_are_stripped_too(self):
        self.assertEqual(clean_extra({"reason": "\x1b[32mok\x1b[0m"})["reason"], "ok")


class ReviewProbeTests(SimpleTestCase):
    """The strings tried in review, with what's stored for each."""

    CASES = {
        # dict and JSON text, as when a payload is logged with %s
        "payload {'password': 'hunter2', 'token': 'abc123'}":
            f"payload {{'password': {REDACTED}, 'token': {REDACTED}}}",
        'body {"password": "hunter2", "code": "123456"}':
            f'body {{"password": {REDACTED}, "code": {REDACTED}}}',
        # magic links, with and without the host
        "GET /services/magic/?email=a%40b.com&code=987654&redirect_url=x":
            f"GET /services/magic/?email=a%40b.com&code={REDACTED}&redirect_url=x",
        "link https://api.example.org/services/magic/?email=a%40b.com&code=987654":
            f"link https://api.example.org/services/magic/?{REDACTED}",
        # passwords in connection URLs; the user name stays
        "could not connect to postgresql://biotech:S3cretPass@db.example.com:5432/app":
            f"could not connect to postgresql://biotech:{REDACTED}@db.example.com:5432/app",
        "Error connecting to rediss://:R3disPass@cache.example.net:6380/0":
            f"Error connecting to rediss://:{REDACTED}@cache.example.net:6380/0",
        # Azure storage
        "DefaultEndpointsProtocol=https;AccountName=acct;AccountKey=Zm9vYmFyYmF6cXV4==;EndpointSuffix=core.windows.net":
            f"DefaultEndpointsProtocol=https;AccountName=acct;AccountKey={REDACTED};EndpointSuffix=core.windows.net",
        "Endpoint=sb://ns.servicebus.windows.net/;SharedAccessKeyName=root;SharedAccessKey=c2VjcmV0a2V5PQ==":
            f"Endpoint=sb://ns.servicebus.windows.net/;SharedAccessKeyName=root;SharedAccessKey={REDACTED}",
        "SharedAccessSignature=sv=2024&sig=abcDEF123%3D":
            f"SharedAccessSignature=sv=2024&sig={REDACTED}",
        # headers, codes and tokens
        "Cookie: sessionid=abc123; csrftoken=def456": f"Cookie: {REDACTED}; csrftoken={REDACTED}",
        "Or enter code: 123456 (expires in 10 mins)": f"Or enter code: {REDACTED} (expires in 10 mins)",
        "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOjF9.c2lnbmF0dXJl": f"token {REDACTED}",
        "bad jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOjF9.c2lnbmF0dXJl": f"bad jwt {REDACTED}",
        "smtp login pass=hunter2": f"smtp login pass={REDACTED}",
        # kept on purpose: admins need to see who and where
        "SMTPRecipientsRefused {'amy@example.com': (550, b'no')}": "SMTPRecipientsRefused {'amy@example.com': (550, b'no')}",
        "verify_login_code: invalid code email_tag=ab12 ip=203.0.113.9":
            "verify_login_code: invalid code email_tag=ab12 ip=203.0.113.9",
    }

    def test_each_review_probe(self):
        for text, stored in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(scrub_text(text), stored)

    def test_secrets_never_survive(self):
        for text in self.CASES:
            scrubbed = scrub_text(text)
            for secret in ("hunter2", "abc123", "987654", "S3cretPass", "R3disPass", "Zm9vYmFy", "c2VjcmV0a2V5", "abcDEF123", "eyJhbGciOi"):
                with self.subTest(text=text, secret=secret):
                    self.assertNotIn(secret, scrubbed)

    def test_extra_values_holding_dicts_are_scrubbed(self):
        cleaned = clean_extra({"payload": {"password": "hunter2"}, "headers": "Authorization: Bearer abcdefgh123"})

        self.assertEqual(cleaned["payload"], f"{{'password': {REDACTED}}}")
        self.assertNotIn("abcdefgh123", cleaned["headers"])

    def test_ordinary_words_like_status_code_and_bypass_are_left_alone(self):
        for text in ("status_code=500 duration_ms=12", "bypass=on key=announcement", "passed=3 failed=0"):
            with self.subTest(text=text):
                self.assertEqual(scrub_text(text), text)


class ShortSecretNameTests(SimpleTestCase):
    """code, sid, sig and pass also mean harmless things; only the secrets
    they can name are redacted."""

    def test_status_and_other_codes_are_kept(self):
        for text in (
            "status code=500",
            "response code: 404",
            "upstream returned HTTP status code: 502",
            "worker exited with exit code: 1",
            "error code=ECONNRESET",
            "{'detail': 'Not found.', 'code': 'not_found'}",
            "code=1234567 is not a sign-in code",
        ):
            with self.subTest(text=text):
                self.assertEqual(scrub_text(text), text)

    def test_sign_in_codes_are_redacted(self):
        cases = {
            "Or enter code: 123456 (expires in 10 mins)": f"Or enter code: {REDACTED} (expires in 10 mins)",
            "GET /services/magic/?email=a%40b.com&code=987654": f"GET /services/magic/?email=a%40b.com&code={REDACTED}",
            '{"email": "a@b.com", "code": "123456"}': f'{{"email": "a@b.com", "code": {REDACTED}}}',
            "context {'OTP_CODE': '123456', 'EXPIRY_MINUTES': 10}":
                f"context {{'OTP_CODE': {REDACTED}, 'EXPIRY_MINUTES': 10}}",
            "otp=123456": f"otp={REDACTED}",
            "login_code=123456": f"login_code={REDACTED}",
            "verify_code: 654321": f"verify_code: {REDACTED}",
            "verification_code=ab12cd": f"verification_code={REDACTED}",
            "reset_code=Xy7-abc": f"reset_code={REDACTED}",
            "auth_code=4/0AbCdEf": f"auth_code={REDACTED}",
        }
        for text, stored in cases.items():
            with self.subTest(text=text):
                self.assertEqual(scrub_text(text), stored)

    def test_log_lines_naming_the_code_views_are_kept(self):
        for text in (
            "verify_login_code: invalid code email_tag=ab12 ip=203.0.113.9 attempt=2",
            "send_login_code: no user found — enumeration attempt suppressed ip=203.0.113.9",
        ):
            with self.subTest(text=text):
                self.assertEqual(scrub_text(text), text)

    def test_sid_is_redacted_only_when_it_looks_like_a_session_key(self):
        self.assertEqual(scrub_text("grading sid=42 component=3"), "grading sid=42 component=3")
        self.assertEqual(
            scrub_text("revoked sid=4f9c1b2a7d3e4c5f8a9b0c1d2e3f4a5b"), f"revoked sid={REDACTED}"
        )

    def test_sig_is_redacted_only_as_a_url_parameter(self):
        self.assertEqual(scrub_text("worker stopped sig=15"), "worker stopped sig=15")
        self.assertEqual(scrub_text("sv=2024&sig=abcDEF123%3D&se=x"), f"sv=2024&sig={REDACTED}&se=x")

    def test_pass_is_redacted_only_as_pass_equals_or_a_quoted_key(self):
        self.assertEqual(scrub_text("First pass: grouped 12 students"), "First pass: grouped 12 students")
        self.assertEqual(scrub_text("smtp login pass=hunter2"), f"smtp login pass={REDACTED}")
        self.assertEqual(scrub_text("{'user': 'a', 'pass': 'hunter2'}"), f"{{'user': 'a', 'pass': {REDACTED}}}")


class ScrubPathTests(SimpleTestCase):
    def test_redacts_url_arguments_named_like_secrets(self):
        self.assertEqual(
            scrub_path("/api/v1/consent/short-tok/", {"token": "short-tok"}),
            f"/api/v1/consent/{REDACTED}/",
        )

    def test_redacts_token_shaped_segments_without_a_match(self):
        signed = "eyJzdHVkZW50Ijo0Mn0:1t2Abc:Qx9sX0aBcDeFgHiJkLmN"
        self.assertEqual(scrub_path(f"/api/v1/guardian-details/{signed}/"), f"/api/v1/guardian-details/{REDACTED}/")

    def test_keeps_readable_paths(self):
        for path in ("/api/v1/admin/user/42/guardian-consent-withdrawal/", "/api/v1/admin/email-template/announcement/"):
            self.assertEqual(scrub_path(path, {"key": "announcement"}), path)


class CleanExtraTests(SimpleTestCase):
    def test_redacts_sensitive_keys(self):
        cleaned = clean_extra({"sid": "live-session-key", "access_token": "t", "user_id": 7, "reason": "no_user"})
        self.assertEqual(cleaned["sid"], REDACTED)
        self.assertEqual(cleaned["access_token"], REDACTED)
        self.assertEqual(cleaned["user_id"], 7)
        self.assertEqual(cleaned["reason"], "no_user")

    def test_code_keys_are_redacted_only_when_they_name_a_sign_in_code(self):
        cleaned = clean_extra({"status_code": 500, "error_code": "E42", "code": "123456", "otp_code": "123456"})
        self.assertEqual(cleaned["status_code"], 500)
        self.assertEqual(cleaned["error_code"], "E42")
        self.assertEqual(cleaned["code"], REDACTED)
        self.assertEqual(cleaned["otp_code"], REDACTED)

    def test_makes_values_json_safe(self):
        cleaned = clean_extra({"obj": object(), "nan": float("nan"), "ok": 1.5})
        self.assertIsInstance(cleaned["obj"], str)
        self.assertEqual(cleaned["nan"], "nan")
        self.assertEqual(cleaned["ok"], 1.5)


class TruncateTests(SimpleTestCase):
    def test_keeps_start_and_end(self):
        text = "START" + "x" * 1000 + "END"
        cut = truncate(text, 200)
        self.assertLessEqual(len(cut), 200)
        self.assertTrue(cut.startswith("START"))
        self.assertTrue(cut.endswith("END"))
        self.assertIn("[truncated]", cut)

    def test_leaves_short_text_alone(self):
        self.assertEqual(truncate("short", 200), "short")
