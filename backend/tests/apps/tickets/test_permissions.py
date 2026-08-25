from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from apps.tickets.models import SupportScope
from apps.tickets.permissions import IsSupportScoped, is_support
from apps.users.models import AdminScope

User = get_user_model()


class IsSupportTests(TestCase):
    """The four quadrants of DEC-001.

    Every admin can work the queue; not every agent is an admin. Both halves
    of that OR are load-bearing, so both are pinned here.
    """

    def setUp(self):
        self.nobody = User.objects.create_user(email="student@example.com", password="pass1234")
        self.agent = User.objects.create_user(email="agent@example.com", password="pass1234")
        self.admin = User.objects.create_user(email="admin@example.com", password="pass1234")
        self.both = User.objects.create_user(email="both@example.com", password="pass1234")

        SupportScope.objects.create(user=self.agent)
        AdminScope.objects.create(user=self.admin)
        SupportScope.objects.create(user=self.both)
        AdminScope.objects.create(user=self.both)

    def test_an_agent_with_only_a_support_row_is_support(self):
        self.assertTrue(is_support(self.agent))

    def test_an_admin_is_support_without_a_support_row(self):
        self.assertTrue(is_support(self.admin))

    def test_holding_both_rows_is_support(self):
        self.assertTrue(is_support(self.both))

    def test_an_ordinary_user_is_not_support(self):
        self.assertFalse(is_support(self.nobody))

    def test_an_anonymous_visitor_is_not_support_and_does_not_blow_up(self):
        # DEC-019 B3: querying with AnonymousUser raises TypeError, which would
        # reach the client as a 500 instead of a 403.
        self.assertFalse(is_support(AnonymousUser()))

    def test_a_missing_user_is_not_support(self):
        self.assertFalse(is_support(None))


class IsSupportScopedTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.permission = IsSupportScoped()
        self.agent = User.objects.create_user(email="agent2@example.com", password="pass1234")
        SupportScope.objects.create(user=self.agent)
        self.outsider = User.objects.create_user(email="outsider@example.com", password="pass1234")

    def _check(self, user):
        request = self.factory.get("/api/v1/admin/tickets/")
        request.user = user
        return self.permission.has_permission(request, view=None)

    def test_support_passes(self):
        self.assertTrue(self._check(self.agent))

    def test_a_signed_in_outsider_is_refused(self):
        self.assertFalse(self._check(self.outsider))

    def test_an_anonymous_visitor_is_refused(self):
        self.assertFalse(self._check(AnonymousUser()))
