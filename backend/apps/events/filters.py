"""Filters for the public events list endpoint.

Driven by ``django-filter`` so each query-param maps to a declarative
filter (OCP — adding a new filter doesn't require touching the view).
"""

import django_filters

from .models import Events
from .services import get_user_registered_event_ids


class EventFilter(django_filters.FilterSet):
    """Query-param filtering for ``GET /events/v1/``.

    Supported params:
      - ``registered=true`` / ``mine=true`` (aliases): restrict the
        result to events the requesting user has actively RSVP'd
        ``GOING`` for. ``=false`` returns the complement (events they
        have not committed to). Both names accepted because the FE
        spec calls out either as acceptable.
      - ``category=workshop``: filter by ``Events.event_type``,
        case-insensitive. Maps the FE's "category" label onto the model
        field without requiring the FE to know the underlying name.

    The "registered" definition is delegated to
    ``services.get_user_registered_event_ids`` so the filter and the
    per-row ``EventSerializer.registered`` field cannot drift apart.
    """

    registered = django_filters.BooleanFilter(method="filter_registered")
    mine = django_filters.BooleanFilter(method="filter_registered")
    category = django_filters.CharFilter(field_name="event_type", lookup_expr="iexact")

    class Meta:
        model = Events
        fields = ["registered", "mine", "category"]

    def filter_registered(self, queryset, name, value):
        # ``request`` may be absent in schema generation; guard rather
        # than raise so drf-spectacular can still introspect the view.
        request = getattr(self, "request", None)
        user = getattr(request, "user", None) if request is not None else None
        if user is None or not getattr(user, "is_authenticated", False):
            # An anonymous caller asking ``registered=true`` cannot
            # have any registrations; ``registered=false`` keeps the
            # full queryset.
            return queryset.none() if value else queryset

        registered_ids = get_user_registered_event_ids(user)
        if value:
            return queryset.filter(id__in=registered_ids)
        return queryset.exclude(id__in=registered_ids)
