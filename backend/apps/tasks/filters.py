"""
Task and Milestone FilterSets for the DRF filter pipeline.

Bug fix (#4): boolean parsing for ?deleted= lives here, not in views.
Centralising it in a FilterSet satisfies the OCP guideline — the view stays
closed to changes whenever new filter rules are needed; only this file grows.

FlexibleDeletedFilter handles all common boolean string representations and
raises HTTP 400 (not 500) for anything unrecognised, exactly as required.
"""
import django_filters
from rest_framework.exceptions import ValidationError

from .models import Milestone, Tasks

# Immutable sets for O(1) membership checks
_TRUE_VALUES = frozenset(('true', '1', 'yes'))
_FALSE_VALUES = frozenset(('false', '0', 'no'))


class FlexibleDeletedFilter(django_filters.Filter):
    """
    Maps ?deleted= query parameter to a deleted_flag BooleanField lookup.

    Accepted values:
      true / 1 / yes  → deleted_flag=True  (soft-deleted records only)
      false / 0 / no  → deleted_flag=False (active records only)

    Raises DRF ValidationError (HTTP 400) for any other value, replacing the
    previous HTTP 500 caused by passing raw strings to the ORM (#4).
    """

    def filter(self, qs, value):
        if value in (None, ''):
            return qs
        normalised = value.strip().lower()
        if normalised in _TRUE_VALUES:
            return qs.filter(deleted_flag=True)
        if normalised in _FALSE_VALUES:
            return qs.filter(deleted_flag=False)
        raise ValidationError('Invalid deleted value. Expected true or false.')


class TaskFilter(django_filters.FilterSet):
    """
    FilterSet for GET /tasks/api/v1/tasks/.

    Declares all supported query parameters so DRF's DjangoFilterBackend can
    apply them without any manual parameter inspection inside the view.

    ?deleted=   — FlexibleDeletedFilter handles all boolean variants (#4).
    ?group_id=  — filters tasks via the task → milestone → group FK chain (#1).
    ?milestone= — filters tasks belonging to a specific milestone.
    """
    deleted = FlexibleDeletedFilter(field_name='deleted_flag')
    group_id = django_filters.NumberFilter(field_name='milestone__group_id')
    milestone = django_filters.NumberFilter(field_name='milestone')

    class Meta:
        model = Tasks
        fields = ['deleted', 'group_id', 'milestone']


class MilestoneFilter(django_filters.FilterSet):
    """
    FilterSet for GET /tasks/api/v1/milestones/.

    ?deleted=  — same FlexibleDeletedFilter as tasks (#4).
    ?group_id= — filters milestones belonging to a specific group (#1).
    """
    deleted = FlexibleDeletedFilter(field_name='deleted_flag')
    group_id = django_filters.NumberFilter(field_name='group_id')

    class Meta:
        model = Milestone
        fields = ['deleted', 'group_id']
