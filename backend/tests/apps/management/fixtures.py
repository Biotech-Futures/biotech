"""Document template helpers for the Management tests: the marks summary
and certificates are made from templates uploaded on Document Setup."""
import io

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.management.models import GradingSettings


def _build_docx(text: str) -> bytes:
    """A one-paragraph docx for template fixtures."""
    from docx import Document as NewDocument

    doc = NewDocument()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _seed_doc_templates():
    """Upload token templates — no fallbacks ship in the repo any more."""
    row = GradingSettings.load()
    row.marks_summary_template = SimpleUploadedFile(
        "marks.docx",
        _build_docx(
            "Team {{TeamCode}} S1 {{SM1}} ({{ShortAnswerQuestionComment1}}) total {{CombinedTotal}} "
            "poster: {{PosterOverallComment}}"
        ),
    )
    row.certificate_template = SimpleUploadedFile(
        "cert.docx", _build_docx("{{Name}} — {{ProjectTitle}}")
    )
    row.mentor_certificate_template = SimpleUploadedFile(
        "mentor.docx", _build_docx("{{Name}} mentored {{ProjectTitle}}")
    )
    row.save()
    return row
