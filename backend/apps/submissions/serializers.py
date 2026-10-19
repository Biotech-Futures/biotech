from rest_framework import serializers

from apps.common.rbac import is_admin

from .checklist import CHECKLIST_ITEMS
from .models import Submission, SubmissionQuestion

STAFF_NAME = "BIOTech Futures"


def submitted_by_label(submission) -> str:
    """Who submitted an entry, as its emails show it; an automated submission is the programme's."""
    if submission.auto_submitted:
        return STAFF_NAME
    return submitter_name(submission.submitted_by)


def submitter_name(user) -> str:
    """Who submitted, as the team sees it; staff acting for a team show as the programme."""
    if user is None:
        return ""
    if is_admin(user) or user.is_staff or user.is_superuser:
        return STAFF_NAME
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.email


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
            "project_title",
            "answers",
            "poster",
            "poster_checks",
            "report",
            "prototype",
            "prototype_url",
            "submitted_project_title",
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
            "auto_submitted",
            "poster_checklist",
            "updated_at",
        ]
        read_only_fields = fields

    def get_submitted_by_name(self, obj) -> str:
        return submitter_name(obj.submitted_by)


class SubmissionDraftSerializer(serializers.Serializer):
    """Title, answers, the prototype link and checklist ticks; files have their own endpoint."""

    project_title = serializers.CharField(max_length=150, required=False, allow_blank=True)
    answers = serializers.DictField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        required=False,
    )
    prototype_url = serializers.URLField(
        max_length=500,
        required=False,
        allow_blank=True,
        error_messages={
            "max_length": "This link is longer than 500 characters. Use a shorter share link.",
            "invalid": "This doesn't look like a web link. Paste the full address, for example https://www.figma.com/…",
        },
    )

    poster_checklist = serializers.DictField(child=serializers.BooleanField(), required=False)
    # Sent with answers and title by a page that cannot hold the live connection while co-editing is on.
    live_unavailable = serializers.BooleanField(required=False)

    def validate_poster_checklist(self, value):
        unknown = sorted(set(value) - set(CHECKLIST_ITEMS))
        if unknown:
            raise serializers.ValidationError(f"Unknown checklist item: {', '.join(unknown)}.")
        return value

    def validate_answers(self, value):
        questions = {q.key: q for q in SubmissionQuestion.active()}

        unknown = sorted(set(value) - set(questions))
        if unknown:
            raise serializers.ValidationError(
                f"Unknown question{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}."
            )
        return value

    def validate(self, attrs):
        # While co-editing, a page without the live connection saves answers as typed, as the shared
        # document does; the limit is checked when the entry is submitted.
        if self.context.get("saves_as_typed") and attrs.get("live_unavailable"):
            return attrs
        questions = {q.key: q for q in SubmissionQuestion.active()}
        too_long = []
        for key, answer in attrs.get("answers", {}).items():
            question = questions[key]
            limit = question.max_words
            if limit and SubmissionQuestion.count_words(answer) > limit:
                words = SubmissionQuestion.count_words(answer)
                too_long.append(f'"{question.prompt}" ({words} words, limit {limit})')
        if too_long:
            raise serializers.ValidationError({"answers": [f"Answer too long for {', '.join(too_long)}."]})
        return attrs


def over_limit_answers(submission) -> list[str]:
    """Prompts of the questions whose answer is over its word limit; only co-edited drafts can hold one."""
    answers = submission.answers or {}
    return [
        question.prompt
        for question in SubmissionQuestion.active()
        if question.max_words and SubmissionQuestion.count_words(str(answers.get(question.key, ""))) > question.max_words
    ]


def missing_required_answers(submission) -> list[str]:
    """Prompts of the required questions this entry has left blank."""
    answers = submission.answers or {}
    return [
        question.prompt
        for question in SubmissionQuestion.active().filter(is_required=True)
        if not str(answers.get(question.key, "")).strip()
    ]
