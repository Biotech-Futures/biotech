import django_filters

from .models import Task


class DeletedFilter(django_filters.BooleanFilter):
    # `?deleted=true` shows soft-deleted rows; `?deleted=false` shows active.
    # That's the inverse of the natural `deleted_at__isnull`, hence the override.
    def filter(self, qs, value):
        if value is None:
            return qs
        return qs.filter(deleted_at__isnull=not value)


class TaskFilter(django_filters.FilterSet):
    deleted = DeletedFilter(field_name="deleted_at")
    task_type = django_filters.ChoiceFilter(choices=Task._meta.get_field("task_type").choices)
    group_id = django_filters.NumberFilter(field_name="group_id")
    assigned_user = django_filters.NumberFilter(field_name="assigned_user_id")
    parent_id = django_filters.NumberFilter(field_name="parent_id")

    class Meta:
        model = Task
        fields = ["deleted", "task_type", "group_id", "assigned_user", "parent_id"]
