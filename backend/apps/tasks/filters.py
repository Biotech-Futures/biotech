import django_filters
from rest_framework.exceptions import ValidationError

from .models import Milestone, Tasks

_TRUE_VALUES = frozenset(('true', '1', 'yes'))
_FALSE_VALUES = frozenset(('false', '0', 'no'))


class FlexibleDeletedFilter(django_filters.Filter):
    """Maps ?deleted= to a deleted_at__isnull lookup.

    Accepts true/1/yes and false/0/no (case-insensitive).
    Raises ValidationError (HTTP 400) for unrecognised values.
    """

    def filter(self, qs, value):
        if value in (None, ''):
            return qs
        normalised = value.strip().lower()
        if normalised in _TRUE_VALUES:
            return qs.filter(deleted_at__isnull=False)
        if normalised in _FALSE_VALUES:
            return qs.filter(deleted_at__isnull=True)
        raise ValidationError('Invalid deleted value. Expected true or false.')


class TaskFilter(django_filters.FilterSet):
    """FilterSet for GET /tasks/api/v1/tasks/.

    ?deleted=   — accepts true/false variants via FlexibleDeletedFilter.
    ?group_id=  — filters via task → milestone → group FK chain.
    ?milestone= — filters by milestone id.
    """
    deleted = FlexibleDeletedFilter(field_name='deleted_at')
    group_id = django_filters.NumberFilter(field_name='milestone__group_id')
    milestone = django_filters.NumberFilter(field_name='milestone')

    class Meta:
        model = Tasks
        fields = ['deleted', 'group_id', 'milestone']


class MilestoneFilter(django_filters.FilterSet):
    """FilterSet for GET /tasks/api/v1/milestones/.

    ?deleted=  — accepts true/false variants via FlexibleDeletedFilter.
    ?group_id= — filters by group id.
    """
    deleted = FlexibleDeletedFilter(field_name='deleted_at')
    group_id = django_filters.NumberFilter(field_name='group_id')

    class Meta:
        model = Milestone
        fields = ['deleted', 'group_id']
