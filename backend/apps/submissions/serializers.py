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

    Both are sent: a locked entry displays the submitted copy, while a reopened
    one shows the draft being edited. Keeping them separate is what lets an
    abandoned revision leave the submitted version intact.
    """

    is_submitted = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)
    status = serializers.CharField(read_only=True)
    submitted_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            "answers",
            "poster",
            "report",
            "prototype",
            "prototype_url",
            "submitted_answers",
            "submitted_poster",
            "submitted_report",
            "submitted_prototype",
            "submitted_prototype_url",
            "submitted_at",
            "submitted_by_name",
            "reopened_at",
            "status",
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

    def validate_answers(self, value):
        """Reject unknown keys and over-long answers.

        Unknown keys are refused rather than ignored: silently dropping them
        would let a client believe an answer had been saved when it had not.
        Retired questions are treated as unknown for writing, while their
        existing answers stay readable.
        """
        questions = {q.key: q for q in SubmissionQuestion.active()}

        unknown = sorted(set(value) - set(questions))
        if unknown:
            raise serializers.ValidationError(
                f"Unknown question{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}."
            )

        # Each answer is measured against its own limit. Worth stating because
        # the client's Qualtrics form gets this wrong: every question there
        # validates the length of the *first* answer, so in practice only that
        # one is capped.
        too_long = []
        for key, answer in value.items():
            limit = questions[key].max_words
            if limit and SubmissionQuestion.count_words(answer) > limit:
                words = SubmissionQuestion.count_words(answer)
                too_long.append(f"{key} ({words} words, limit {limit})")
        if too_long:
            raise serializers.ValidationError(
                f"Answer too long for {', '.join(too_long)}."
            )

        return value


def missing_required_answers(submission) -> list[str]:
    """Prompts of the required questions this entry has left blank.

    Checked at submit time rather than on every draft save, so a team can
    stop half-way and come back without being nagged.
    """
    answers = submission.answers or {}
    return [
        question.prompt
        for question in SubmissionQuestion.active().filter(is_required=True)
        if not str(answers.get(question.key, "")).strip()
    ]
