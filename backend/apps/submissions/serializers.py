from rest_framework import serializers

from .models import Submission, SubmissionQuestion


class SubmissionQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubmissionQuestion
        fields = ["key", "prompt", "help_text", "is_required", "max_words"]
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    """A team's entry: both the working copy and the submitted copy."""

    is_submitted = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    stage = serializers.CharField(read_only=True)
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "cohort",
            "answers",
            "poster",
            "poster_checks",
            "report",
            "prototype",
            "prototype_url",
            "submitted_answers",
            "submitted_poster",
            "submitted_poster_checks",
            "submitted_report",
            "submitted_prototype",
            "submitted_prototype_url",
            "submitted_at",
            "submitted_by_name",
            "reopened_at",
            "stage",
            "is_submitted",
            "is_locked",
            "is_late",
            "updated_at",
        ]
        read_only_fields = fields

    def get_submitted_by_name(self, obj) -> str:
        user = obj.submitted_by
        if user is None:
            return ""
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.email


class SubmissionDraftSerializer(serializers.Serializer):
    """Answers and the prototype link; files have their own endpoint."""

    answers = serializers.DictField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        required=False,
    )
    prototype_url = serializers.URLField(required=False, allow_blank=True)

    def validate_answers(self, value):
        questions = {q.key: q for q in SubmissionQuestion.active()}

        unknown = sorted(set(value) - set(questions))
        if unknown:
            raise serializers.ValidationError(
                f"Unknown question{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}."
            )

        too_long = []
        for key, answer in value.items():
            question = questions[key]
            limit = question.max_words
            if limit and SubmissionQuestion.count_words(answer) > limit:
                words = SubmissionQuestion.count_words(answer)
                too_long.append(f'"{question.prompt}" ({words} words, limit {limit})')
        if too_long:
            raise serializers.ValidationError(
                f"Answer too long for {', '.join(too_long)}."
            )

        return value


def missing_required_answers(submission) -> list[str]:
    """Prompts of the required questions this entry has left blank."""
    answers = submission.answers or {}
    return [
        question.prompt
        for question in SubmissionQuestion.active().filter(is_required=True)
        if not str(answers.get(question.key, "")).strip()
    ]
