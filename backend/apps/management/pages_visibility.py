"""Pages Visibility (Management > Challenge Start), kept by the server too:
until its date, students, mentors and supervisors are refused the APIs behind
Home, Groups, Events, Announcements and Resources, as the frontend hides those
pages from them. Admins always get them. A view is kept back by saying so:
``hidden_with_pages = True`` on its class."""
from __future__ import annotations

from django.http import JsonResponse
from django.utils import timezone

from apps.common.rbac import is_admin

HIDDEN = "This page isn't open yet. It opens on the date set on Management > Challenge Start."


def pages_shown_to(user) -> bool:
    """Whether ``user`` may see the pages now: always for an admin, else once
    Pages Visibility's date has come."""
    if is_admin(user) or user.is_staff or user.is_superuser:
        return True
    from .models import SupervisorPagesSetting

    return SupervisorPagesSetting.load().shown_at(timezone.now())


class PagesVisibilityMiddleware:
    """Refuses a view marked ``hidden_with_pages`` to anyone signed in who
    can't see the pages yet. Someone not signed in is left to the view, which
    asks them to sign in."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        view = getattr(view_func, "cls", None) or getattr(view_func, "view_class", None)
        if not getattr(view, "hidden_with_pages", False):
            return None
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or pages_shown_to(user):
            return None
        return JsonResponse({"error": HIDDEN, "code": "pages_hidden"}, status=403)
