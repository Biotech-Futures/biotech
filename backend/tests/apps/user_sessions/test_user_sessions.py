from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import IntegrityError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.user_sessions.middleware import SessionTrackingMiddleware
from apps.user_sessions.models import UserSession

User = get_user_model()


class SessionTrackingMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="session-user@example.com",
            password="testpass123",
            first_name="Session",
            last_name="User",
        )
        self.middleware = SessionTrackingMiddleware(lambda request: HttpResponse("ok"))

    def _build_request(self, method="post", *, with_session_key=True, user=None):
        # Tracking middleware only writes on state-changing methods, so the
        # tracking-behaviour tests below use POST. The GET-skip behaviour has
        # its own test (test_skips_safe_methods).
        builder = getattr(self.factory, method)
        request = builder("/services/session-test/")
        session_middleware = SessionMiddleware(lambda req: HttpResponse("ok"))
        session_middleware.process_request(request)
        if with_session_key:
            request.session.create()
        request.user = self.user if user is None else user
        return request

    def test_skips_safe_methods(self):
        for method in ("get", "head", "options"):
            UserSession.objects.all().delete()
            request = self._build_request(method=method)
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                UserSession.objects.count(),
                0,
                f"{method.upper()} should not create a user_session row",
            )

    def test_updates_active_session_activity_and_expiry(self):
        request = self._build_request()
        opened_at = timezone.now() - timedelta(minutes=15)
        tracked_session = UserSession.objects.create(
            user=self.user,
            sid=request.session.session_key,
            created_at=opened_at,
            last_activity_at=opened_at,
            expires_at=opened_at + timedelta(minutes=30),
        )

        before_request = timezone.now()
        response = self.middleware(request)

        tracked_session.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserSession.objects.count(), 1)
        self.assertIsNone(tracked_session.ended_at)
        self.assertIsNone(tracked_session.revoked_at)
        self.assertGreaterEqual(tracked_session.last_activity_at, before_request)
        self.assertGreater(tracked_session.expires_at, tracked_session.last_activity_at)

    def test_does_not_resurrect_revoked_session_and_flushes_django_session(self):
        # Mirror apps.users.utils.sessions.terminate_user_sessions: revoked
        # + ended set. A surviving authenticated request landing on this row
        # must NOT clear those flags (otherwise the security signal vanishes), and
        # the Django session should be flushed so subsequent requests from
        # this client cannot proceed.
        request = self._build_request()
        original_sid = request.session.session_key
        terminated_at = timezone.now() - timedelta(minutes=5)
        tracked_session = UserSession.objects.create(
            user=self.user,
            sid=original_sid,
            created_at=terminated_at - timedelta(minutes=10),
            last_activity_at=terminated_at - timedelta(minutes=1),
            expires_at=terminated_at + timedelta(minutes=30),
            ended_at=terminated_at,
            revoked_at=terminated_at,
        )

        response = self.middleware(request)

        tracked_session.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        # Revocation flags survive intact.
        self.assertEqual(tracked_session.ended_at, terminated_at)
        self.assertEqual(tracked_session.revoked_at, terminated_at)
        # last_activity_at / expires_at are NOT bumped on a revoked session,
        # otherwise the row would look active in dashboards / audit views.
        self.assertLess(tracked_session.last_activity_at, timezone.now() - timedelta(seconds=1))
        # The Django session is gone — the client's next request is anonymous.
        self.assertIsNone(request.session.session_key)

    def test_does_not_resurrect_ended_only_session(self):
        # Defence in depth: ended without revoked should also not be reopened.
        request = self._build_request()
        ended_at = timezone.now() - timedelta(minutes=5)
        tracked_session = UserSession.objects.create(
            user=self.user,
            sid=request.session.session_key,
            created_at=ended_at - timedelta(minutes=10),
            last_activity_at=ended_at - timedelta(minutes=1),
            expires_at=ended_at + timedelta(minutes=30),
            ended_at=ended_at,
        )

        self.middleware(request)

        tracked_session.refresh_from_db()
        self.assertEqual(tracked_session.ended_at, ended_at)
        self.assertIsNone(tracked_session.revoked_at)
        self.assertIsNone(request.session.session_key)

    def test_skips_when_no_session_key_token_auth_case(self):
        # Token/JWT clients arrive authenticated but with no Django session.
        # Creating one here would orphan a django_session row (the cookie is
        # never set on this response) and bloat user_session with a fresh row
        # per API call.
        request = self._build_request(with_session_key=False)
        self.assertIsNone(request.session.session_key)

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserSession.objects.count(), 0)
        # And no session was implicitly created behind our back.
        self.assertIsNone(request.session.session_key)

    def test_skips_when_user_anonymous(self):
        request = self._build_request(user=AnonymousUser())
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserSession.objects.count(), 0)

    def test_tracking_failure_does_not_break_response(self):
        # The view has already committed by the time we run; a DB hiccup in
        # the tracking write must not bubble up and surface as a 500 to the
        # client, or non-idempotent endpoints get retried.
        request = self._build_request()
        with patch.object(
            UserSession.objects,
            "get_or_create",
            side_effect=RuntimeError("db is on fire"),
        ):
            response = self.middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        # No row was written, but the request still completed successfully.
        self.assertEqual(UserSession.objects.count(), 0)

    def test_recovers_if_another_request_inserts_same_sid_first(self):
        request = self._build_request()
        stale_created_at = timezone.now() - timedelta(hours=1)
        stale_expires_at = stale_created_at + timedelta(minutes=30)

        def concurrent_insert(*args, **kwargs):
            UserSession._base_manager.create(
                user=self.user,
                sid=kwargs["sid"],
                created_at=stale_created_at,
                last_activity_at=stale_created_at,
                expires_at=stale_expires_at,
            )
            raise IntegrityError("duplicate key value violates unique constraint")

        before_request = timezone.now()
        with patch.object(UserSession.objects, "get_or_create", side_effect=concurrent_insert):
            response = self.middleware(request)

        tracked_session = UserSession.objects.get(sid=request.session.session_key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserSession.objects.count(), 1)
        self.assertGreaterEqual(tracked_session.last_activity_at, before_request)
        self.assertGreater(tracked_session.expires_at, stale_expires_at)
