"""What System Logs never stores: secrets in messages, tracebacks and extras.

The logging calls in this codebase already avoid secrets (emails go through
``email_log_tag``, failures log the exception type). This is the safety net for
the ones that don't, and for third-party messages: anything shaped like a
credential is replaced with ``[redacted]`` before a row is queued.
"""
import math
import re

REDACTED = "[redacted]"

MESSAGE_MAX_CHARS = 8_000
TRACEBACK_MAX_CHARS = 32_000
EXTRA_VALUE_MAX_CHARS = 500
EXTRA_MAX_KEYS = 20

# Any URL's query string: reset links (?token=), magic links
# (/services/magic/?...) and Azure SAS URLs (?sig=) all carry secrets there.
# "#" is allowed before the "?": the SPA's links are hash-routed (/#/auth/...).
_URL_QUERY = re.compile(r"(?P<url>\bhttps?://[^\s?\"'<>]+)\?[^\s\"'<>]*")
# "Bearer abc...", "Token abc..." as in an Authorization header.
_AUTH_SCHEME = re.compile(r"(?i)\b(?P<scheme>bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
# name=value / name: value pairs whose name says the value is secret.
_SECRET_PAIR = re.compile(
    r"(?i)\b(?P<name>password|passwd|pwd|secret|client_secret|token|access_token|refresh_token"
    r"|api_key|apikey|secret_key|account_key|access_key|sessionid|session_key|csrftoken|csrfmiddlewaretoken"
    r"|sid|otp|code|signature|sig|authorization|cookie)"
    r"(?P<sep>\s*[=:]\s*)(?P<value>\"[^\"]*\"|'[^']*'|[^\s&,;]+)"
)

# Extra keys kept as they are, even though a word in them looks sensitive.
SAFE_EXTRA_KEYS = frozenset({"user_id", "reason", "status", "kind", "count", "duration_ms", "revoked_at", "ended_at"})
_SENSITIVE_KEY_PARTS = frozenset({
    "password", "passwd", "pwd", "secret", "token", "sid", "session", "sessionid", "cookie",
    "authorization", "auth", "otp", "code", "magic", "csrf", "signature", "sig", "credential",
    "credentials", "apikey", "key",
})


# Terminal colour and cursor codes, as servers colour their console lines
# ("\x1b[31;1mHTTP POST ... 400\x1b[0m"): CSI sequences (7-bit and 8-bit),
# OSC sequences (window titles, links), character set selection ("\x1b(B")
# and the other two-character escapes.
_ANSI_ESCAPE = re.compile(
    r"\x1b\[[0-?]*[ -/]*[@-~]"
    r"|\x9b[0-?]*[ -/]*[@-~]"
    r"|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|\x1b[()*+#%][0-~]"
    r"|\x1b[@-Z\\-_]"
)


def strip_ansi(text: str) -> str:
    """``text`` without terminal escape codes; a stray ESC left over is
    dropped too."""
    return _ANSI_ESCAPE.sub("", text).replace("\x1b", "")


def scrub_text(text: str) -> str:
    """``text`` with terminal colour codes removed, URL query strings, auth
    headers and secret=value pairs replaced, and NUL characters (which
    PostgreSQL text can't hold) removed."""
    if not text:
        return ""
    # First, so a code next to a secret can't hide it from the patterns below.
    text = strip_ansi(text.replace("\x00", ""))
    text = _URL_QUERY.sub(lambda m: f"{m.group('url')}?{REDACTED}", text)
    text = _AUTH_SCHEME.sub(lambda m: f"{m.group('scheme')} {REDACTED}", text)
    return _SECRET_PAIR.sub(lambda m: f"{m.group('name')}{m.group('sep')}{REDACTED}", text)


def truncate(text: str, limit: int) -> str:
    """``text`` cut to about ``limit`` characters, keeping the start and the
    end (where a traceback names the actual error)."""
    if len(text) <= limit:
        return text
    marker = "\n...[truncated]...\n"
    head = limit // 4
    tail = limit - head - len(marker)
    return text[:head] + marker + text[-tail:]


def is_sensitive_key(key: str) -> bool:
    if key.lower() in SAFE_EXTRA_KEYS:
        return False
    parts = re.split(r"[^a-z0-9]+", key.lower())
    return any(part in _SENSITIVE_KEY_PARTS for part in parts) or any(
        word in key.lower() for word in ("password", "token", "secret")
    )


# A path segment that looks like a token: long, only token characters, with
# both letters and digits (so readable slugs like "guardian-consent-withdrawal"
# are kept). Catches the guardian links (/consent/<token>/) even when the URL
# didn't resolve.
_TOKEN_SEGMENT = re.compile(r"^(?=[^/]*[A-Za-z])(?=[^/]*\d)[A-Za-z0-9_\-:.=]{24,}$")
_SECRET_KWARG_WORDS = ("token", "secret", "signature", "password", "otp", "magic")


def scrub_path(path: str, url_kwargs: dict | None = None) -> str:
    """A request path safe to store: values of URL arguments named like
    secrets (``<str:token>``) and token-shaped segments replaced."""
    secrets = {
        str(value)
        for name, value in (url_kwargs or {}).items()
        if value and any(word in name.lower() for word in _SECRET_KWARG_WORDS)
    }
    segments = [
        REDACTED if segment in secrets or _TOKEN_SEGMENT.match(segment) else segment
        for segment in path.split("/")
    ]
    return "/".join(segments).replace("\x00", "")


def clean_extra(extra: dict) -> dict:
    """A record's ``extra`` fields made safe to store: sensitive keys
    redacted, values reduced to short JSON-safe scalars."""
    cleaned = {}
    for key, value in list(extra.items())[:EXTRA_MAX_KEYS]:
        key = str(key)[:100]
        if is_sensitive_key(key):
            cleaned[key] = REDACTED
        elif value is None or isinstance(value, (bool, int)):
            cleaned[key] = value
        elif isinstance(value, float):
            # PostgreSQL's JSON rejects NaN and infinity.
            cleaned[key] = value if math.isfinite(value) else str(value)
        else:
            cleaned[key] = truncate(scrub_text(str(value)), EXTRA_VALUE_MAX_CHARS)
    return cleaned
