from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
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

    def _build_request(self, method="post"):
        # Tracking middleware only writes on state-changing methods, so the
        # tracking-behaviour tests below use POST. The GET-skip behaviour has
        # its own test (test_skips_safe_methods).
        builder = getattr(self.factory, method)
        request = builder("/services/session-test/")
        session_middleware = SessionMiddleware(lambda req: HttpResponse("ok"))
        session_middleware.process_request(request)
        request.session.create()
        request.user = self.user
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

    def test_reopens_existing_row_for_same_sid_without_creating_duplicate(self):
        request = self._build_request()
        closed_at = timezone.now() - timedelta(minutes=5)
        tracked_session = UserSession.objects.create(
            user=self.user,
            sid=request.session.session_key,
            created_at=closed_at - timedelta(minutes=10),
            last_activity_at=closed_at - timedelta(minutes=1),
            expires_at=closed_at + timedelta(minutes=30),
            ended_at=closed_at,
            revoked_at=closed_at,
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
