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
    status = django_filters.ChoiceFilter(choices=Task._meta.get_field("status").choices)
    completed = django_filters.BooleanFilter(field_name="completed")
    group_id = django_filters.NumberFilter(field_name="group_id")
    assigned_user = django_filters.NumberFilter(field_name="assigned_user_id")
    parent_id = django_filters.NumberFilter(field_name="parent_id")
    due_date_after = django_filters.IsoDateTimeFilter(field_name="due_date", lookup_expr="gte")
    due_date_before = django_filters.IsoDateTimeFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Task
        fields = [
            "deleted",
            "task_type",
            "status",
            "completed",
            "group_id",
            "assigned_user",
            "parent_id",
            "due_date_after",
            "due_date_before",
        ]
