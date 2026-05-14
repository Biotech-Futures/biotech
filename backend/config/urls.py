"""URL configuration for the project.

The frontend always hits ``/api/v1/<app>/...`` first and falls back to the
legacy unprefixed path on 404. Originally only a handful of apps were mounted
under ``/api/v1/`` (``admin``, ``users``, ``tasks``) so every chat / dashboard /
groups / resources request paid a 404 round-trip before resolving against the
legacy path.

This module mounts each app under **both** prefixes where doing so is clean:

* ``/api/v1/<app>/...`` — canonical, what the FE hits first.
* ``/<app>/...`` — legacy, kept so old clients, the curl scripts in the
  link-preview PR, and the existing test suite continue to resolve.

Only apps whose internal URLconf has **no internal ``v1/`` segment** are
dual-mounted (see :data:`_DUAL_MOUNTS` below) — otherwise the v1 mount would
produce nonsense paths like ``/api/v1/events/v1/...``.
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


# Apps that should be served from BOTH ``/api/v1/<prefix>`` and ``/<prefix>``.
#
# To add a new entry:
#   1. Open the app's ``urls.py`` and confirm it does NOT register routes under
#      its own ``v1/`` segment (no ``router.register(r"v1", ...)`` and no
#      ``path("api/v1/", include(...))`` inside). If it does, mounting it here
#      will create double-prefixed paths like ``/api/v1/events/v1/`` — skip it.
#   2. Confirm the module does not declare ``app_name`` (otherwise dual-mount
#      registers the namespace twice and emits ``urls.W005``).
_DUAL_MOUNTS: tuple[tuple[str, str], ...] = (
    # The reported case: FE primary URL is ``/api/v1/chat/groups/<gid>/messages/``.
    ("chat/",      "apps.chat.urls"),
    # FE hits ``/api/v1/dashboard/{summary,progress,...}/``.
    ("dashboard/", "apps.dashboard.urls"),
    # FE hits ``/api/v1/groups/...`` for group listings + members.
    ("groups/",    "apps.groups.urls"),
    # FE hits ``/api/v1/resources/`` for the resource catalogue.
    ("resources/", "apps.resources.urls"),
    # ``services`` exposes csrf/login/logout endpoints; dual-mount for consistency.
    ("services/",  "apps.services.urls"),
)


def _dual_mount_patterns():
    """Return a fresh list of include() patterns built from :data:`_DUAL_MOUNTS`.

    Each call instantiates a new URL resolver per ``include()``, so the same
    module can safely be mounted at two different prefixes without Django
    reusing internal caches.
    """
    return [path(prefix, include(module)) for prefix, module in _DUAL_MOUNTS]


# Routes that live exclusively under ``/api/v1/``. ``apps.admin.urls`` declares
# ``app_name='admin_api'`` (distinct from Django's built-in ``admin`` namespace
# used by ``admin.site.urls``) and stays single-mounted. ``apps.users.urls``
# registers ``users/``, ``admin/summary/``, etc. at its own root, so mounting it
# at the v1 root keeps ``/api/v1/users/me/`` and friends working.
_api_v1_patterns = [
    *_dual_mount_patterns(),
    path("admin/", include("apps.admin.urls")),
    path("tasks/", include("apps.tasks.urls")),
    path("", include("apps.users.urls")),
]


urlpatterns = [
    path("admin/", admin.site.urls),

    # Canonical v1 mount — registered first so it short-circuits the legacy
    # 404→fallback dance the FE currently relies on.
    path("api/v1/", include(_api_v1_patterns)),

    # Legacy mounts — preserved so old clients, the curl integration scripts
    # checked into the link-preview PR, and the existing test suite keep
    # resolving. Apps with internal ``v1/`` segments (events, announcements,
    # audit, certificates, matching_runtime) live ONLY here today — adding a
    # ``/api/v1/`` mount for them needs a per-app urlconf refactor first.
    *_dual_mount_patterns(),
    path("users/", include("apps.users.urls")),
    path("dashboard/v1/", include("apps.dashboard.urls")),  # historical alias
    path("events/", include("apps.events.urls")),
    path("announcements/", include("apps.announcements.urls")),
    path("audit/", include("apps.audit.urls")),
    path("matching/", include("apps.matching_runtime.urls")),
    path("certificates/", include("apps.certificates.urls")),

    path("api-auth/", include("rest_framework.urls")),  # browsable API login

    # Schema & docs.
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
