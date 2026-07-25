"""Convert any stored full Azure SAS URLs in Events.event_image to bare blob keys.

Historically the upload path saved a 1-hour signed URL into event_image, so those
links expire and the banner stops loading. Reads now re-sign on the fly, but this
one-off pass shrinks stored values to durable keys so the DB is self-consistent and
edit round-trips carry keys. Logic is inlined (not imported from app code) so the
migration stays stable if the helpers change.
"""
from urllib.parse import urlparse

from django.conf import settings
from django.db import migrations

_CONTAINER = "media"


def _account_name_from_connection_string():
    conn = getattr(settings, "AZURE_CONNECTION_STRING", "") or ""
    for part in conn.split(";"):
        if part.strip().lower().startswith("accountname="):
            return part.split("=", 1)[1].strip()
    return ""


def _managed_hosts():
    hosts = set()
    account = (getattr(settings, "AZURE_ACCOUNT_NAME", "") or "") or _account_name_from_connection_string()
    if account:
        hosts.add(f"{account}.blob.core.windows.net")
    custom = getattr(settings, "AZURE_CUSTOM_DOMAIN", "") or ""
    if custom:
        hosts.add(custom)
    return hosts


def _to_key(value):
    if not value:
        return value
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value  # already a bare key
    if parsed.netloc not in _managed_hosts():
        return value  # external URL — leave alone
    path = parsed.path.lstrip("/")
    prefix = f"{_CONTAINER}/"
    if path.startswith(prefix):
        path = path[len(prefix):]
    return path or value


def normalize_keys(apps, schema_editor):
    Events = apps.get_model("events", "Events")
    qs = Events.objects.exclude(event_image__isnull=True).exclude(event_image="")
    for event in qs.iterator():
        new_value = _to_key(event.event_image)
        if new_value != event.event_image:
            event.event_image = new_value
            event.save(update_fields=["event_image"])


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0015_remove_eventtargettrack_event_and_more"),
    ]

    operations = [
        migrations.RunPython(normalize_keys, migrations.RunPython.noop),
    ]
