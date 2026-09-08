"""Render the submission emails to disk and serve them for review.

A development helper, for showing the programme team what a student actually
receives before the wording is signed off. Nothing here touches the database or
sends anything — the templates are rendered against a made-up team so the page
can be looked at without first arranging a real submission.

    python manage.py preview_submission_emails --settings=config.settings_local
    python manage.py preview_submission_emails --port 8900

The inline logo is swapped for a data URI. In a real message it is a ``cid:``
reference to an attached image part, which a mail client resolves and a browser
cannot, so previewing the file as sent would show a broken image where the
masthead belongs.
"""
from __future__ import annotations

import base64
import functools
import http.server
import pathlib
import socketserver
import tempfile
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone

from apps.services.email_branding import brand_context
from apps.submissions import emails as confirmation
from apps.submissions import reminders


DEFAULT_PORT = 8900


class _Team:
    """Just enough of a team for the templates to render."""

    id = 1
    group_name = "BTF12"


class _Person:
    def __str__(self):
        return "Priya Raman"


def _logo_data_uri() -> str:
    path = pathlib.Path(confirmation._LOGO_PATH)
    if not path.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _component(label, present, detail="", *, absent_word):
    return {
        "label": label,
        "submitted": present,
        "status": "Submitted" if present else absent_word,
        "detail": detail if present else "",
    }


class Command(BaseCommand):
    help = "Render the submission confirmation and reminder emails and serve them."

    def add_arguments(self, parser):
        parser.add_argument("--port", type=int, default=DEFAULT_PORT)
        parser.add_argument(
            "--no-serve",
            action="store_true",
            help="Write the files and print their paths without starting a server.",
        )

    def handle(self, *args, **options):
        out = pathlib.Path(tempfile.gettempdir()) / "btf-email-preview"
        out.mkdir(parents=True, exist_ok=True)

        team = _Team()
        deadline = timezone.now() + timedelta(days=5)
        shared = {
            **brand_context(),
            "LOGO_URL": _logo_data_uri(),
            "GROUP_NAME": team.group_name,
            "YEAR": timezone.now().year,
            "DEADLINE": reminders._format_deadline(deadline),
            "SUBMISSION_URL": "https://example.org/#/submission/1",
        }

        # The confirmation, as a team who submitted everything would see it.
        complete = {
            **shared,
            "REQUIRED_COMPONENTS": [
                _component("Poster", True, "btf12-poster.pdf", absent_word="Absent"),
                _component("Short Answer Questions (SAQs)", True, absent_word="Absent"),
            ],
            "OPTIONAL_COMPONENTS": [
                _component("Scientific Report", True, "btf12-report.pdf", absent_word="Absent"),
                _component("Prototype", False, absent_word="Absent"),
            ],
            "INCOMPLETE": False,
            "SUBMITTED_BY": _Person(),
        }

        # The reminder, as a team who is missing their poster would see it.
        outstanding = {
            **shared,
            "REQUIRED_COMPONENTS": [
                _component("Poster", False, absent_word="Not Submitted"),
                _component(
                    "Short Answer Questions (SAQs)", True, absent_word="Not Submitted"
                ),
            ],
            "OPTIONAL_COMPONENTS": [
                _component(
                    "Scientific Report", True, "btf12-report.pdf",
                    absent_word="Not Submitted",
                ),
                _component("Prototype", False, absent_word="Not Submitted"),
            ],
        }

        pages = {
            "confirmation.html": ("emails/submission_confirmation.html", complete),
            "reminder.html": ("emails/submission_reminder.html", outstanding),
        }
        for filename, (template, context) in pages.items():
            (out / filename).write_text(render_to_string(template, context), encoding="utf-8")

        # The plain-text parts too: some clients show these instead, and the
        # wording has to hold up on its own.
        for filename, (template, context) in {
            "confirmation.txt": ("emails/submission_confirmation.txt", complete),
            "reminder.txt": ("emails/submission_reminder.txt", outstanding),
        }.items():
            (out / filename).write_text(render_to_string(template, context), encoding="utf-8")

        (out / "index.html").write_text(_INDEX, encoding="utf-8")

        self.stdout.write(self.style.SUCCESS(f"Rendered to {out}"))
        if options["no_serve"]:
            for path in sorted(out.iterdir()):
                self.stdout.write(f"  {path}")
            return

        port = options["port"]
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
        socketserver.TCPServer.allow_reuse_address = True
        with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
            self.stdout.write(self.style.SUCCESS(f"\n  http://localhost:{port}/\n"))
            self.stdout.write("Press Ctrl+C to stop.")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                self.stdout.write("\nStopped.")


_INDEX = """<!doctype html>
<meta charset="utf-8">
<title>BIOTech Futures — submission emails</title>
<style>
  body { font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
         margin: 0; background: #f6f7f6; color: #26312c; }
  header { padding: 22px 28px; background: #ffffff; border-bottom: 1px solid #e2e6e3; }
  h1 { margin: 0; font-size: 19px; }
  p  { margin: 6px 0 0; color: #5f6b65; font-size: 13.5px; }
  .row { display: flex; gap: 20px; padding: 20px; align-items: stretch; flex-wrap: wrap; }
  .col { flex: 1 1 520px; display: flex; flex-direction: column; }
  .col h2 { font-size: 14px; margin: 0 0 8px; }
  .col small { color: #5f6b65; font-weight: 400; }
  iframe { width: 100%; height: 1180px; border: 1px solid #e2e6e3; background: #fff; }
  .links { padding: 0 20px 24px; font-size: 13px; }
  a { color: #017151; }
</style>
<header>
  <h1>Submission emails</h1>
  <p>Rendered from the real templates. The confirmation is shown for a complete
     entry; the reminder for a team still missing their poster.</p>
</header>
<div class="row">
  <div class="col">
    <h2>Confirmation <small>— sent once, when a team submits</small></h2>
    <iframe src="confirmation.html" title="Submission confirmation email"></iframe>
  </div>
  <div class="col">
    <h2>Reminder <small>— daily for the last week, until they submit</small></h2>
    <iframe src="reminder.html" title="Submission reminder email"></iframe>
  </div>
</div>
<p class="links">
  Plain-text versions:
  <a href="confirmation.txt">confirmation.txt</a> &middot;
  <a href="reminder.txt">reminder.txt</a>
</p>
"""
