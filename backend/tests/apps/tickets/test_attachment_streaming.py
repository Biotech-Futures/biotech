"""Ticket attachment downloads are streamed, and refusals stay machine-readable.

Both front ends ask for an attachment with the app's own client rather than
pointing the browser at the URL. A link click is a top-level navigation the
browser commits to before it knows what comes back: when the answer is a file
the navigation is cancelled, but when it is a 403 or a 404 the answer *replaces
the page*, and on the portal that takes the half-typed reply underneath with
it. Fetching instead turns a refusal into a value the page can render.

That only works if the endpoint answers on our own origin. In production
``resolve_url`` hands back a signed Azure URL and ``serve_managed_file``
answers 302 into the blob container; a ``fetch`` re-applies CORS at that second
hop, the container publishes no ``Access-Control-Allow-Origin``, and the
download fails with a bare ``TypeError`` that carries no status. So these two
endpoints pass ``prefer_stream=True``.

Nothing in this repository has ever executed the Azure branch — ``settings_test``
and ``settings_local`` both set ``USE_AZURE_BLOB_STORAGE = False``, so
``resolve_url`` returns a local ``/media/...`` path and the redirect never
fires. Every test below that cares about the production shape patches
``resolve_url`` to return an absolute URL, which is the only way to reach the
branch at all.
"""
import ast
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.storage import reset_managed_storage_caches, serve_managed_file
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketCategory,
)
from apps.tickets.services import attachments as attachments_module

User = get_user_model()

LIST_URL = "/api/v1/tickets/"
_MEDIA = tempfile.mkdtemp(prefix="ticket-stream-tests-")

# What a signed Azure URL looks like coming out of resolve_url. Absolute, which
# is what serve_managed_file tests before it redirects.
SIGNED = "https://acct.blob.core.windows.net/chat/tickets/2026/08/x.pdf?sig=abc"

# What a browser sends when it follows a link, taken from Chrome 140. DRF has
# no DEFAULT_RENDERER_CLASSES override, so this negotiates its way to the
# browsable-API HTML renderer.
BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

FILE_BODY = b"%PDF-1.4" + b"0" * 1024


def pdf(name="report.pdf"):
    return SimpleUploadedFile(name, FILE_BODY, content_type="application/pdf")


def body_of(response):
    if getattr(response, "streaming", False):
        return b"".join(response.streaming_content)
    return response.content


