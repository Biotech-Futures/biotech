from rest_framework import serializers

from apps.submissions.models import Submission

from .models import SubmissionComponent

from .models import Grade, Rubric, RubricCriterion


class SubmissionComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionComponent
        fields = [
            "id",
            "code",
            "name",
            "is_optional",
            "accepts_file",
            "accepts_text",
            "accepts_link",
            "order",
        ]
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    # `file.url` on an Azure Blob-backed FileField returns a SAS-signed URL
    # whose expiry is controlled by settings.AZURE_URL_EXPIRATION_SECS.
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "id",
            "component",
            "file_url",
            "text",
            "link",
            "submitted_at",
            "is_late",
            "overall_comment",
        ]
        read_only_fields = fields

    @staticmethod
    def get_file_url(obj) -> str | None:
        if not obj.file:
            return None
        try:
            return obj.file.url
        except Exception:
            # Missing blob / mis-configured storage shouldn't 500 the whole
            # marking payload — surface as null and let the UI say "unavailable".
            return None


class RubricCriterionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RubricCriterion
        fields = [
            "id",
            "rubric",
            "name",
            "description",
            "max_mark",
            "order",
        ]
        read_only_fields = fields


class RubricSerializer(serializers.ModelSerializer):
    criteria = RubricCriterionSerializer(many=True, read_only=True)

    class Meta:
        model = Rubric
        fields = [
            "id",
            "component",
            "year",
            "active",
            "criteria",
        ]
        read_only_fields = fields


class GradeSerializer(serializers.ModelSerializer):
    """Read + PATCH single grade. Only ``mark`` and ``comment`` are writable."""

    class Meta:
        model = Grade
        fields = [
            "id",
            "submission",
            "criterion",
            "mark",
            "comment",
            "graded_by",
            "graded_at",
        ]
        read_only_fields = ["id", "submission", "criterion", "graded_by", "graded_at"]


class GradeBulkItemSerializer(serializers.Serializer):
    """Body item for POST /grades/bulk/.

    ``id`` is optional — if present, the grade is updated. If absent, a Grade
    is upserted against (submission, criterion). Both must resolve to the
    same rubric's criterion + a submission of the same component; enforced
    in the view.
    """

    id = serializers.IntegerField(required=False)
    submission = serializers.IntegerField()
    criterion = serializers.IntegerField()
    mark = serializers.DecimalField(max_digits=6, decimal_places=2, allow_null=True, required=False)
    comment = serializers.CharField(allow_blank=True, required=False, default="")


class OverallCommentItemSerializer(serializers.Serializer):
    """Optional per-submission overall comment saved alongside the grades."""

    submission = serializers.IntegerField()
    comment = serializers.CharField(allow_blank=True, default="")


class GradeBulkRequestSerializer(serializers.Serializer):
    items = GradeBulkItemSerializer(many=True)
    overall_comments = OverallCommentItemSerializer(many=True, required=False, default=list)
