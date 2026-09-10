"""Open the most recently sent email in a browser.

Local development writes mail to disk as raw MIME (see ``EMAIL_FILE_PATH`` in
settings_local). That file is technically readable but impractical to check by
eye: the headers, a plain-text part, an HTML part and a base64-encoded logo all
sit in one file, and the logo alone runs to tens of thousands of characters.

This pulls out the part you actually want to look at and opens it rendered.
Development helper only — it does nothing outside the file-based backend.
"""
from __future__ import annotations

import email
import pathlib
import tempfile
import webbrowser

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Open the most recently sent email (file-based backend) in a browser."

    def add_arguments(self, parser):
        parser.add_argument(
            "--text",
            action="store_true",
            help="Print the plain-text part to the terminal instead of opening the HTML.",
        )
        parser.add_argument(
            "--headers",
            action="store_true",
            help="Print To/From/Subject only. Quickest way to check who was emailed.",
        )

    def handle(self, *args, **options):
        path = getattr(settings, "EMAIL_FILE_PATH", None)
        if not path:
            raise CommandError(
                "EMAIL_FILE_PATH is not set, so mail is not being written to disk. "
                "Run with --settings=config.settings_local."
            )

        folder = pathlib.Path(path)
        messages = sorted(folder.glob("*.log")) if folder.exists() else []
        if not messages:
            raise CommandError(
                f"No emails found in {folder}. Send one first — submitting an "
                f"entry triggers a confirmation."
            )

        newest = max(messages, key=lambda p: p.stat().st_mtime)
        msg = email.message_from_bytes(newest.read_bytes())
        self.stdout.write(f"Message: {newest.name}  ({len(messages)} on file)")

        for header in ("From", "To", "Subject"):
            self.stdout.write(f"  {header}: {msg.get(header, '(none)')}")

        if options["headers"]:
            return

        wanted = "text/plain" if options["text"] else "text/html"
        body = self._part(msg, wanted)
        if body is None:
            raise CommandError(f"No {wanted} part in {newest.name}.")

        if options["text"]:
            self.stdout.write("")
            self.stdout.write(body)
            return

        # The logo travels as an inline cid: attachment, which a standalone
        # file cannot resolve — hide it rather than show a broken-image icon.
        body = body.replace('src="cid:btf-logo"', 'src="" style="display:none"')

        target = pathlib.Path(tempfile.gettempdir()) / "btf-last-email.html"
        target.write_text(body, encoding="utf-8")
        webbrowser.open(target.as_uri())
        self.stdout.write(self.style.SUCCESS(f"\nOpened in your browser: {target}"))

    @staticmethod
    def _part(msg, content_type: str) -> str | None:
        for part in msg.walk():
            if part.get_content_type() == content_type:
                return part.get_payload(decode=True).decode("utf-8", "replace")
        return None
