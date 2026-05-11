"""drf_spectacular preprocessing hooks.

The project URLconf mounts most apps at two prefixes:

* ``/api/v1/<app>/...``  (canonical — what the FE and any new SDK consumer hit)
* ``/<app>/...``          (legacy — kept resolving so old clients don't break)

Some apps additionally expose an in-app ``v1/`` alias for their previous URL
layout (events, announcements, audit, certificates, matching_runtime). That
means each of those views is reachable at up to **four** URLs at runtime.

For the OpenAPI document we want only **one** canonical URL per operation —
the rest are backward-compat redirects, not API surface that SDK generators
should code-gen. This hook filters the endpoint list accordingly:

* Keep paths under ``/api/v1/...``.
* Drop paths matching ``/api/v1/<app>/v1/...`` — that's the in-app legacy
  alias bleeding through the v1 mount.

Without this, drf_spectacular emits ``operationId ... has collisions``
warnings and disambiguates duplicates with ``_2``/``_3``/``_4`` suffixes that
shift whenever the urlconf order shifts.
"""
from __future__ import annotations

import re
from typing import Any


# Matches the in-app legacy ``v1/`` alias paths that get re-exposed under the
# canonical mount, e.g. ``/api/v1/events/v1/<id>/rsvp/``. The first ``[^/]+``
# is the app prefix (``events``, ``announcements``, ...); the literal ``v1``
# segment that follows is what we want to suppress in the schema.
_LEGACY_V1_ALIAS_UNDER_API_V1 = re.compile(r"^/api/v1/[^/]+/v1(/|$)")


def filter_v1_only(endpoints: list[tuple[str, Any, str, Any]], **_: Any):
    """Return only the canonical ``/api/v1/...`` endpoints.

    Args:
        endpoints: list of ``(path, path_regex, method, callback)`` tuples
            produced by ``drf_spectacular`` before schema generation.

    Returns:
        The same list with non-canonical entries removed.
    """
    return [
        endpoint for endpoint in endpoints
        if endpoint[0].startswith("/api/v1/")
        and not _LEGACY_V1_ALIAS_UNDER_API_V1.match(endpoint[0])
    ]