@override_settings(MEDIA_ROOT=_MEDIA)
class AttachmentDownloadIsStreamedTests(APITestCase):
    """The two ticket endpoints answer with bytes, never with a redirect."""

    def setUp(self):
        reset_managed_storage_caches()
        cache.clear()
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.agent = User.objects.create_user(
            email="agent@example.com", password="pass1234",
            first_name="Sam", last_name="Reid",
        )
        SupportScope.objects.create(user=self.agent)
        self.client.force_login(self.requester)
        data = self.client.post(
            LIST_URL,
            {
                "category": TicketCategory.HELP_STUDENT_GROUP,
                "subject": "With a file",
                "body": "See attached.",
                "files": pdf(),
            },
            format="multipart",
        ).json()["data"]
        self.ticket = Ticket.objects.get(pk=data["id"])
        self.attachment_id = data["messages"][0]["attachments"][0]["id"]

    def tearDown(self):
        reset_managed_storage_caches()

    def requester_url(self):
        return f"{LIST_URL}{self.ticket.pk}/attachments/{self.attachment_id}/"

    def support_url(self):
        return f"/api/v1/admin/tickets/{self.ticket.pk}/attachments/{self.attachment_id}/"

    def test_the_requester_endpoint_streams_even_when_a_signed_url_exists(self):
        # Without prefer_stream this is a 302 into the blob container, which a
        # fetch cannot follow: the container sends no CORS header, so the
        # browser reports a TypeError with no status behind it.
        with patch.object(
            attachments_module.ticket_files, "resolve_url", return_value=SIGNED
        ):
            response = self.client.get(self.requester_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("Location", response.headers)
        self.assertEqual(body_of(response), FILE_BODY)

    def test_the_support_endpoint_streams_even_when_a_signed_url_exists(self):
        self.client.force_login(self.agent)
        with patch.object(
            attachments_module.ticket_files, "resolve_url", return_value=SIGNED
        ):
            response = self.client.get(self.support_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn("Location", response.headers)
        self.assertEqual(body_of(response), FILE_BODY)

    def test_a_streamed_download_still_says_it_is_an_attachment(self):
        # The Content-Disposition is what makes the browser save the blob under
        # a name rather than render it. Losing it while gaining the stream
        # would trade one bug for another.
        with patch.object(
            attachments_module.ticket_files, "resolve_url", return_value=SIGNED
        ):
            response = self.client.get(self.requester_url())
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("report.pdf", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Content-Type"], "application/pdf")

    def test_neither_endpoint_asks_azure_to_sign_a_url_it_will_not_use(self):
        # Signing is a round trip into the storage backend. prefer_stream skips
        # the call rather than making it and throwing the answer away.
        for label, url, who in (
            ("requester", self.requester_url(), self.requester),
            ("support", self.support_url(), self.agent),
        ):
            with self.subTest(endpoint=label):
                self.client.force_login(who)
                with patch.object(
                    attachments_module.ticket_files,
                    "resolve_url",
                    return_value=SIGNED,
                ) as resolve:
                    response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                resolve.assert_not_called()


@override_settings(MEDIA_ROOT=_MEDIA)
class RefusalsStayMachineReadableTests(APITestCase):
    """Every way this endpoint can refuse, answered as JSON with a status.

    ⚠️ These cases are HAND-DERIVED, not generated, and saying so matters
    because a hand-picked list of examples is the shape of fake test this
    project keeps producing. ``refusals()`` covers four of the six conditions
    the view's queryset encodes (views.py:333-341): the two it does not cover
    are ``message__ticket_id`` (an attachment id belonging to another ticket)
    and the ``INTERNAL_NOTE`` exclusion. All six leave by the same
    ``if attachment is None`` return, so the JSON-refusal behaviour under test
    is the same for every one of them — but nobody should read this list as
    exhaustive, and a seventh condition added later would not be noticed here.

    What the frontend reads is the STATUS, so that is what is pinned: a 403
    means "sign in again" and a 404 means "that file is gone". A body that
    negotiated its way to HTML carries neither.
    """

    def setUp(self):
        reset_managed_storage_caches()
        cache.clear()
        self.requester = User.objects.create_user(
            email="mia@example.com", password="pass1234",
            first_name="Mia", last_name="Thompson",
        )
        self.stranger = User.objects.create_user(
            email="alex@example.com", password="pass1234",
            first_name="Alex", last_name="Doe",
        )
        self.client.force_login(self.requester)
        data = self.client.post(
            LIST_URL,
            {
                "category": TicketCategory.HELP_STUDENT_GROUP,
                "subject": "With a file",
                "body": "See attached.",
                "files": pdf(),
            },
            format="multipart",
        ).json()["data"]
        self.ticket = Ticket.objects.get(pk=data["id"])
        self.attachment_id = data["messages"][0]["attachments"][0]["id"]

    def tearDown(self):
        reset_managed_storage_caches()

    def url(self):
        return f"{LIST_URL}{self.ticket.pk}/attachments/{self.attachment_id}/"

    def refusals(self):
        """(name, arrange callable, expected status) for each reachable refusal."""

        def soft_delete_ticket():
            Ticket.objects.filter(pk=self.ticket.pk).update(deleted_at=timezone.now())

        def soft_delete_message():
            self.ticket.messages.update(deleted_at=timezone.now())

        def sign_out():
            self.client.logout()

        def become_a_stranger():
            self.client.force_login(self.stranger)

        return [
            ("the ticket was deleted by an agent", soft_delete_ticket, 404),
            ("the parent message was deleted", soft_delete_message, 404),
            ("the session aged out", sign_out, 403),
            ("somebody else's ticket", become_a_stranger, 404),
        ]

    def test_every_refusal_answers_json_when_the_client_asks_for_json(self):
        for name, arrange, expected in self.refusals():
            with self.subTest(refusal=name):
                with self.captureOnCommitCallbacks(execute=True):
                    pass
                arrange()
                response = self.client.get(self.url(), HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, expected)
                self.assertIn("application/json", response.headers["Content-Type"])
                self.assertNotIn(b"<!DOCTYPE html>", body_of(response))
                # Undo, so each case starts from a working download again.
                Ticket.objects.filter(pk=self.ticket.pk).update(deleted_at=None)
                self.ticket.messages.update(deleted_at=None)
                self.client.force_login(self.requester)

    def test_a_missing_blob_answers_json_too(self):
        # The one refusal that comes from storage rather than the queryset, and
        # the one that would be 100% of downloads on day one if the container
        # and the tickets/ prefix did not line up in the deployed config.
        with patch.object(
            attachments_module.ticket_files, "open", side_effect=OSError("BlobNotFound")
        ):
            response = self.client.get(self.url(), HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response.headers["Content-Type"])

    def test_a_browser_accept_header_still_negotiates_its_way_to_html(self):
        # Not a wish, a measurement, and the reason the front ends must not
        # point the browser at this URL. settings.py declares no
        # DEFAULT_RENDERER_CLASSES, so DRF's browsable-API renderer wins
        # content negotiation for anything sending Accept: text/html. If this
        # ever stops being true the fix is still correct, but the sentence
        # explaining WHY it exists has stopped being true and should be redone.
        Ticket.objects.filter(pk=self.ticket.pk).update(deleted_at=timezone.now())
        response = self.client.get(self.url(), HTTP_ACCEPT=BROWSER_ACCEPT)
        self.assertEqual(response.status_code, 404)
        self.assertIn("text/html", response.headers["Content-Type"])
        self.assertIn(b"<!DOCTYPE html>", body_of(response))


class ServeManagedFileDefaultTests(SimpleTestCase):
    """The flag is off unless asked for, and off means exactly what it meant.

    ``serve_managed_file`` is shared. A wrong default here would put every
    resource, chat, submission and grading download through the app server
    instead of straight from Azure, which for a large file is a production
    incident rather than a test failure.
    """

    def serve(self, **kwargs):
        return serve_managed_file(
            resolve_url=lambda *_a, **_k: SIGNED,
            open_file=lambda _key: SimpleUploadedFile("report.pdf", FILE_BODY),
            storage_key="tickets/2026/08/x.pdf",
            filename="report.pdf",
            mime_type="application/pdf",
            size=len(FILE_BODY),
            as_attachment=True,
            **kwargs,
        )

    def test_without_the_flag_a_signed_url_is_still_a_redirect(self):
        response = self.serve()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], SIGNED)

    def test_with_the_flag_the_signed_url_is_never_asked_for(self):
        calls = []

        def resolve(*args, **kwargs):
            calls.append(args)
            return SIGNED

        response = serve_managed_file(
            resolve_url=resolve,
            open_file=lambda _key: SimpleUploadedFile("report.pdf", FILE_BODY),
            storage_key="tickets/2026/08/x.pdf",
            filename="report.pdf",
            mime_type="application/pdf",
            size=len(FILE_BODY),
            as_attachment=True,
            prefer_stream=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, [])

    def test_with_the_flag_an_unopenable_file_is_still_a_json_refusal(self):
        # The streamed path's own failure mode. It has to keep answering with a
        # status the caller can read, not raise.
        def boom(_key):
            raise OSError("BlobNotFound")

        response = serve_managed_file(
            resolve_url=lambda *_a, **_k: SIGNED,
            open_file=boom,
            storage_key="tickets/2026/08/x.pdf",
            filename="report.pdf",
            mime_type="application/pdf",
            size=len(FILE_BODY),
            as_attachment=True,
            prefer_stream=True,
        )
        self.assertEqual(response.status_code, 404)
        self.assertIn("application/json", response.headers["Content-Type"])


class OnlyTheTicketEndpointsOptInTests(SimpleTestCase):
    """Which call sites pass the flag, read off the source rather than listed.

    A hand-written list of call sites is the fake test this project keeps
    producing: it passes because it only checks the examples somebody thought
    of. The written specification for this fix said there were FOUR callers of
    ``serve_managed_file``; on this tree there are five, because the merge
    brought ``apps/submissions/views.py`` with it. So the callers are found by
    walking the AST of every module under ``apps/``, and a new one appearing
    anywhere fails this test until somebody decides which side it belongs on.
    """

    #: Modules whose download is answered to a fetch() and must stream.
    STREAMING = {"apps/tickets/views.py", "apps/tickets/views_admin.py"}

    def call_sites(self):
        root = Path(__file__).resolve().parents[3] / "apps"
        self.assertTrue(root.is_dir(), root)
        found = []
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if name != "serve_managed_file":
                    continue
                flag = next(
                    (kw for kw in node.keywords if kw.arg == "prefer_stream"), None
                )
                streams = bool(flag) and getattr(flag.value, "value", None) is True
                found.append(
                    (str(path.relative_to(root.parent)), node.lineno, streams)
                )
        return found

    def test_the_two_ticket_views_stream_and_no_other_caller_does(self):
        sites = self.call_sites()
        self.assertGreaterEqual(len(sites), 5, sites)
        streaming = {module for module, _line, streams in sites if streams}
        self.assertEqual(streaming, self.STREAMING, sites)

    def test_every_ticket_attachment_download_is_one_of_them(self):
        # Guards the other direction: a third ticket download endpoint added
        # later would be found here rather than shipping as a redirect.
        sites = {module for module, _line, _streams in self.call_sites()}
        ticket_sites = {module for module in sites if module.startswith("apps/tickets/")}
        self.assertEqual(ticket_sites, self.STREAMING, sorted(sites))
