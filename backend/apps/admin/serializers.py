"""Request-shape validation for admin endpoints."""
from rest_framework import serializers

from apps.admin.services.user import ROLES


class BulkUserRowSerializer(serializers.Serializer):
    """Shape-only guard for one row of the bulk user import.

    Validation only — callers must pass the ORIGINAL request rows to the service,
    never ``validated_data``: ``add_users_by_role`` reads ~20 keys straight off each
    raw dict and DRF would drop every one this serializer does not declare.
    """

    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=ROLES, required=False)
    groupNumber = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def to_internal_value(self, data):
        # A group number is naturally numeric, so accept scalars; the service
        # str()-coerces it. Containers are still rejected — they'd be meaningless.
        group_number = data.get("groupNumber") if isinstance(data, dict) else None
        if isinstance(group_number, (list, dict, tuple, set)):
            raise serializers.ValidationError(
                {"groupNumber": ["Must be a string or number."]}
            )
        return super().to_internal_value(data)


def bulk_user_error_message(errors) -> str:
    """Flatten DRF's per-row error map into one row-numbered message."""
    if isinstance(errors, dict):
        return _format_row(errors) or "Invalid user payload"

    parts = [
        f"Row {index + 1}: {_format_row(row_errors)}"
        for index, row_errors in enumerate(errors)
        if row_errors
    ]
    return "; ".join(parts) or "Invalid user payload"


def _format_row(row_errors) -> str:
    if not isinstance(row_errors, dict):
        return " ".join(str(e) for e in row_errors)
    return ", ".join(
        f"{field} - {' '.join(str(m) for m in messages)}"
        for field, messages in row_errors.items()
    )
