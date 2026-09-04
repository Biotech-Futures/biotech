from rest_framework import serializers

from .models import Grade, Rubric, RubricCriterion, SubmissionComponent


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


# The per-component "submission" block of the marking payload is built by
# services.content.entry_payload — the submissions app no longer has a
# per-component model for a ModelSerializer to wrap.


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

    # Display name of the last marker, so the marking page can say who last
    # touched each criterion without a second lookup.
    graded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Grade
        fields = [
            "id",
            "submission",
            "criterion",
            "mark",
            "comment",
            "graded_by",
            "graded_by_name",
            "graded_at",
        ]
        read_only_fields = ["id", "submission", "criterion", "graded_by", "graded_by_name", "graded_at"]

    @staticmethod
    def get_graded_by_name(obj) -> str | None:
        user = obj.graded_by
        if user is None:
            return None
        return f"{user.first_name} {user.last_name}".strip() or user.email


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
    """Optional per-component overall comment saved alongside the grades.

    ``component`` is the component code (e.g. "POSTER"). Required whenever the
    entry has submitted content for more than one component — one submission id
    covers the whole entry, so the id alone cannot say which comment this is.
    """

    submission = serializers.IntegerField()
    component = serializers.CharField(allow_blank=True, required=False, default="")
    comment = serializers.CharField(allow_blank=True, default="")


class GradeBulkRequestSerializer(serializers.Serializer):
    items = GradeBulkItemSerializer(many=True)
    overall_comments = OverallCommentItemSerializer(many=True, required=False, default=list)
