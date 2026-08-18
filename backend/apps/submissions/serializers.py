from rest_framework import serializers

from .models import Submission


class SubmissionSerializer(serializers.ModelSerializer):
    """Read shape for a team's current entry."""

    is_submitted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Submission
        fields = [
            "answers",
            "poster",
            "report",
            "prototype",
            "prototype_url",
            "submitted_at",
            "is_submitted",
            "is_late",
            "updated_at",
        ]
        read_only_fields = fields


class SubmissionDraftSerializer(serializers.Serializer):
    """Write shape for saving a draft.

    Only the text answers and the prototype link are editable here. Files are
    handled by their own upload endpoint, so they cannot be set or cleared by
    a stray field in a draft save.

    Both fields are optional so a client can update one without resending the
    other; ``partial`` semantics are handled explicitly in the view.
    """

    answers = serializers.DictField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        required=False,
    )
    prototype_url = serializers.URLField(required=False, allow_blank=True)
