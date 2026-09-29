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

The one exception is ``AMissingStoredFileIsA404Tests``, which has to see what
the Azure backend does when a blob is missing. It switches ticket storage to
the real Azure classes and fakes only the HTTP session underneath the SDK.
"""
import ast
import errno
import io
import logging
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import requests
from azure.core.pipeline.transport import RequestsTransport
from azure.storage.blob import ContainerClient
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.storage import (
    get_ticket_storage,
    reset_managed_storage_caches,
    serve_managed_file,
)
from apps.tickets.models import (
    SupportScope,
    Ticket,
    TicketAttachment,
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
        #
        # The file is really taken off disk rather than open() being patched.
        # The patch used to raise a bare OSError("BlobNotFound"), which neither
        # backend this runs on raises for a missing file (local storage raises
        # FileNotFoundError, Azure raises ResourceNotFoundError), and any other
        # OSError, a permission problem say, is now meant to stay a 500.
        key = TicketAttachment.objects.get(pk=self.attachment_id).storage_key
        get_ticket_storage().backend.delete(key)
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


AZURE_SETTINGS = {
    "USE_AZURE_BLOB_STORAGE": True,
    "AZURE_CONNECTION_STRING": "",
    "AZURE_ACCOUNT_NAME": "acct",
    "AZURE_ACCOUNT_KEY": "a2V5",
    "AZURE_CHAT_CONTAINER": "chat",
    "AZURE_CUSTOM_DOMAIN": "",
}

# Every byte value, so a stream that re-encoded or trimmed anything shows.
AZURE_BODY = b"%PDF-1.4\n" + bytes(range(256)) * 40


class _AzureAnswers(requests.Session):
    """The bottom of the real Azure SDK stack, answering the way Azure does.

    Everything above this session is production code. azure-core's own
    pipeline turns these HTTP answers into the exceptions it really raises
    (a 404 becomes ResourceNotFoundError, a 403 an HttpResponseError), and it
    raises them from inside django-storages' own AzureStorageFile at the moment
    that class really asks. Patching any higher means choosing the exception
    and the moment by hand, and the moment is the whole bug here: open() never
    touches the network, the first touch of the file does.
    """

    def __init__(self, answer):
        super().__init__()
        self.answer = answer
        self.seen = []

    def request(self, method, url, **kwargs):
        self.seen.append((method, urlparse(url).path))
        return self.answer(url)


def _azure_reply(url, status_code, headers, body):
    reply = requests.Response()
    reply.status_code = status_code
    reply.headers.update(headers)
    reply.headers["Content-Length"] = str(len(body))
    reply.raw = io.BytesIO(body)
    reply.url = url
    return reply


def _azure_error(url, status_code, code):
    body = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f"<Error><Code>{code}</Code><Message>{code}</Message></Error>"
    ).encode()
    return _azure_reply(
        url,
        status_code,
        {"x-ms-error-code": code, "Content-Type": "application/xml"},
        body,
    )


def blob_not_found(url):
    return _azure_error(url, 404, "BlobNotFound")


def container_not_found(url):
    return _azure_error(url, 404, "ContainerNotFound")


def access_refused(url):
    return _azure_error(url, 403, "AuthorizationFailure")


def unreachable(url):
    raise requests.ConnectionError("Connection refused")


def blob_holding(body):
    def answer(url):
        return _azure_reply(
            url,
            206,
            {
                "Content-Range": f"bytes 0-{len(body) - 1}/{len(body)}",
                "Content-Type": "application/pdf",
                "ETag": '"0x8DC0000000000"',
                "Last-Modified": "Mon, 28 Sep 2026 10:00:00 GMT",
                "x-ms-blob-type": "BlockBlob",
            },
            body,
        )

    return answer


@override_settings(MEDIA_ROOT=_MEDIA)
class AMissingStoredFileIsA404Tests(APITestCase):
    """T15. A row whose file storage no longer has is "not found", on both sides.

    It was a 404 in development and a 500 in production. Local storage opens
    eagerly, so a missing file raised inside the try around open().
    django-storages' AzureStorageFile is lazy: open() returns without a network
    call, the blob is fetched the first time anything touches the file, and the
    first thing that did was FileResponse's own header code, outside every try.
    Both front ends read a 500 as "try again", which for a file that is gone is
    advice that can never work.

    The other half matters as much: only "not there" becomes a 404. Storage
    refusing our credentials, or not answering at all, is an outage somebody
    has to see, so it stays a logged 500.
    """

    NOT_FOUND = {"msg": "Attachment not found", "data": None}

    def setUp(self):
        reset_managed_storage_caches()
        cache.clear()
        # The SDK logs every request and response at INFO. Noise here.
        azure_logger = logging.getLogger("azure")
        self.addCleanup(azure_logger.setLevel, azure_logger.level)
        azure_logger.setLevel(logging.WARNING)

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
        # An earlier ticket carrying three files and one follow-up, so that the
        # ticket, message and attachment under test get three different ids.
        # On a fresh test database they would all be 1, and a warning that
        # printed one id in the other's place would still read correctly.
        #
        # The follow-up is what keeps message ids ahead of ticket ids. This
        # used to lean on creation writing a second, system line, and C-05
        # took that line away: the ids collapsed to (2, 2, 4) with nothing
        # else changed. A message the requester sends is not going anywhere.
        earlier = self.client.post(
            LIST_URL,
            {
                "category": TicketCategory.HELP_STUDENT_GROUP,
                "subject": "Earlier",
                "body": "Three files.",
                "files": [pdf("one.pdf"), pdf("two.pdf"), pdf("three.pdf")],
            },
            format="multipart",
        )
        # Checked here because nothing below reads it: if it were refused,
        # the ids would quietly collapse back to 1, 1, 1.
        self.assertEqual(earlier.status_code, 201, earlier.content)
        follow_up = self.client.post(
            f"{LIST_URL}{earlier.json()['data']['id']}/messages/",
            {"body": "One more thing."},
        )
        self.assertEqual(follow_up.status_code, 201, follow_up.content)
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
        row = TicketAttachment.objects.get(pk=self.attachment_id)
        self.storage_key = row.storage_key
        self.message_id = row.message_id

    def tearDown(self):
        reset_managed_storage_caches()

    def endpoints(self):
        return (
            (
                "requester",
                f"{LIST_URL}{self.ticket.pk}/attachments/{self.attachment_id}/",
                self.requester,
            ),
            (
                "support",
                f"/api/v1/admin/tickets/{self.ticket.pk}/attachments/{self.attachment_id}/",
                self.agent,
            ),
        )

    def get_from_azure(self, url, answer):
        """GET the url with ticket storage on Azure and `answer` behind the SDK."""
        session = _AzureAnswers(answer)
        with override_settings(**AZURE_SETTINGS):
            reset_managed_storage_caches()
            get_ticket_storage().backend._client = ContainerClient(
                "https://acct.blob.core.windows.net",
                "chat",
                credential={"account_name": "acct", "account_key": "a2V5"},
                transport=RequestsTransport(session=session, session_owner=False),
                # Each fake answers every request the same way, so a retry
                # would only repeat it, after a backoff sleep.
                retry_total=0,
            )
            response = self.client.get(url, HTTP_ACCEPT="application/json")
            body = body_of(response)
        reset_managed_storage_caches()
        return response, body, session.seen

    def test_a_blob_azure_no_longer_has_is_a_404_on_both_endpoints(self):
        for side, url, who in self.endpoints():
            with self.subTest(endpoint=side):
                self.client.force_login(who)
                response, _body, seen = self.get_from_azure(url, blob_not_found)
                # One GET, and Azure answered it. The 404 is Azure's answer
                # passed on, not a shortcut that never reached storage.
                self.assertEqual(seen, [("GET", f"/chat/{self.storage_key}")])
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), self.NOT_FOUND)

    def test_a_file_gone_from_local_disk_is_the_same_404(self):
        # The real FileSystemStorage, raising its real FileNotFoundError.
        get_ticket_storage().backend.delete(self.storage_key)
        for side, url, who in self.endpoints():
            with self.subTest(endpoint=side):
                self.client.force_login(who)
                response = self.client.get(url, HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), self.NOT_FOUND)

    def test_a_missing_file_is_logged_by_id_and_nothing_else(self):
        # Ticket and attachment ids only. The storage key ends in the
        # student's own file name, so it stays out of a line that ops will
        # paste into chat. The reason tells one lost blob (BlobNotFound) from
        # a container that is not configured at all (ContainerNotFound): one
        # missing file, or every download failing.
        #
        # Only meaningful while the three ids differ, which setUp arranges.
        self.assertEqual(
            len({self.ticket.pk, self.message_id, self.attachment_id}),
            3,
            (self.ticket.pk, self.message_id, self.attachment_id),
        )
        prefix = (
            f"ticket_attachment.file_missing ticket={self.ticket.pk} "
            f"attachment={self.attachment_id}"
        )
        for side, url, who in self.endpoints():
            for answer, reason in (
                (blob_not_found, "BlobNotFound"),
                (container_not_found, "ContainerNotFound"),
            ):
                with self.subTest(backend="azure", endpoint=side, reason=reason):
                    self.client.force_login(who)
                    with self.assertLogs(
                        "apps.tickets.services.attachments", level="WARNING"
                    ) as logged:
                        self.get_from_azure(url, answer)
                    self.assertEqual(
                        [(r.levelno, r.getMessage()) for r in logged.records],
                        [(logging.WARNING, f"{prefix} reason={reason}")],
                    )

        get_ticket_storage().backend.delete(self.storage_key)
        for side, url, who in self.endpoints():
            with self.subTest(backend="local", endpoint=side):
                self.client.force_login(who)
                with self.assertLogs(
                    "apps.tickets.services.attachments", level="WARNING"
                ) as logged:
                    self.client.get(url, HTTP_ACCEPT="application/json")
                self.assertEqual(
                    [(r.levelno, r.getMessage()) for r in logged.records],
                    [(logging.WARNING, f"{prefix} reason=FileNotFoundError")],
                )

    def test_azure_refusing_or_not_answering_is_still_a_logged_500(self):
        for label, answer, raised in (
            ("403 AuthorizationFailure", access_refused, "HttpResponseError"),
            ("connection refused", unreachable, "ServiceRequestError"),
        ):
            for side, url, who in self.endpoints():
                with self.subTest(azure=label, endpoint=side):
                    self.client.force_login(who)
                    with (
                        self.assertLogs("config.exception_handler", level="ERROR") as logged,
                        self.assertLogs("django.request", level="ERROR"),
                        self.assertNoLogs("apps.tickets.services.attachments", level="WARNING"),
                    ):
                        response, _body, seen = self.get_from_azure(url, answer)
                    self.assertEqual(seen, [("GET", f"/chat/{self.storage_key}")])
                    self.assertEqual(response.status_code, 500)
                    self.assertEqual(response.json()["code"], "internal_server_error")
                    self.assertEqual(
                        [type(r.exc_info[1]).__name__ for r in logged.records],
                        [raised],
                    )

    def test_a_local_permission_error_is_a_logged_500_not_a_404(self):
        # FileSystemStorage._open is where the real local backend calls the
        # builtin open(), so it is where a permission problem really raises.
        # This used to be answered 404 with nothing logged at all.
        denied = PermissionError(errno.EACCES, "Permission denied")
        for side, url, who in self.endpoints():
            with self.subTest(endpoint=side):
                self.client.force_login(who)
                with (
                    patch.object(get_ticket_storage().backend, "_open", side_effect=denied),
                    self.assertLogs("config.exception_handler", level="ERROR") as logged,
                    self.assertLogs("django.request", level="ERROR"),
                    self.assertNoLogs("apps.tickets.services.attachments", level="WARNING"),
                ):
                    response = self.client.get(url, HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, 500)
                self.assertEqual(
                    [type(r.exc_info[1]).__name__ for r in logged.records],
                    ["PermissionError"],
                )

    def test_a_file_that_exists_still_streams_byte_identical(self):
        for side, url, who in self.endpoints():
            self.client.force_login(who)
            with self.subTest(backend="azure", endpoint=side):
                response, body, seen = self.get_from_azure(url, blob_holding(AZURE_BODY))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body, AZURE_BODY)
                self.assertEqual(response.headers["Content-Length"], str(len(AZURE_BODY)))
                self.assertEqual(
                    response.headers["Content-Disposition"],
                    'attachment; filename="report.pdf"',
                )
                # Still one download. Proving the blob is there must not cost
                # a second round trip (an exists() first, say) on every file.
                self.assertEqual(seen, [("GET", f"/chat/{self.storage_key}")])
            with self.subTest(backend="local", endpoint=side):
                response = self.client.get(url, HTTP_ACCEPT="application/json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(body_of(response), FILE_BODY)
                self.assertEqual(response.headers["Content-Length"], str(len(FILE_BODY)))


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
