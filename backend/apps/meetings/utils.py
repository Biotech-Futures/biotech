from urllib.parse import urlparse

_PROVIDER_DOMAINS = {
    "zoom": ("zoom.us",),
    "google_meet": ("meet.google.com",),
    "microsoft_teams": ("teams.microsoft.com", "teams.live.com")
}
# check hostname
def detect_provider(url: str) -> str:
    parsed = (urlparse(url or "").hostname or "").lower()

    for provider, domains in _PROVIDER_DOMAINS.items():
        if any(parsed == d or parsed.endswith("." + d) for d in domains):
            return provider

    return "other"