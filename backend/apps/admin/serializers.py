"""Request-shape validation for admin endpoints."""
import nh3
from rest_framework import serializers

from apps.admin.services.user import ROLES
from apps.services.email_registry import (
    get_email_type,
    is_known_email_type,
    unknown_merge_tags,
)


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


class SystemEmailTemplateUpdateSerializer(serializers.Serializer):
    """PATCH /api/v1/admin/email-template/<key>/ body.

    Every field is optional (PATCH semantics) so toggling an email does not
    disturb its wording and vice versa. The serializer rejects wording that
    references a merge tag the email type cannot fill, refuses to switch off a
    locked type, and sanitises the body with nh3 before it is ever stored.
    """

    subject = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )
    body = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    enabled = serializers.BooleanField(required=False)

    def validate(self, attrs):
        key = self.context.get("key", "")
        if not is_known_email_type(key):
            # Leave the 404 decision to the service/view; validating tags or
            # locked state against a non-existent type would raise KeyError.
            return attrs

        email_type = get_email_type(key)
        if attrs.get("enabled") is False and email_type.locked:
            raise serializers.ValidationError(
                {
                    "enabled": [
                        f"The '{email_type.name}' email is required for signing "
                        "in and cannot be switched off."
                    ]
                }
            )

        for field in ("subject", "body"):
            value = attrs.get(field)
            if value is None:
                continue
            unknown = unknown_merge_tags(key, value)
            if unknown:
                raise serializers.ValidationError(
                    {
                        field: [
                            "Unsupported merge tag(s): "
                            f"'{', '.join(sorted(unknown))}'"
                        ]
                    }
                )

        # nh3 keeps the formatting an admin can produce in the editor and
        # strips scripts, event handlers and javascript: URLs.
        if attrs.get("body"):
            attrs["body"] = nh3.clean(attrs["body"])
        return attrs


class SystemEmailPreviewSerializer(serializers.Serializer):
    """Optional unsaved wording for preview / test-send.

    Absent fields mean "use the saved/default wording"; an explicit empty
    string means "clear it", which is why both are allowed and null is not
    silently coerced to empty.
    """

    subject = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, max_length=255
    )
    body = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class SystemEmailSettingsUpdateSerializer(serializers.Serializer):
    """PATCH /api/v1/admin/email-settings/ body."""

    enabled = serializers.BooleanField()


def serializer_error_message(errors) -> str:
    """Flatten DRF's error map into one human-readable message."""
    if isinstance(errors, dict):
        return "; ".join(
            f"{field} - {' '.join(str(m) for m in messages)}"
            for field, messages in errors.items()
        )
    return " ".join(str(error) for error in errors)
