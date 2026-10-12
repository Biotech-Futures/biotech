"""Question and guidance fixtures; CI disables migrations, so seeded data never exists there."""
from apps.submissions.checklist import CHECKLIST_ITEMS
from apps.submissions.models import Submission, SubmissionInstruction, SubmissionQuestion

# Every poster checklist item ticked, as a team would before submitting.
CONFIRMED_CHECKLIST = {item: True for item in CHECKLIST_ITEMS}


QUESTIONS = (
    ("solution_purpose", "What does your solution do?"),
    ("inspiration", "What was the inspiration for your solution?"),
    ("research", "What research did you carry out?"),
    ("development", "How did you develop your solution?"),
    ("challenges", "What challenges did you face?"),
    ("future_work", "What would you do next?"),
)

MAX_WORDS = 150


def install_question_set():
    """Replace any existing questions with a known set."""
    SubmissionQuestion.objects.all().delete()
    return [
        SubmissionQuestion.objects.create(
            key=key,
            prompt=prompt,
            order=index,
            is_required=True,
            max_words=MAX_WORDS,
            is_active=True,
        )
        for index, (key, prompt) in enumerate(QUESTIONS)
    ]


INSTRUCTIONS = (
    ("questions", "Short Answer Questions", "Max 150 words each."),
    ("poster", "Poster", "Upload your poster as a PDF."),
    ("extras", "Additional Materials", "Optional supporting material."),
)


def install_instructions():
    SubmissionInstruction.objects.all().delete()
    return [
        SubmissionInstruction.objects.create(section=section, heading=heading, body=body)
        for section, heading, body in INSTRUCTIONS
    ]


def install_reference_data():
    return install_question_set(), install_instructions()


def confirm_checklist(group):
    """Tick the team's whole poster checklist, as Submit requires."""
    Submission.objects.filter(group=group).update(poster_checklist=CONFIRMED_CHECKLIST)
