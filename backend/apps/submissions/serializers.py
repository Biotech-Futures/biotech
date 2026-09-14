from rest_framework import serializers

from .models import Submission, SubmissionQuestion


class SubmissionQuestionSerializer(serializers.ModelSerializer):
    """The question set the entry form should render."""

    class Meta:
        model = SubmissionQuestion
        fields = ["key", "prompt", "help_text", "is_required", "max_words"]
        read_only_fields = fields


class SubmissionSerializer(serializers.ModelSerializer):
    """Read shape for a team's entry, working copy and submitted copy alike.

    Both are sent: a locked entry shows the submitted copy, a reopened one the
    draft. Keeping them separate lets an abandoned revision leave it intact.
    """

    is_submitted = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    stage = serializers.CharField(read_only=True)
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            # Published for the grading side, which would otherwise infer the
            # year from submitted_at — wrong across a grace window.
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
        """Who submitted, for the "submitted by X on Y" line."""
        user = obj.submitted_by
        if user is None:
            return ""
        full_name = f"{user.first_name} {user.last_name}".strip()
        return full_name or user.email


class SubmissionDraftSerializer(serializers.Serializer):
    """Write shape for saving a draft.

    Answers and the prototype link only; files have their own endpoint, so a
    stray field here cannot set or clear one. Both fields are optional.
    """

    answers = serializers.DictField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        required=False,
    )
    prototype_url = serializers.URLField(required=False, allow_blank=True)

    def validate_answers(self, value):
        """Reject unknown keys and over-long answers.

        Refused rather than ignored: dropping them silently would let a client
        believe an answer had been saved when it had not.
        """
        questions = {q.key: q for q in SubmissionQuestion.active()}

        unknown = sorted(set(value) - set(questions))
        if unknown:
            raise serializers.ValidationError(
                f"Unknown question{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}."
            )

        # Each answer against its own limit. The client's Qualtrics form checks
        # every question against the *first* answer, so only that one is capped.
        too_long = []
        for key, answer in value.items():
            question = questions[key]
            limit = question.max_words
            if limit and SubmissionQuestion.count_words(answer) > limit:
                words = SubmissionQuestion.count_words(answer)
                # The question's wording, not its key: a student has no reason
                # to know what "solution_purpose" means.
                too_long.append(f'"{question.prompt}" ({words} words, limit {limit})')
        if too_long:
            raise serializers.ValidationError(
                f"Answer too long for {', '.join(too_long)}."
            )

        return value


def missing_required_answers(submission) -> list[str]:
    """Prompts of the required questions this entry has left blank.

    Checked at submit, not on every save, so a team can stop half-way.
    """
    answers = submission.answers or {}
    return [
        question.prompt
        for question in SubmissionQuestion.active().filter(is_required=True)
        if not str(answers.get(question.key, "")).strip()
    ]
